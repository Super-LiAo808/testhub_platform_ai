"""Sync discovered locators into UI Element management (independent of TestCase compile)."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from django.db import transaction

from apps.ui_automation.models import Element, ElementGroup, LocatorStrategy, UiProject
from apps.ui_automation.services.action_trace import _is_unstable_only, _rank_locators

logger = logging.getLogger(__name__)

STRATEGY_ALIAS = {
    'css selector': 'css',
    'css_selector': 'css',
    'test_id': 'test-id',
    'testid': 'test-id',
    'data-testid': 'test-id',
}


def get_or_create_strategy(name: str) -> LocatorStrategy:
    name = STRATEGY_ALIAS.get((name or 'css').lower(), (name or 'css').lower())
    strategy, _ = LocatorStrategy.objects.get_or_create(
        name=name,
        defaults={'description': f'Auto-created for element sync ({name})'},
    )
    return strategy


def guess_element_type(action_type: str) -> str:
    if action_type == 'fill':
        return 'INPUT'
    if action_type == 'click':
        return 'BUTTON'
    if action_type == 'hover':
        return 'LINK'
    return 'TEXT'


def _page_label(url: str) -> str:
    if not url:
        return ''
    try:
        parsed = urlparse(url)
        path = parsed.path or '/'
        if len(path) > 180:
            path = path[:180]
        return f'{parsed.netloc}{path}' if parsed.netloc else path
    except Exception:
        return (url or '')[:200]


def _ensure_ai_group(project: UiProject, page: str) -> Optional[ElementGroup]:
    root_name = 'AI发现'
    root, _ = ElementGroup.objects.get_or_create(
        project=project,
        name=root_name,
        parent_group=None,
        defaults={},
    )
    if not page:
        return root
    child_name = page[:100]
    child, _ = ElementGroup.objects.get_or_create(
        project=project,
        name=child_name,
        parent_group=root,
        defaults={},
    )
    return child


def _element_name(action: Dict[str, Any], suffix: str) -> str:
    name = action.get('description') or ''
    if not name:
        primary = action.get('primary_locator') or {}
        name = primary.get('value') or f'元素_{suffix}'
    name = re.sub(r'\s+', ' ', str(name)).strip()[:180]
    return name or f'元素_{suffix}'


@transaction.atomic
def upsert_element_from_action(
    project: UiProject,
    action: Dict[str, Any],
    *,
    created_by=None,
    source: str = 'ai_discovered',
    name_suffix: str = '1',
    skip_unstable: bool = True,
) -> Optional[Element]:
    locators = _rank_locators(action.get('locators') or [])
    if skip_unstable and _is_unstable_only(locators):
        return None
    primary = action.get('primary_locator') or (locators[0] if locators else None)
    if not primary or not primary.get('value'):
        return None

    strategy = get_or_create_strategy(primary.get('strategy') or 'css')
    value = str(primary['value'])[:500]
    page = _page_label(action.get('url') or '')
    group = _ensure_ai_group(project, page) if source == 'ai_discovered' else None

    backups = []
    for loc in locators[1:]:
        if loc.get('value'):
            entry = {'strategy': loc.get('strategy') or 'css', 'value': str(loc['value'])[:500]}
            if entry['strategy'] != strategy.name or entry['value'] != value:
                backups.append(entry)

    existing = Element.objects.filter(
        project=project,
        locator_strategy=strategy,
        locator_value=value,
    ).first()
    if existing:
        changed = False
        merged = list(existing.backup_locators or [])
        for entry in backups:
            if entry not in merged:
                merged.append(entry)
                changed = True
        update_fields = []
        if changed:
            existing.backup_locators = merged
            update_fields.append('backup_locators')
        if source and getattr(existing, 'discovery_source', None) in (None, '', 'manual'):
            if hasattr(existing, 'discovery_source'):
                existing.discovery_source = source
                update_fields.append('discovery_source')
        if group and not existing.group_id:
            existing.group = group
            update_fields.append('group')
        if page and not existing.page:
            existing.page = page
            update_fields.append('page')
        if update_fields:
            update_fields.append('updated_at')
            existing.save(update_fields=update_fields)
        return existing

    return Element.objects.create(
        project=project,
        group=group,
        name=_element_name(action, name_suffix),
        description=action.get('description') or '',
        element_type=guess_element_type(action.get('action_type') or 'click'),
        locator_strategy=strategy,
        locator_value=value,
        backup_locators=backups or None,
        page=page,
        discovery_source=source,
        created_by=created_by,
    )


def sync_elements_from_actions(
    project: UiProject,
    actions: List[Dict[str, Any]],
    *,
    created_by=None,
    source: str = 'ai_discovered',
    skip_unstable: bool = True,
) -> Dict[str, Any]:
    """
    Upsert Element records from normalized actions.
    Returns stats: created/updated/skipped/element_ids.
    """
    created = 0
    updated = 0
    skipped = 0
    element_ids: List[int] = []
    seen_keys = set()

    for i, action in enumerate(actions or [], start=1):
        if not action.get('needs_element') and action.get('action_type') not in (
            'click', 'fill', 'hover', 'waitFor', 'getText', 'assert', 'scroll'
        ):
            continue
        locators = _rank_locators(action.get('locators') or [])
        if not locators:
            skipped += 1
            continue
        if skip_unstable and _is_unstable_only(locators):
            skipped += 1
            continue
        primary = locators[0]
        key = (primary.get('strategy'), primary.get('value'))
        before = Element.objects.filter(
            project=project,
            locator_strategy=get_or_create_strategy(primary.get('strategy') or 'css'),
            locator_value=str(primary.get('value') or '')[:500],
        ).first()
        el = upsert_element_from_action(
            project,
            {**action, 'locators': locators, 'primary_locator': primary, 'needs_element': True},
            created_by=created_by,
            source=source,
            name_suffix=str(i),
            skip_unstable=skip_unstable,
        )
        if not el:
            skipped += 1
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        element_ids.append(el.id)
        if before:
            updated += 1
        else:
            created += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'total': len(element_ids),
        'element_ids': element_ids,
    }


def ensure_page_scan_group(
    project: UiProject,
    url: str,
    *,
    group_id: Optional[int] = None,
    title: str = '',
) -> ElementGroup:
    """每个 URL 只对应一个页面分组（不拆子模块）。"""
    if group_id:
        group = ElementGroup.objects.filter(id=group_id, project=project).first()
        if group:
            return group
        raise ValueError(f'分组不存在或不属于当前项目: {group_id}')

    page = _page_label(url) or '未命名页面'
    # 优先复用同名分组；否则挂在「页面扫描」根下建一个子组（仍是单页一层）
    existing = ElementGroup.objects.filter(project=project, name=page[:100]).first()
    if existing:
        return existing

    root, _ = ElementGroup.objects.get_or_create(
        project=project,
        name='页面扫描',
        parent_group=None,
        defaults={'description': 'Playwright 页面扫描自动创建'},
    )
    child_name = page[:100]
    if title:
        # 名称仍用 URL path，描述写标题，避免同站多标题冲突
        pass
    child, _ = ElementGroup.objects.get_or_create(
        project=project,
        name=child_name,
        parent_group=root,
        defaults={'description': (title or url or '')[:500]},
    )
    if title and not child.description:
        child.description = title[:500]
        child.save(update_fields=['description', 'updated_at'])
    return child


@transaction.atomic
def upsert_element_from_scan_item(
    project: UiProject,
    item: Dict[str, Any],
    *,
    group: Optional[ElementGroup] = None,
    created_by=None,
    source: str = 'page_scan',
) -> Optional[Element]:
    """Upsert one scanned element into the given page group."""
    locators = _rank_locators(item.get('locators') or [])
    primary = item.get('primary_locator') or (locators[0] if locators else None)
    if not primary or not primary.get('value'):
        return None

    strategy = get_or_create_strategy(primary.get('strategy') or 'css')
    value = str(primary['value'])[:500]
    page = _page_label(item.get('url') or '')
    component_name = str(item.get('component_name') or '')[:100]
    element_type = str(item.get('element_type') or 'BUTTON').upper()
    valid_types = {c[0] for c in Element.ELEMENT_TYPE_CHOICES}
    if element_type not in valid_types:
        element_type = 'BUTTON'

    backups = []
    for loc in locators[1:]:
        if loc.get('value'):
            entry = {'strategy': loc.get('strategy') or 'css', 'value': str(loc['value'])[:500]}
            if entry['strategy'] != strategy.name or entry['value'] != value:
                backups.append(entry)

    name = re.sub(r'\s+', ' ', str(item.get('name') or '')).strip()[:180] or f'扫描元素_{value[:40]}'
    description = str(item.get('description') or '')[:500]

    existing = Element.objects.filter(
        project=project,
        locator_strategy=strategy,
        locator_value=value,
    ).first()
    if existing:
        update_fields = []
        merged = list(existing.backup_locators or [])
        changed = False
        for entry in backups:
            if entry not in merged:
                merged.append(entry)
                changed = True
        if changed:
            existing.backup_locators = merged
            update_fields.append('backup_locators')
        # 不抢占用户已手动归组的元素；仅空分组或同为扫描分组时可写入
        if group and existing.group_id != group.id:
            existing_src = getattr(existing, 'discovery_source', None) or ''
            if not existing.group_id or existing_src in ('page_scan', 'ai_discovered'):
                existing.group = group
                update_fields.append('group')
        if page and existing.page != page:
            existing.page = page
            update_fields.append('page')
        if component_name and not existing.component_name:
            existing.component_name = component_name
            update_fields.append('component_name')
        if source and getattr(existing, 'discovery_source', None) in (None, '', 'manual'):
            existing.discovery_source = source
            update_fields.append('discovery_source')
        if description and not existing.description:
            existing.description = description
            update_fields.append('description')
        if update_fields:
            update_fields.append('updated_at')
            existing.save(update_fields=update_fields)
        return existing

    return Element.objects.create(
        project=project,
        group=group,
        name=name,
        description=description,
        element_type=element_type,
        locator_strategy=strategy,
        locator_value=value,
        backup_locators=backups or None,
        page=page,
        component_name=component_name,
        discovery_source=source,
        created_by=created_by,
    )


def sync_elements_from_scan(
    project: UiProject,
    candidates: List[Dict[str, Any]],
    *,
    group: Optional[ElementGroup] = None,
    created_by=None,
    source: str = 'page_scan',
) -> Dict[str, Any]:
    """Batch upsert scanned candidates into one page group."""
    created = 0
    updated = 0
    skipped = 0
    element_ids: List[int] = []
    preview: List[Dict[str, Any]] = []
    seen_keys = set()

    for item in candidates or []:
        primary = item.get('primary_locator') or {}
        if not primary.get('value'):
            skipped += 1
            continue
        key = (primary.get('strategy'), str(primary.get('value'))[:500])
        if key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(key)

        before = Element.objects.filter(
            project=project,
            locator_strategy=get_or_create_strategy(primary.get('strategy') or 'css'),
            locator_value=str(primary.get('value') or '')[:500],
        ).first()
        el = upsert_element_from_scan_item(
            project,
            item,
            group=group,
            created_by=created_by,
            source=source,
        )
        if not el:
            skipped += 1
            continue
        element_ids.append(el.id)
        if before:
            updated += 1
        else:
            created += 1
        if len(preview) < 30:
            preview.append({
                'id': el.id,
                'name': el.name,
                'element_type': el.element_type,
                'component_name': el.component_name,
                'locator_strategy': el.locator_strategy.name if el.locator_strategy_id else '',
                'locator_value': el.locator_value,
            })

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'total': len(element_ids),
        'element_ids': element_ids,
        'preview': preview,
        'group_id': group.id if group else None,
        'group_name': group.name if group else '',
    }

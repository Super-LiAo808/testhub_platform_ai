"""Project-level self-healing policy helpers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

DEFAULT_HEAL_SETTINGS: Dict[str, Any] = {
    'auto_diagnose': True,
    'mode': 'manual_apply',  # diagnose_only | manual_apply | auto_low_risk
    # promote_backup: 元素库备用升格；update_locator 仅当 auto_from_element 且来自 backup/suggested
    'auto_apply_types': ['increase_wait', 'add_backup_locator', 'promote_backup', 'force_action', 'regenerate_script'],
    'verify_rerun': True,
    'auto_promote_backup': False,
    'auto_pick_from_element': True,  # 诊断时结合元素库主/备定位自动选定修复方案
    'use_llm_on_manual_diagnose': True,
}

VALID_MODES = frozenset({'diagnose_only', 'manual_apply', 'auto_low_risk'})


def merge_heal_settings(raw: Any) -> Dict[str, Any]:
    settings = deepcopy(DEFAULT_HEAL_SETTINGS)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in settings or key in DEFAULT_HEAL_SETTINGS:
                settings[key] = value
    mode = settings.get('mode') or 'manual_apply'
    if mode not in VALID_MODES:
        settings['mode'] = 'manual_apply'
    types = settings.get('auto_apply_types')
    if not isinstance(types, list):
        settings['auto_apply_types'] = list(DEFAULT_HEAL_SETTINGS['auto_apply_types'])
    return settings


def get_project_heal_settings(project) -> Dict[str, Any]:
    if project is None:
        return merge_heal_settings({})
    if hasattr(project, 'get_heal_settings'):
        return project.get_heal_settings()
    return merge_heal_settings(getattr(project, 'heal_settings', None) or {})


def is_auto_diagnose_enabled(project) -> bool:
    return bool(get_project_heal_settings(project).get('auto_diagnose', True))


def can_write_test_assets(project) -> bool:
    """diagnose_only forbids applying writes to elements."""
    return get_project_heal_settings(project).get('mode') != 'diagnose_only'


def should_auto_apply(project, fix_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    settings = get_project_heal_settings(project)
    if settings.get('mode') != 'auto_low_risk':
        return False
    allowed = settings.get('auto_apply_types') or []
    if fix_type in allowed:
        return True
    # 元素库自动选定的定位修复：在开启 auto_pick_from_element 时视为低风险可写
    payload = payload if isinstance(payload, dict) else {}
    if (
        settings.get('auto_pick_from_element', True)
        and payload.get('auto_from_element')
        and fix_type in ('promote_backup', 'update_locator')
        and payload.get('replace_primary')
    ):
        src = (payload.get('locator_source') or '').lower()
        # 备用升格最安全；suggested 消歧次之；纯 LLM 仍需白名单
        return src in ('backup', 'suggested') or fix_type == 'promote_backup'

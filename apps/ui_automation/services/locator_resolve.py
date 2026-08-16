"""Shared locator candidate resolution with backup fallbacks and element-DB ranking."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def build_locator_candidates(element_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build ordered locator candidates: primary first, then backups."""
    element_data = element_data or {}
    candidates: List[Dict[str, Any]] = []
    primary_strategy = element_data.get('locator_strategy') or 'css'
    primary_value = element_data.get('locator_value') or ''
    if primary_value:
        candidates.append({
            'strategy': primary_strategy,
            'value': primary_value,
            'is_primary': True,
        })
    for backup in element_data.get('backup_locators') or []:
        if isinstance(backup, dict) and backup.get('value'):
            candidates.append({
                'strategy': backup.get('strategy') or 'css',
                'value': backup['value'],
                'is_primary': False,
            })
    if not candidates and primary_value:
        candidates.append({
            'strategy': primary_strategy,
            'value': primary_value,
            'is_primary': True,
        })
    return candidates


def mark_locator_hit(step_meta: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Attach locator_used / used_backup onto a result meta dict."""
    step_meta = dict(step_meta or {})
    step_meta['locator_used'] = {
        'strategy': candidate.get('strategy') or 'css',
        'value': candidate.get('value') or '',
    }
    step_meta['used_backup'] = not bool(candidate.get('is_primary', True))
    return step_meta


def _norm_locator(locator: Any) -> Optional[Dict[str, str]]:
    if not isinstance(locator, dict):
        return None
    value = (locator.get('value') or '').strip()
    if not value:
        return None
    strategy = (locator.get('strategy') or 'css').strip() or 'css'
    return {'strategy': strategy, 'value': value}


def _locator_key(locator: Dict[str, Any]) -> Tuple[str, str]:
    return (str(locator.get('strategy') or '').lower(), str(locator.get('value') or ''))


_STRATEGY_SCORE = {
    'test-id': 100,
    'testid': 100,
    'id': 90,
    'name': 75,
    'role': 70,
    'placeholder': 65,
    'label': 65,
    'css': 55,
    'css selector': 55,
    'text': 40,
    'xpath': 35,
    'title': 30,
}


def _score_candidate(
    candidate: Dict[str, Any],
    *,
    error_kind: str,
    demote_primary: bool,
    element_meta: Optional[Dict[str, Any]] = None,
) -> float:
    """Higher is better. Prefer backups when primary failed; prefer stable strategies."""
    loc = _norm_locator(candidate) or {}
    strategy = (loc.get('strategy') or 'css').lower()
    value = loc.get('value') or ''
    source = (candidate.get('source') or '').lower()
    score = float(_STRATEGY_SCORE.get(strategy, 50))

    # Shorter, more specific selectors tend to be better (weak heuristic)
    if strategy in ('css', 'css selector', 'xpath') and value:
        score += max(0, 40 - min(len(value), 80) * 0.4)

    if 'nth=' in value:
        score += 15  # disambiguation
    if 'visible=true' in value.lower():
        score += 20

    if source == 'backup' or candidate.get('is_primary') is False:
        # 元素库备用优先于临时 nth/visible 消歧建议
        if source == 'backup':
            score += 80 if demote_primary else 20
        else:
            score += 50 if demote_primary else 10
    if source == 'primary' or candidate.get('is_primary') is True:
        score -= 40 if demote_primary else 0
    if source == 'suggested':
        score += 15  # 消歧候选，弱于 backup
    if source == 'llm':
        score += 35
    if source == 'action_trace':
        score += 30

    meta = element_meta or {}
    # Prefer recorded/scanned assets slightly
    disc = (meta.get('discovery_source') or '').lower()
    if disc in ('recorded', 'page_scan', 'ai_discovered'):
        score += 5
    # Heal churn: heavily healed elements' primary is less trusted
    heal_count = int(meta.get('heal_count') or 0)
    if demote_primary and (source == 'primary' or candidate.get('is_primary')):
        score -= min(heal_count * 3, 20)

    if error_kind == 'ambiguous' and source == 'primary':
        score -= 30
    if error_kind == 'not_found' and source == 'primary':
        score -= 35

    return score


def build_disambiguation_candidates(
    current_locator: Optional[Dict[str, Any]],
    match_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Generate nth / visible candidates from a failed primary locator."""
    loc = _norm_locator(current_locator or {})
    if not loc:
        return []
    strategy = (loc.get('strategy') or 'css').lower()
    value = loc.get('value') or ''
    if strategy == 'id':
        base = value if value.startswith('#') else f'#{value}'
    elif strategy in ('css', 'css selector'):
        base = value
    else:
        return []

    out: List[Dict[str, Any]] = []
    n = max(2, min(int(match_count or 4), 6))
    if 'visible=true' not in base.lower():
        out.append({
            'strategy': 'css',
            'value': f'{base} >> visible=true',
            'source': 'suggested',
            'label': '仅可见元素',
            'is_primary': False,
        })
    for i in range(n):
        out.append({
            'strategy': 'css',
            'value': f'{base} >> nth={i}',
            'source': 'suggested',
            'label': f'第 {i + 1} 个匹配',
            'is_primary': False,
        })
    return out


def candidates_from_element_model(element) -> List[Dict[str, Any]]:
    """Primary + backup from Element ORM, with labels/sources for ranking."""
    candidates: List[Dict[str, Any]] = []
    if not element:
        return candidates
    strategy_name = 'css'
    if getattr(element, 'locator_strategy', None):
        strategy_name = element.locator_strategy.name or 'css'
    primary = _norm_locator({
        'strategy': strategy_name,
        'value': getattr(element, 'locator_value', '') or '',
    })
    if primary:
        candidates.append({
            **primary,
            'source': 'primary',
            'label': '当前主定位器',
            'is_primary': True,
        })
    for backup in (getattr(element, 'backup_locators', None) or []):
        loc = _norm_locator(backup)
        if not loc:
            continue
        if any(_locator_key(c) == _locator_key(loc) for c in candidates):
            continue
        candidates.append({
            **loc,
            'source': 'backup',
            'label': '备用定位器（元素库）',
            'is_primary': False,
        })
    return candidates


def rank_and_pick_from_element(
    element=None,
    *,
    error_kind: str = 'not_found',
    match_count: Optional[int] = None,
    current_locator: Optional[Dict[str, Any]] = None,
    extra_candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Pick best repair locator from Element DB (+ optional extras).

    Returns dict:
      picked: {strategy,value,source,label,score} | None
      ranked: list
      fix_type: promote_backup | update_locator | None
      replace_primary: bool
      auto_from_element: bool
      reason: str
    """
    error_kind = (error_kind or 'not_found').lower()
    demote_primary = error_kind in ('not_found', 'ambiguous', 'locator_break', 'strict')

    element_meta: Dict[str, Any] = {}
    pool: List[Dict[str, Any]] = []
    if element is not None:
        pool.extend(candidates_from_element_model(element))
        element_meta = {
            'discovery_source': getattr(element, 'discovery_source', '') or '',
            'heal_count': getattr(element, 'heal_count', 0) or 0,
            'is_unique': bool(getattr(element, 'is_unique', False)),
            'page': getattr(element, 'page', '') or '',
            'element_id': getattr(element, 'id', None),
        }

    # Ambiguous: add nth/visible variants of failed primary
    if error_kind in ('ambiguous', 'strict'):
        failed = current_locator or (pool[0] if pool else None)
        for d in build_disambiguation_candidates(failed, match_count):
            if not any(_locator_key(c) == _locator_key(d) for c in pool):
                pool.append(d)

    for extra in extra_candidates or []:
        loc = _norm_locator(extra)
        if not loc:
            continue
        if any(_locator_key(c) == _locator_key(loc) for c in pool):
            continue
        pool.append({**extra, **loc})

    if not pool:
        return {
            'picked': None,
            'ranked': [],
            'fix_type': None,
            'replace_primary': False,
            'auto_from_element': False,
            'reason': '元素库无可用定位候选',
        }

    ranked: List[Dict[str, Any]] = []
    for c in pool:
        item = dict(c)
        item['score'] = _score_candidate(
            item,
            error_kind=error_kind,
            demote_primary=demote_primary,
            element_meta=element_meta,
        )
        ranked.append(item)
    ranked.sort(key=lambda x: x.get('score', 0), reverse=True)

    # Prefer non-primary when demoting; else take top
    picked = None
    if demote_primary:
        for item in ranked:
            if item.get('source') != 'primary' and not item.get('is_primary'):
                picked = item
                break
    if picked is None:
        picked = ranked[0]

    # If still primary after demote and there is no better option, report weak confidence
    still_primary = picked.get('source') == 'primary' or picked.get('is_primary') is True
    if demote_primary and still_primary and len(ranked) == 1:
        return {
            'picked': {
                'strategy': picked['strategy'],
                'value': picked['value'],
                'source': picked.get('source'),
                'label': picked.get('label'),
                'score': picked.get('score'),
            },
            'ranked': ranked,
            'fix_type': None,
            'replace_primary': False,
            'auto_from_element': False,
            'reason': '元素库仅有失败主定位，无备用可升格',
        }

    source = (picked.get('source') or '').lower()
    if source == 'backup':
        fix_type = 'promote_backup'
        reason = '从元素库备用定位器自动升格'
    else:
        fix_type = 'update_locator'
        reason = f'结合元素库候选自动选定（source={source or "suggested"}）'

    return {
        'picked': {
            'strategy': picked['strategy'],
            'value': picked['value'],
            'source': picked.get('source'),
            'label': picked.get('label'),
            'score': picked.get('score'),
        },
        'ranked': ranked,
        'fix_type': fix_type,
        'replace_primary': True,
        'auto_from_element': True,
        'reason': reason,
        'element_meta': element_meta,
    }

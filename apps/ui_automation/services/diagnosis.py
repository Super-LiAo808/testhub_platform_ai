"""Failure diagnosis and semi-automatic fix proposals."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_llm():
    """Reuse browser_use_text AIModelConfig via LangChain ChatOpenAI."""
    import os
    from langchain_openai import ChatOpenAI
    from apps.requirement_analysis.models import AIModelConfig

    config = AIModelConfig.objects.filter(role='browser_use_text', is_active=True).first()
    if not config:
        config = AIModelConfig.objects.filter(is_active=True).first()
    if not config:
        raise ValueError('未配置可用的 AI 模型，请先在配置中心添加模型')

    return ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key or os.getenv('AUTH_TOKEN'),
        base_url=config.base_url or os.getenv('BASE_URL') or None,
        temperature=0,
    ), config


def _parse_match_count(text: str) -> Optional[int]:
    m = re.search(r'resolved to\s+(\d+)\s+elements?', text or '', re.I)
    if m:
        return int(m.group(1))
    return None


def _rule_based_diagnosis(logs: str, error_message: str = '') -> Dict[str, Any]:
    text = f'{logs or ""}\n{error_message or ""}'
    text_l = text.lower()

    # 必须先于 timing：Playwright strict 日志含 "waiting for locator"，易被误判为超时
    match_count = _parse_match_count(text)
    if (
        'strict mode' in text_l
        or match_count is not None
        or 'strict mode violation' in text_l
    ):
        return {
            'category': 'locator_break',
            'confidence': 0.9,
            'summary': (
                f'定位器匹配到多个元素（strict mode'
                f'{f"，共 {match_count} 个" if match_count else ""}），'
                '增大等待无效；需换成唯一选择器或指定 nth/可见元素。'
            ),
            'suggested_fix': {
                'type': 'update_locator',
                'replace_primary': True,
                'ambiguity': True,
                'match_count': match_count,
            },
            'subcategory': 'ambiguous_locator',
        }

    # 元素已命中但不可见：常见于 hover/click；增大 wait 无效
    if 'not visible' in text_l or 'element is not visible' in text_l:
        return {
            'category': 'script_bug',
            'confidence': 0.88,
            'summary': (
                '定位器已匹配到元素，但元素当前不可见（被遮挡、列表裁切或未入视口）。'
                '悬停/点击应先 scroll_into_view，必要时 force=True；单纯增大等待通常无效。'
            ),
            'suggested_fix': {
                'type': 'force_action',
                'force_action': True,
                'scroll_into_view': True,
            },
            'subcategory': 'not_visible',
        }

    if any(k in text_l for k in ('timeout', 'timed out', '等待超时')) or (
        'waiting for' in text_l and 'strict mode' not in text_l
    ):
        # 纯超时：排除已含 locator not found 的情况优先走定位（下面会再判）
        if not any(k in text_l for k in ('not found', 'no node', 'unable to locate', '定位失败')):
            return {
                'category': 'timing',
                'confidence': 0.7,
                'summary': '疑似等待/超时问题，可增大 wait_timeout 或增加显式等待。',
                'suggested_fix': {'type': 'increase_wait', 'wait_timeout': 15},
            }

    if any(k in text_l for k in ('not found', 'no node', 'unable to locate', '定位', 'locator')):
        return {
            'category': 'locator_break',
            'confidence': 0.75,
            'summary': '疑似元素定位失效（未找到），建议更新主定位器或补充 backup_locators。',
            'suggested_fix': {'type': 'update_locator', 'replace_primary': True},
        }
    if any(k in text_l for k in ('chrome', 'webdriver', 'browser', 'connection refused', 'chrome not')):
        return {
            'category': 'env',
            'confidence': 0.7,
            'summary': '疑似浏览器/驱动/环境问题。',
            'suggested_fix': {'type': 'check_environment'},
        }
    if any(k in text_l for k in ('assert', 'assertion', 'expected', '断言失败', '文案', '文案不符')):
        return {
            'category': 'product_bug',
            'confidence': 0.55,
            'summary': '断言失败，可能是产品行为/文案变更。',
            'suggested_fix': {'type': 'create_defect'},
        }
    return {
        'category': 'unknown',
        'confidence': 0.3,
        'summary': '无法高置信度分类，请人工查看日志与截图。',
        'suggested_fix': {},
    }


def _llm_diagnosis(logs: str, error_message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        llm, _ = _get_llm()
        prompt = f"""你是 UI 自动化失败诊断专家。根据日志判断失败类别，只返回 JSON：
{{
  "category": "locator_break|timing|env|flaky|script_bug|product_bug|unknown",
  "confidence": 0.0-1.0,
  "summary": "一句话中文摘要",
  "suggested_fix": {{
     "type": "update_locator|increase_wait|fix_step|create_defect|product_code_patch|none",
     "details": "...",
     "locator": {{"strategy":"css","value":"..."}},
     "replace_primary": true,
     "wait_timeout": 10,
     "diff": "可选的业务代码补丁unified diff"
  }}
}}

重要规则：
1. 若错误含 strict mode / resolved to N elements：属于定位歧义（多匹配），category=locator_break，
   type=update_locator 且 replace_primary=true；禁止建议 increase_wait。
2. 新 locator 必须尽可能唯一（可用 >> nth=0、>> visible=true、更具体 css/xpath/role+name）。
3. 若提供了 candidate_locators 或 dom_snippet，优先据此给出可用的 locator。
上下文: {json.dumps(context, ensure_ascii=False)[:3500]}
错误: {(error_message or '')[:1500]}
日志尾部:
{(logs or '')[-4000:]}
"""
        resp = llm.invoke(prompt)
        content = getattr(resp, 'content', None) or str(resp)
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return None
        data = json.loads(match.group(0))
        if 'category' not in data:
            return None
        data.setdefault('confidence', 0.5)
        data.setdefault('summary', '')
        data.setdefault('suggested_fix', {})
        return data
    except Exception as exc:
        logger.warning('LLM diagnosis failed: %s', exc)
        return None


def _normalize_locator(locator: Any) -> Optional[Dict[str, str]]:
    if not isinstance(locator, dict):
        return None
    value = (locator.get('value') or '').strip()
    if not value:
        return None
    strategy = (locator.get('strategy') or 'css').strip() or 'css'
    return {'strategy': strategy, 'value': value}


def _locator_key(locator: Dict[str, str]) -> Tuple[str, str]:
    return (str(locator.get('strategy') or '').lower(), str(locator.get('value') or ''))


def parse_step_logs(logs: str) -> List[Dict[str, Any]]:
    """Parse execution_logs which may be JSON step list or plain text."""
    text = (logs or '').strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get('steps'), list):
            return [x for x in data['steps'] if isinstance(x, dict)]
    except (TypeError, json.JSONDecodeError):
        pass
    return []


def extract_first_failed_step(logs: str) -> Optional[Dict[str, Any]]:
    for step in parse_step_logs(logs):
        success = step.get('success')
        if success is False or str(step.get('status', '')).lower() in ('failed', 'error'):
            return step
        if step.get('error') and success is not True:
            return step
    return None


def _candidates_from_element(element) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if not element:
        return candidates
    strategy_name = ''
    if getattr(element, 'locator_strategy', None):
        strategy_name = element.locator_strategy.name or 'css'
    primary = _normalize_locator({
        'strategy': strategy_name or 'css',
        'value': element.locator_value or '',
    })
    if primary:
        candidates.append({**primary, 'source': 'primary', 'label': '当前主定位器'})
    for backup in (element.backup_locators or []):
        loc = _normalize_locator(backup)
        if not loc:
            continue
        if any(_locator_key(c) == _locator_key(loc) for c in candidates):
            continue
        candidates.append({**loc, 'source': 'backup', 'label': '备用定位器'})
    return candidates


def _resolve_step_from_testcase(execution, failed_step: Optional[Dict[str, Any]]):
    from apps.ui_automation.models import TestCaseStep

    if not getattr(execution, 'test_case_id', None):
        return None

    qs = TestCaseStep.objects.filter(test_case_id=execution.test_case_id).select_related(
        'element', 'element__locator_strategy'
    )
    step_id = None
    step_number = None
    if failed_step:
        step_id = failed_step.get('step_id') or failed_step.get('id')
        step_number = failed_step.get('step_number')
        element_id = failed_step.get('element_id')
        if element_id and not step_id:
            step = qs.filter(element_id=element_id).order_by('step_number').first()
            if step:
                return step

    if step_id:
        step = qs.filter(id=step_id).first()
        if step:
            return step

    if step_number is not None:
        try:
            n = int(step_number)
        except (TypeError, ValueError):
            n = None
        if n is not None:
            step = qs.filter(step_number=n).first()
            if step:
                return step
            ordered = list(qs.order_by('step_number'))
            if 1 <= n <= len(ordered):
                return ordered[n - 1]
    return None


def resolve_testcase_failure_context(execution, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build rich context with element_id / step_id / candidate locators for a failed case run."""
    from apps.ui_automation.models import Element

    context: Dict[str, Any] = {
        'test_case_id': getattr(execution, 'test_case_id', None),
        'engine': getattr(execution, 'engine', None),
        'status': getattr(execution, 'status', None),
        'auto_enriched': True,
    }
    if extra:
        context.update({k: v for k, v in extra.items() if v is not None})

    failed_step = extract_first_failed_step(getattr(execution, 'execution_logs', '') or '')
    if failed_step:
        context['failed_step'] = {
            'step_number': failed_step.get('step_number'),
            'step_id': failed_step.get('step_id') or failed_step.get('id'),
            'action_type': failed_step.get('action_type'),
            'description': failed_step.get('description'),
            'error': failed_step.get('error'),
            'element_id': failed_step.get('element_id'),
            'element_name': failed_step.get('element_name'),
        }
        loc = _normalize_locator(failed_step.get('locator') or {})
        if loc:
            context['current_locator'] = loc
        backups = failed_step.get('backup_locators') or []
        if isinstance(backups, list) and backups:
            context['backup_locators'] = backups

    # Request overrides win
    element_id = context.get('element_id') or (failed_step or {}).get('element_id')
    step_id = context.get('step_id') or (failed_step or {}).get('step_id') or (failed_step or {}).get('id')

    step = _resolve_step_from_testcase(execution, failed_step)
    if step:
        step_id = step_id or step.id
        if step.element_id:
            element_id = element_id or step.element_id
        context['failed_step'] = {
            **(context.get('failed_step') or {}),
            'step_id': step.id,
            'step_number': step.step_number,
            'action_type': step.action_type,
            'description': step.description,
            'element_id': step.element_id,
            'element_name': step.element.name if step.element_id else None,
        }

    element = None
    if element_id:
        element = Element.objects.filter(id=element_id).select_related('locator_strategy').first()
    elif step and step.element_id:
        element = step.element

    if element:
        element_id = element.id
        context['element_id'] = element.id
        context['element_name'] = element.name
        context['wait_timeout'] = element.wait_timeout
        context['element_meta'] = {
            'page': getattr(element, 'page', '') or '',
            'discovery_source': getattr(element, 'discovery_source', '') or '',
            'is_unique': bool(getattr(element, 'is_unique', False)),
            'heal_count': int(getattr(element, 'heal_count', 0) or 0),
            'element_type': getattr(element, 'element_type', '') or '',
        }
        # Keep ORM ref for rank_and_pick (not serialized into evidence long-term)
        context['_element'] = element
        candidates = _candidates_from_element(element)
        context['candidate_locators'] = candidates
        if not context.get('current_locator') and candidates:
            primary = next((c for c in candidates if c.get('source') == 'primary'), candidates[0])
            context['current_locator'] = {
                'strategy': primary['strategy'],
                'value': primary['value'],
            }
        if not context.get('backup_locators'):
            context['backup_locators'] = [
                {'strategy': c['strategy'], 'value': c['value']}
                for c in candidates if c.get('source') == 'backup'
            ]

    if step_id:
        context['step_id'] = step_id
    if element_id:
        context['element_id'] = element_id
    return context


def resolve_ai_failure_context(execution_record, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Best-effort context for AI execution failures (selectors from action_trace)."""
    context: Dict[str, Any] = {
        'case_name': getattr(execution_record, 'case_name', None),
        'status': getattr(execution_record, 'status', None),
        'planned_tasks': getattr(execution_record, 'planned_tasks', None),
        'auto_enriched': True,
    }
    if extra:
        context.update({k: v for k, v in extra.items() if v is not None})

    candidates: List[Dict[str, Any]] = []
    actions = getattr(execution_record, 'action_trace', None) or []
    if isinstance(actions, list):
        for action in reversed(actions):
            if not isinstance(action, dict):
                continue
            status = str(action.get('status') or '').lower()
            # Prefer last interactive action; prefer ones marked failed
            element_meta = action.get('element') if isinstance(action.get('element'), dict) else {}
            selector = (
                action.get('selector')
                or action.get('css_selector')
                or action.get('xpath')
                or element_meta.get('selector')
            )
            strategy = 'xpath' if (isinstance(selector, str) and selector.strip().startswith('//')) else 'css'
            if action.get('xpath') and not action.get('selector'):
                selector = action.get('xpath')
                strategy = 'xpath'
            loc = _normalize_locator({'strategy': strategy, 'value': selector or ''})
            if not loc:
                continue
            entry = {**loc, 'source': 'action_trace', 'label': action.get('action') or action.get('type') or '轨迹定位'}
            if status in ('failed', 'error'):
                candidates.insert(0, entry)
                context['failed_action'] = {
                    'action': action.get('action') or action.get('type'),
                    'status': status,
                    'locator': loc,
                }
                break
            if not candidates:
                candidates.append(entry)

    # Deduplicate
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for c in candidates:
        key = _locator_key(c)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    if uniq:
        context['candidate_locators'] = uniq
        context['current_locator'] = {'strategy': uniq[0]['strategy'], 'value': uniq[0]['value']}
    return context


def _disambiguation_candidates(current_locator: Optional[Dict[str, Any]], match_count: Optional[int]) -> List[Dict[str, Any]]:
    """Generate nth / visible candidates for ambiguous primary locators."""
    loc = _normalize_locator(current_locator or {})
    if not loc:
        return []
    strategy = (loc.get('strategy') or 'css').lower()
    value = loc.get('value') or ''
    if strategy == 'id':
        base = value if value.startswith('#') else f'#{value}'
    elif strategy in ('css', 'css selector'):
        base = value
    else:
        # xpath/text 等先给可见过滤提示，具体仍靠人工/LLM
        return [{
            'strategy': strategy,
            'value': value,
            'source': 'suggested',
            'label': '请手工消歧（当前策略不支持自动 nth）',
        }]

    out: List[Dict[str, Any]] = []
    n = max(2, min(int(match_count or 4), 6))
    if 'visible=true' not in base:
        out.append({
            'strategy': 'css',
            'value': f'{base} >> visible=true',
            'source': 'suggested',
            'label': '仅可见元素',
        })
    for i in range(n):
        out.append({
            'strategy': 'css',
            'value': f'{base} >> nth={i}',
            'source': 'suggested',
            'label': f'第 {i + 1} 个匹配',
        })
    return out


def _auto_pick_locator_from_element(
    enriched: Dict[str, Any],
    context: Dict[str, Any],
    category: str = '',
) -> Dict[str, Any]:
    """Combine Element DB primary/backups (+ disambiguation) into an applyable locator."""
    from apps.ui_automation.services.heal_settings import get_project_heal_settings
    from apps.ui_automation.services.locator_resolve import rank_and_pick_from_element

    project = context.get('project')
    settings = get_project_heal_settings(project) if project is not None else {}
    if project is not None and not settings.get('auto_pick_from_element', True):
        return enriched

    # Timing-only fixes should not overwrite locator
    if enriched.get('type') == 'increase_wait' and category == 'timing' and not enriched.get('ambiguity'):
        return enriched

    error_kind = 'not_found'
    if enriched.get('ambiguity') or enriched.get('match_count') or category == 'locator_break':
        if enriched.get('ambiguity') or enriched.get('match_count'):
            error_kind = 'ambiguous'
        else:
            error_kind = 'not_found'
    elif category not in ('locator_break', 'script_bug', ''):
        return enriched

    element = context.get('_element')
    if element is None and enriched.get('element_id'):
        from apps.ui_automation.models import Element
        element = Element.objects.filter(id=enriched['element_id']).select_related('locator_strategy').first()

    extra = list(enriched.get('candidate_locators') or context.get('candidate_locators') or [])
    # Prefer any LLM locator already present as extra
    llm_loc = _normalize_locator(enriched.get('locator') or {})
    if llm_loc and not any(_locator_key(c) == _locator_key(llm_loc) for c in extra):
        extra.insert(0, {**llm_loc, 'source': 'llm', 'label': 'AI 建议定位器'})

    pick_result = rank_and_pick_from_element(
        element,
        error_kind=error_kind,
        match_count=enriched.get('match_count') or context.get('match_count'),
        current_locator=enriched.get('current_locator') or context.get('current_locator'),
        extra_candidates=extra,
    )
    ranked = pick_result.get('ranked') or []
    if ranked:
        # Merge ranked into candidate list (dedupe by key, keep highest score order)
        cands = list(enriched.get('candidate_locators') or [])
        existing = {_locator_key(c) for c in cands if isinstance(c, dict)}
        for item in ranked:
            key = _locator_key(item)
            if key not in existing:
                cands.append({
                    'strategy': item.get('strategy'),
                    'value': item.get('value'),
                    'source': item.get('source'),
                    'label': item.get('label') or item.get('source'),
                    'score': item.get('score'),
                })
                existing.add(key)
        enriched['candidate_locators'] = cands
        enriched['ranked_locators'] = [
            {
                'strategy': r.get('strategy'),
                'value': r.get('value'),
                'source': r.get('source'),
                'score': r.get('score'),
                'label': r.get('label'),
            }
            for r in ranked[:12]
        ]

    picked = pick_result.get('picked')
    if picked and pick_result.get('fix_type'):
        enriched['locator'] = {
            'strategy': picked['strategy'],
            'value': picked['value'],
        }
        enriched['locator_source'] = picked.get('source')
        enriched['locator_score'] = picked.get('score')
        enriched['type'] = pick_result['fix_type']
        enriched['replace_primary'] = bool(pick_result.get('replace_primary'))
        enriched['auto_from_element'] = bool(pick_result.get('auto_from_element'))
        enriched['pick_reason'] = pick_result.get('reason') or ''
        # Boost summary hint for UI
        enriched['details'] = (
            (enriched.get('details') or '')
            + (f" | {pick_result.get('reason')}" if pick_result.get('reason') else '')
        ).strip(' |')
    return enriched


def enrich_fix_payload(payload: Dict[str, Any], context: Dict[str, Any], category: str = '') -> Dict[str, Any]:
    """Merge element_id / step_id / locator candidates into a fix payload."""
    enriched = dict(payload or {})
    for key in ('element_id', 'step_id', 'wait_timeout', 'test_script_id', 'test_case_id'):
        if context.get(key) is not None and enriched.get(key) is None:
            enriched[key] = context[key]

    if context.get('candidate_locators') and not enriched.get('candidate_locators'):
        enriched['candidate_locators'] = list(context['candidate_locators'])

    # 多匹配：注入 nth/visible 候选，并默认替换主定位
    if enriched.get('ambiguity') or enriched.get('match_count'):
        enriched['replace_primary'] = True
        if enriched.get('type') in (None, '', 'increase_wait'):
            enriched['type'] = 'update_locator'
        disambig = _disambiguation_candidates(
            enriched.get('current_locator') or context.get('current_locator'),
            enriched.get('match_count') or context.get('match_count'),
        )
        if disambig:
            cands = list(enriched.get('candidate_locators') or [])
            existing = {_locator_key(c) for c in cands if isinstance(c, dict)}
            for d in disambig:
                if _locator_key(d) not in existing:
                    cands.append(d)
                    existing.add(_locator_key(d))
            enriched['candidate_locators'] = cands
            if not enriched.get('locator'):
                enriched['locator'] = _normalize_locator(disambig[0])

    llm_locator = _normalize_locator(enriched.get('locator') or {})
    if llm_locator:
        enriched['locator'] = llm_locator
        # Promote LLM locator into candidates head
        cands = list(enriched.get('candidate_locators') or [])
        if not any(_locator_key(c) == _locator_key(llm_locator) for c in cands):
            cands.insert(0, {**llm_locator, 'source': 'llm', 'label': 'AI 建议定位器'})
            enriched['candidate_locators'] = cands
    else:
        # Pick first suggested/llm/action_trace candidate for apply convenience
        for c in (enriched.get('candidate_locators') or context.get('candidate_locators') or []):
            if c.get('source') in ('llm', 'suggested', 'action_trace'):
                loc = _normalize_locator(c)
                if loc:
                    enriched['locator'] = loc
                    break

    if not enriched.get('type'):
        if category == 'timing':
            enriched['type'] = 'increase_wait'
        elif category in ('locator_break', 'script_bug'):
            # Prefer replace primary when we already plan to fix broken locator
            enriched['type'] = 'update_locator'

    if enriched.get('type') == 'update_locator' and enriched.get('replace_primary') is None:
        # 定位失效默认替换主定位，避免只追加 backup 导致验证仍撞坏定位
        enriched['replace_primary'] = True

    if enriched.get('type') == 'increase_wait' and not enriched.get('wait_timeout'):
        enriched['wait_timeout'] = context.get('wait_timeout') or 15

    if context.get('current_locator') and not enriched.get('current_locator'):
        enriched['current_locator'] = context['current_locator']

    # 不可见/强制操作：不要被元素库选点覆盖成 update_locator
    if enriched.get('type') in ('force_action', 'regenerate_script', 'increase_wait', 'check_environment', 'create_defect'):
        return enriched

    # 结合元素库主/备定位自动判定并填充可应用提案
    if category in ('locator_break', 'script_bug') or enriched.get('ambiguity'):
        enriched = _auto_pick_locator_from_element(enriched, context, category=category)

    return enriched


def diagnose_failure(
    *,
    execution_type: str,
    execution_id: int,
    project=None,
    logs: str = '',
    error_message: str = '',
    context: Optional[Dict[str, Any]] = None,
    created_by=None,
    use_llm: bool = True,
    auto_apply: bool = True,
):
    from apps.ui_automation.models import AutoFixProposal, FailureDiagnosis
    from apps.ui_automation.services.heal_settings import (
        get_project_heal_settings,
        should_auto_apply,
    )

    context = dict(context or {})
    if project is not None and context.get('project') is None:
        context['project'] = project
    result = None
    if use_llm:
        result = _llm_diagnosis(logs, error_message, context)
    if not result:
        result = _rule_based_diagnosis(logs, error_message)

    # Merge LLM locator into context candidates before creating proposals
    fix = dict(result.get('suggested_fix') or {})
    llm_locator = _normalize_locator(fix.get('locator') or {})
    if llm_locator:
        cands = list(context.get('candidate_locators') or [])
        if not any(_locator_key(c) == _locator_key(llm_locator) for c in cands):
            cands.insert(0, {**llm_locator, 'source': 'llm', 'label': 'AI 建议定位器'})
        context['candidate_locators'] = cands

    category = result.get('category') or 'unknown'
    fix = enrich_fix_payload(fix, context, category=category)

    summary = result.get('summary') or ''
    if fix.get('auto_from_element') and fix.get('pick_reason'):
        summary = f"{summary}（{fix['pick_reason']}）".strip()

    # Do not persist ORM object into JSON evidence
    evidence_context = {k: v for k, v in context.items() if k != '_element' and k != 'project'}

    diagnosis = FailureDiagnosis.objects.create(
        execution_type=execution_type,
        execution_id=execution_id,
        project=project,
        category=category,
        confidence=float(result.get('confidence') or 0),
        summary=summary,
        evidence={
            'logs_tail': (logs or '')[-3000:],
            'error_message': error_message or '',
            'context': evidence_context,
            'screenshot_refs': context.get('screenshot_refs') or [],
            'dom_snippet': (context.get('dom_snippet') or '')[:2000],
            'element_pick': {
                'auto_from_element': fix.get('auto_from_element'),
                'locator_source': fix.get('locator_source'),
                'locator_score': fix.get('locator_score'),
                'pick_reason': fix.get('pick_reason'),
                'ranked_locators': fix.get('ranked_locators') or [],
            } if fix.get('auto_from_element') or fix.get('ranked_locators') else None,
        },
        suggested_fix=fix,
        status='proposed',
        created_by=created_by,
    )

    proposals = []
    settings = get_project_heal_settings(project)

    if category in ('locator_break', 'script_bug', 'timing'):
        fix_title = f'测试侧修复建议: {category}'
        if fix.get('auto_from_element') and fix.get('type') == 'promote_backup':
            fix_title = '元素库备用定位升格'
        elif fix.get('auto_from_element') and fix.get('type') == 'update_locator':
            fix_title = '结合元素库自动选定定位器'
        elif fix.get('type') == 'force_action':
            fix_title = '启用强制操作（不可见元素）'
        elif fix.get('type') == 'regenerate_script':
            fix_title = '按最新 codegen 重生成独立脚本'
        proposals.append(AutoFixProposal.objects.create(
            diagnosis=diagnosis,
            target='test_asset',
            title=fix_title,
            description=diagnosis.summary,
            diff=json.dumps(fix, ensure_ascii=False, indent=2),
            patch_payload=fix,
            status='proposed',
            created_by=created_by,
        ))
        if category == 'locator_break' and fix.get('element_id') and fix.get('type') != 'increase_wait':
            # 多匹配（歧义）时增大等待无意义，不生成备选 wait 提案
            if not fix.get('ambiguity'):
                wait_payload = enrich_fix_payload(
                    {'type': 'increase_wait', 'wait_timeout': 15},
                    context,
                    category='timing',
                )
                proposals.append(AutoFixProposal.objects.create(
                    diagnosis=diagnosis,
                    target='test_asset',
                    title='备选: 增大等待超时',
                    description='定位失效时也可先增大 wait_timeout 缓解时序问题。',
                    diff=json.dumps(wait_payload, ensure_ascii=False, indent=2),
                    patch_payload=wait_payload,
                    status='proposed',
                    created_by=created_by,
                ))

    if category == 'product_bug' or fix.get('type') in ('create_defect', 'product_code_patch'):
        proposals.append(AutoFixProposal.objects.create(
            diagnosis=diagnosis,
            target='product_code',
            title='产品缺陷 / 代码补丁提案',
            description=diagnosis.summary,
            diff=fix.get('diff') or '',
            patch_payload=fix,
            status='proposed',
            created_by=created_by,
        ))

    # auto_low_risk: apply whitelisted proposals then verify
    if auto_apply and settings.get('mode') == 'auto_low_risk':
        from apps.ui_automation.services.heal_verify import verify_proposal_by_rerun
        # Prefer element-DB backed locator fixes first
        ordered = sorted(
            proposals,
            key=lambda p: (
                0 if (p.patch_payload or {}).get('type') == 'regenerate_script' else 1,
                0 if (p.patch_payload or {}).get('type') == 'force_action' else 1,
                0 if (p.patch_payload or {}).get('auto_from_element') else 1,
                0 if (p.patch_payload or {}).get('type') == 'promote_backup' else 1,
            ),
        )
        for proposal in ordered:
            if proposal.target != 'test_asset':
                continue
            payload = proposal.patch_payload or {}
            fix_type = payload.get('type')
            if not should_auto_apply(project, fix_type, payload):
                continue
            if not payload.get('element_id') and fix_type not in ('increase_wait', 'regenerate_script'):
                continue
            try:
                apply_test_asset_fix(proposal, applied_by=created_by)
                if settings.get('verify_rerun', True):
                    verify_proposal_by_rerun(proposal, user=created_by)
                break  # apply at most one auto fix per diagnosis
            except Exception as exc:
                logger.warning('auto_low_risk apply failed: %s', exc)

    return diagnosis, proposals


def _snapshot_element(el) -> Dict[str, Any]:
    return {
        'element_id': el.id,
        'locator_strategy': el.locator_strategy.name if el.locator_strategy_id else 'css',
        'locator_value': el.locator_value or '',
        'backup_locators': list(el.backup_locators or []),
        'wait_timeout': el.wait_timeout,
    }


def _snapshot_step(step) -> Dict[str, Any]:
    return {
        'step_id': step.id,
        'wait_time': step.wait_time,
    }


def apply_test_asset_fix(proposal, applied_by=None, *, run_verify: bool = False) -> Dict[str, Any]:
    """Apply locator/wait fixes to Element / TestCaseStep. Never touches product code."""
    from apps.ui_automation.models import Element, TestCaseStep
    from apps.ui_automation.services.heal_settings import can_write_test_assets

    if proposal.target != 'test_asset':
        raise ValueError('仅测试资产提案可直接应用')
    if proposal.status == 'applied':
        return {'message': '已应用过', 'proposal_id': proposal.id}
    if proposal.status == 'rolled_back':
        raise ValueError('提案已回滚，请重新诊断')

    project = proposal.diagnosis.project if proposal.diagnosis_id else None
    if not can_write_test_assets(project):
        raise ValueError('项目策略为 diagnose_only，禁止写入测试资产')

    payload = dict(proposal.patch_payload or {})
    evidence_ctx = {}
    if proposal.diagnosis_id and isinstance(getattr(proposal.diagnosis, 'evidence', None), dict):
        evidence_ctx = (proposal.diagnosis.evidence or {}).get('context') or {}
    payload = enrich_fix_payload(payload, evidence_ctx, category=getattr(proposal.diagnosis, 'category', ''))

    if not _normalize_locator(payload.get('locator') or {}):
        for c in payload.get('candidate_locators') or []:
            if c.get('source') in ('llm', 'suggested', 'action_trace', 'backup'):
                loc = _normalize_locator(c)
                if loc:
                    payload['locator'] = loc
                    break

    fix_type = payload.get('type')
    applied = []
    before_snapshot: Dict[str, Any] = {'elements': [], 'steps': []}

    element_id = payload.get('element_id')
    step_id = payload.get('step_id')

    if fix_type == 'increase_wait':
        timeout = int(payload.get('wait_timeout') or 15)
        if element_id:
            el = Element.objects.filter(id=element_id).select_related('locator_strategy').first()
            if el:
                before_snapshot['elements'].append(_snapshot_element(el))
                el.wait_timeout = timeout
                el.last_healed_at = timezone.now()
                el.heal_count = (el.heal_count or 0) + 1
                el.save(update_fields=['wait_timeout', 'last_healed_at', 'heal_count', 'updated_at'])
                applied.append(f'element#{el.id}.wait_timeout={timeout}')
        if step_id:
            step = TestCaseStep.objects.filter(id=step_id).first()
            if step:
                before_snapshot['steps'].append(_snapshot_step(step))
                step.wait_time = timeout * 1000
                step.save(update_fields=['wait_time'])
                applied.append(f'step#{step.id}.wait_time={timeout * 1000}')
        if not applied:
            raise ValueError('缺少 element_id / step_id，无法应用等待修复')

    elif fix_type == 'force_action':
        if not element_id:
            raise ValueError('缺少 element_id，无法启用强制操作')
        el = Element.objects.filter(id=element_id).select_related('locator_strategy').first()
        if not el:
            raise ValueError(f'元素 #{element_id} 不存在')
        before_snapshot['elements'].append({
            **_snapshot_element(el),
            'force_action': bool(el.force_action),
        })
        el.force_action = True
        el.last_healed_at = timezone.now()
        el.heal_count = (el.heal_count or 0) + 1
        # CSS 定位优先挂 visible=true，避免命中隐藏幽灵节点
        strategy_name = el.locator_strategy.name if el.locator_strategy_id else 'css'
        val = el.locator_value or ''
        if strategy_name.lower() in ('css', 'css selector') and val and 'visible=true' not in val.lower():
            backups = list(el.backup_locators or [])
            old = {'strategy': strategy_name, 'value': val}
            if old not in backups:
                backups.insert(0, old)
            el.locator_value = f'{val} >> visible=true'
            el.backup_locators = backups
            el.save(update_fields=[
                'force_action', 'locator_value', 'backup_locators',
                'last_healed_at', 'heal_count', 'updated_at',
            ])
            applied.append(f'element#{el.id}.locator += >> visible=true')
        else:
            el.save(update_fields=['force_action', 'last_healed_at', 'heal_count', 'updated_at'])
        applied.append(f'element#{el.id}.force_action=True')
        # 若诊断来自独立脚本且关联用例，同步重生成脚本悬停/点击写法
        script_id = payload.get('test_script_id') or evidence_ctx.get('test_script_id')
        case_id = payload.get('test_case_id') or evidence_ctx.get('test_case_id')
        if script_id or case_id:
            try:
                from apps.ui_automation.models import TestCase, TestScript
                from apps.ui_automation.services.codegen import export_testcase_to_script
                case = None
                if case_id:
                    case = TestCase.objects.filter(id=case_id).first()
                elif script_id:
                    script = TestScript.objects.filter(id=script_id).select_related('source_test_case').first()
                    case = script.source_test_case if script else None
                if case:
                    export_testcase_to_script(case, engine='playwright', force=True)
                    applied.append(f'regenerated script for case#{case.id}')
            except Exception as exc:
                logger.warning('force_action regenerate script failed: %s', exc)

    elif fix_type == 'regenerate_script':
        from apps.ui_automation.models import TestCase, TestScript
        from apps.ui_automation.services.codegen import export_testcase_to_script
        case_id = payload.get('test_case_id') or evidence_ctx.get('test_case_id')
        script_id = payload.get('test_script_id') or evidence_ctx.get('test_script_id')
        case = None
        if case_id:
            case = TestCase.objects.filter(id=case_id).first()
        elif script_id:
            script = TestScript.objects.filter(id=script_id).select_related('source_test_case').first()
            case = script.source_test_case if script else None
        if not case:
            raise ValueError('缺少关联用例，无法重生成脚本')
        before_snapshot['script'] = {'test_case_id': case.id, 'test_script_id': script_id}
        script, meta = export_testcase_to_script(case, engine='playwright', force=True)
        applied.append(f'regenerated script#{script.id} ({meta})')

    elif fix_type in ('update_locator', 'add_backup_locator', 'promote_backup'):
        locator = _normalize_locator(payload.get('locator') or {})
        if not element_id:
            raise ValueError('缺少 element_id，无法应用定位修复')
        if not locator:
            raise ValueError('缺少可用 locator（可从 candidate_locators 选择后重试）')
        el = Element.objects.filter(id=element_id).select_related('locator_strategy').first()
        if not el:
            raise ValueError(f'元素 #{element_id} 不存在')
        before_snapshot['elements'].append(_snapshot_element(el))
        backups = list(el.backup_locators or [])
        entry = {
            'strategy': locator['strategy'],
            'value': locator['value'],
        }
        replace_primary = bool(payload.get('replace_primary')) or fix_type == 'promote_backup'
        if fix_type in ('update_locator', 'promote_backup') and replace_primary:
            if el.locator_strategy_id and el.locator_value:
                old = {
                    'strategy': el.locator_strategy.name,
                    'value': el.locator_value,
                }
                if old not in backups and _locator_key(old) != _locator_key(entry):
                    backups.insert(0, old)
            from apps.ui_automation.services.compiler import _get_or_create_strategy
            el.locator_strategy = _get_or_create_strategy(entry['strategy'])
            el.locator_value = entry['value']
            # remove promoted entry from backups if present
            backups = [b for b in backups if _locator_key(b) != _locator_key(entry)]
        else:
            if entry not in backups and not (
                el.locator_value == entry['value']
                and (el.locator_strategy.name if el.locator_strategy_id else '') == entry['strategy']
            ):
                backups.append(entry)
        el.backup_locators = backups
        el.last_healed_at = timezone.now()
        el.heal_count = (el.heal_count or 0) + 1
        el.save()
        applied.append(f'element#{el.id} locator updated ({fix_type})')
    else:
        raise ValueError(f'不支持的修复类型: {fix_type or "(空)"}')

    proposal.patch_payload = payload
    proposal.before_snapshot = before_snapshot
    proposal.status = 'applied'
    proposal.applied_at = timezone.now()
    proposal.reviewed_by = applied_by
    proposal.reviewed_at = timezone.now()
    proposal.verify_status = 'pending'
    proposal.save(update_fields=[
        'patch_payload', 'before_snapshot', 'status', 'applied_at',
        'reviewed_by', 'reviewed_at', 'verify_status', 'updated_at',
    ])
    proposal.diagnosis.status = 'applied'
    proposal.diagnosis.save(update_fields=['status', 'updated_at'])

    result = {
        'applied': applied,
        'proposal_id': proposal.id,
        'patch_payload': payload,
        'before_snapshot': before_snapshot,
        'verify_status': proposal.verify_status,
    }
    if run_verify:
        from apps.ui_automation.services.heal_verify import verify_proposal_by_rerun
        from apps.ui_automation.services.heal_settings import get_project_heal_settings
        if get_project_heal_settings(project).get('verify_rerun', True):
            result['verification'] = verify_proposal_by_rerun(proposal, user=applied_by)
            result['verify_status'] = proposal.verify_status
    return result


def rollback_test_asset_fix(proposal, rolled_back_by=None) -> Dict[str, Any]:
    """Restore Element/TestCaseStep from before_snapshot."""
    from apps.ui_automation.models import Element, TestCaseStep
    from apps.ui_automation.services.compiler import _get_or_create_strategy

    if proposal.target != 'test_asset':
        raise ValueError('仅测试资产提案可回滚')
    if proposal.status not in ('applied',):
        raise ValueError('仅已应用的提案可回滚')
    snapshot = proposal.before_snapshot or {}
    restored = []
    for item in snapshot.get('elements') or []:
        el = Element.objects.filter(id=item.get('element_id')).first()
        if not el:
            continue
        el.locator_strategy = _get_or_create_strategy(item.get('locator_strategy') or 'css')
        el.locator_value = item.get('locator_value') or ''
        el.backup_locators = item.get('backup_locators') or []
        if item.get('wait_timeout') is not None:
            el.wait_timeout = item['wait_timeout']
        el.save()
        restored.append(f'element#{el.id}')
    for item in snapshot.get('steps') or []:
        step = TestCaseStep.objects.filter(id=item.get('step_id')).first()
        if not step:
            continue
        if item.get('wait_time') is not None:
            step.wait_time = item['wait_time']
            step.save(update_fields=['wait_time'])
            restored.append(f'step#{step.id}')
    proposal.status = 'rolled_back'
    proposal.reviewed_by = rolled_back_by or proposal.reviewed_by
    proposal.reviewed_at = timezone.now()
    proposal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
    if proposal.diagnosis_id:
        proposal.diagnosis.status = 'proposed'
        proposal.diagnosis.save(update_fields=['status', 'updated_at'])
    return {'restored': restored, 'proposal_id': proposal.id}


def create_promote_backup_proposal(
    *,
    project,
    element,
    locator: Dict[str, str],
    execution_type: str = 'testcase',
    execution_id: int = 0,
    created_by=None,
    auto_apply: bool = False,
):
    """Create a promote_backup proposal after runtime backup hit."""
    from apps.ui_automation.models import AutoFixProposal, FailureDiagnosis
    from apps.ui_automation.services.heal_settings import get_project_heal_settings

    loc = _normalize_locator(locator)
    if not loc or not element:
        return None, None
    diagnosis = FailureDiagnosis.objects.create(
        execution_type=execution_type,
        execution_id=execution_id or 0,
        project=project,
        category='locator_break',
        confidence=0.8,
        summary=f'运行时备用定位命中，建议升格为主定位: {loc["strategy"]}={loc["value"]}',
        evidence={'context': {'element_id': element.id, 'locator_used': loc, 'used_backup': True}},
        suggested_fix={'type': 'promote_backup', 'locator': loc, 'element_id': element.id, 'replace_primary': True},
        status='proposed',
        created_by=created_by,
    )
    payload = {
        'type': 'promote_backup',
        'locator': loc,
        'element_id': element.id,
        'replace_primary': True,
    }
    proposal = AutoFixProposal.objects.create(
        diagnosis=diagnosis,
        target='test_asset',
        title='升格备用定位器为主定位',
        description=diagnosis.summary,
        diff=json.dumps(payload, ensure_ascii=False, indent=2),
        patch_payload=payload,
        status='proposed',
        created_by=created_by,
    )
    settings = get_project_heal_settings(project)
    if auto_apply or settings.get('auto_promote_backup'):
        try:
            apply_test_asset_fix(proposal, applied_by=created_by, run_verify=True)
        except Exception as exc:
            logger.warning('auto promote backup failed: %s', exc)
    return diagnosis, proposal


def create_defect_from_diagnosis(diagnosis, *, user, project_id: Optional[int] = None) -> Dict[str, Any]:
    """Create apps.defects.Defect from diagnosis. Requires projects.Project id."""
    from apps.defects.models import Defect
    from apps.projects.models import Project

    if not project_id:
        if diagnosis.project_id:
            matched = Project.objects.filter(name=diagnosis.project.name).first()
            if matched:
                project_id = matched.id
    if not project_id:
        raise ValueError('创建缺陷需要 projects.Project 的 project_id（与 UI 项目不同）')

    project = Project.objects.get(id=project_id)
    defect = Defect.objects.create(
        title=(diagnosis.summary or f'UI自动化失败诊断#{diagnosis.id}')[:300],
        description=diagnosis.summary,
        reproduce_steps=json.dumps(diagnosis.evidence, ensure_ascii=False)[:5000],
        actual_result=(diagnosis.evidence or {}).get('error_message') or '',
        expected_result='用例通过',
        project=project,
        severity='major',
        priority='p2',
        defect_type='ui',
        source='ui_automation',
        reporter=user,
    )
    for proposal in diagnosis.fix_proposals.filter(target='product_code'):
        proposal.defect_id = defect.id
        proposal.save(update_fields=['defect_id', 'updated_at'])
    return {'defect_id': defect.id, 'code': defect.code}


def has_diagnosis(execution_type: str, execution_id: int) -> bool:
    from apps.ui_automation.models import FailureDiagnosis
    return FailureDiagnosis.objects.filter(
        execution_type=execution_type,
        execution_id=execution_id,
    ).exists()


def auto_diagnose_testcase_execution(execution, *, created_by=None, use_llm: bool = False):
    """Auto-run after failed case execution. Default rule-based for speed."""
    from apps.ui_automation.services.heal_settings import is_auto_diagnose_enabled

    if getattr(execution, 'status', None) not in ('failed', 'error'):
        return None, []
    if not is_auto_diagnose_enabled(getattr(execution, 'project', None)):
        return None, []
    if has_diagnosis('testcase', execution.id):
        return None, []
    try:
        context = resolve_testcase_failure_context(execution)
        # attach screenshot refs (no base64)
        screenshots = getattr(execution, 'screenshots', None) or []
        refs = []
        for s in screenshots[:3]:
            if isinstance(s, dict):
                url = s.get('url') or s.get('path') or ''
                if url and not str(url).startswith('data:'):
                    refs.append({'url': url, 'step_number': s.get('step_number')})
                elif url and str(url).startswith('data:'):
                    refs.append({'embedded': True, 'step_number': s.get('step_number')})
        if refs:
            context['screenshot_refs'] = refs
        failed = extract_first_failed_step(getattr(execution, 'execution_logs', '') or '')
        if failed and failed.get('dom_snippet'):
            context['dom_snippet'] = str(failed.get('dom_snippet'))[:2000]
        return diagnose_failure(
            execution_type='testcase',
            execution_id=execution.id,
            project=getattr(execution, 'project', None),
            logs=getattr(execution, 'execution_logs', '') or '',
            error_message=getattr(execution, 'error_message', '') or '',
            context=context,
            created_by=created_by or getattr(execution, 'created_by', None),
            use_llm=use_llm,
        )
    except Exception:
        logger.exception('auto_diagnose_testcase_execution failed for #%s', getattr(execution, 'id', None))
        return None, []


def auto_diagnose_ai_execution(execution_record, *, created_by=None, use_llm: bool = False):
    """Auto-run after failed AI execution. Default rule-based for speed."""
    from apps.ui_automation.services.heal_settings import is_auto_diagnose_enabled

    if getattr(execution_record, 'status', None) != 'failed':
        return None, []
    if not is_auto_diagnose_enabled(getattr(execution_record, 'project', None)):
        return None, []
    if has_diagnosis('ai', execution_record.id):
        return None, []
    try:
        context = resolve_ai_failure_context(execution_record)
        logs = getattr(execution_record, 'logs', '') or ''
        error_message = ''
        for line in reversed(logs.splitlines()):
            if '失败' in line or 'error' in line.lower() or 'fail' in line.lower():
                error_message = line.strip()
                break
        return diagnose_failure(
            execution_type='ai',
            execution_id=execution_record.id,
            project=getattr(execution_record, 'project', None),
            logs=logs,
            error_message=error_message,
            context=context,
            created_by=created_by or getattr(execution_record, 'executed_by', None),
            use_llm=use_llm,
        )
    except Exception:
        logger.exception('auto_diagnose_ai_execution failed for #%s', getattr(execution_record, 'id', None))
        return None, []


def _parse_locator_from_playwright_error(text: str) -> Optional[Dict[str, str]]:
    """Extract locator("...") / get_by_* from Playwright error logs."""
    if not text:
        return None
    m = re.search(r'locator\([\'"](.+?)[\'"]\)', text)
    if m:
        return {'strategy': 'css', 'value': m.group(1)}
    m = re.search(r'waiting for locator\([\'"](.+?)[\'"]\)', text, re.I)
    if m:
        return {'strategy': 'css', 'value': m.group(1)}
    return None


def resolve_script_failure_context(execution, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build context for independent TestScript run failures (TestExecution)."""
    from apps.ui_automation.models import Element, TestCaseStep

    context: Dict[str, Any] = {
        'test_script_id': getattr(execution, 'test_script_id', None),
        'engine': getattr(execution, 'engine', None),
        'status': getattr(execution, 'status', None),
        'auto_enriched': True,
    }
    if extra:
        context.update({k: v for k, v in extra.items() if v is not None})

    logs = ''
    result = getattr(execution, 'result_data', None) or {}
    if isinstance(result, dict):
        logs = result.get('logs') or ''
    err = getattr(execution, 'error_message', '') or ''
    blob = f'{logs}\n{err}'

    loc = _parse_locator_from_playwright_error(blob)
    if loc:
        context['current_locator'] = loc

    script = getattr(execution, 'test_script', None)
    if script is None and getattr(execution, 'test_script_id', None):
        from apps.ui_automation.models import TestScript
        script = TestScript.objects.filter(id=execution.test_script_id).select_related(
            'source_test_case', 'project'
        ).first()

    case = getattr(script, 'source_test_case', None) if script else None
    if case:
        context['test_case_id'] = case.id
        context['test_case_name'] = case.name
        # Match failed locator to a step element
        element = None
        if loc:
            steps = TestCaseStep.objects.filter(test_case_id=case.id).select_related(
                'element', 'element__locator_strategy'
            )
            for step in steps:
                el = step.element
                if not el:
                    continue
                if (el.locator_value or '') == loc.get('value'):
                    element = el
                    context['step_id'] = step.id
                    context['element_id'] = el.id
                    context['element_name'] = el.name
                    break
                # partial match (nth-of-type selectors may be stored truncated)
                if loc.get('value') and el.locator_value and (
                    loc['value'] in (el.locator_value or '')
                    or (el.locator_value or '') in loc['value']
                ):
                    element = el
                    context['step_id'] = step.id
                    context['element_id'] = el.id
                    context['element_name'] = el.name
                    break
        if element is None and loc:
            element = Element.objects.filter(
                project_id=case.project_id,
                locator_value=loc.get('value'),
            ).select_related('locator_strategy').first()
            if element:
                context['element_id'] = element.id
                context['element_name'] = element.name
        if element:
            context['_element'] = element
            context['wait_timeout'] = element.wait_timeout
            context['candidate_locators'] = _candidates_from_element(element)
            context['backup_locators'] = [
                {'strategy': c['strategy'], 'value': c['value']}
                for c in context['candidate_locators'] if c.get('source') == 'backup'
            ]

    return context


def auto_diagnose_script_execution(execution, *, created_by=None, use_llm: bool = False):
    """Auto-run after failed independent script TestExecution."""
    from apps.ui_automation.services.heal_settings import is_auto_diagnose_enabled

    status = (getattr(execution, 'status', None) or '').upper()
    if status != 'FAILED':
        return None, []
    if not getattr(execution, 'test_script_id', None):
        return None, []
    if not is_auto_diagnose_enabled(getattr(execution, 'project', None)):
        return None, []
    if has_diagnosis('script', execution.id):
        return None, []
    try:
        context = resolve_script_failure_context(execution)
        result = getattr(execution, 'result_data', None) or {}
        logs = result.get('logs') if isinstance(result, dict) else ''
        error_message = getattr(execution, 'error_message', '') or ''
        diagnosis, proposals = diagnose_failure(
            execution_type='script',
            execution_id=execution.id,
            project=getattr(execution, 'project', None),
            logs=logs or '',
            error_message=error_message,
            context=context,
            created_by=created_by or getattr(execution, 'executed_by', None),
            use_llm=use_llm,
        )
        # 不可见 + 关联用例：额外提案「重生成脚本」（含 scroll + force hover）
        fix = (diagnosis.suggested_fix if diagnosis else None) or {}
        if (
            diagnosis
            and fix.get('type') == 'force_action'
            and context.get('test_case_id')
        ):
            from apps.ui_automation.models import AutoFixProposal
            regen = {
                'type': 'regenerate_script',
                'test_case_id': context.get('test_case_id'),
                'test_script_id': context.get('test_script_id'),
                'element_id': context.get('element_id'),
            }
            proposals.append(AutoFixProposal.objects.create(
                diagnosis=diagnosis,
                target='test_asset',
                title='按最新 codegen 重生成独立脚本',
                description='将悬停改为 scroll_into_view + hover(force=True)，修复「元素存在但不可见」类失败。',
                diff=json.dumps(regen, ensure_ascii=False, indent=2),
                patch_payload=regen,
                status='proposed',
                created_by=created_by or getattr(execution, 'executed_by', None),
            ))
        return diagnosis, proposals
    except Exception:
        logger.exception('auto_diagnose_script_execution failed for #%s', getattr(execution, 'id', None))
        return None, []


def enrich_step_result_meta(step_result: Dict[str, Any], step_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Attach element_id / locator meta onto a step result dict (mutates and returns)."""
    step_data = step_data or {}
    if step_data.get('id') and not step_result.get('step_id'):
        step_result['step_id'] = step_data['id']
    element = step_data.get('element') if isinstance(step_data.get('element'), dict) else None
    element_data = step_data.get('element_data') if isinstance(step_data.get('element_data'), dict) else None
    meta = element or element_data
    if meta:
        if meta.get('id') and not step_result.get('element_id'):
            step_result['element_id'] = meta['id']
        if meta.get('name') and not step_result.get('element_name'):
            step_result['element_name'] = meta['name']
        if not step_result.get('locator') and meta.get('locator_value'):
            step_result['locator'] = {
                'strategy': meta.get('locator_strategy') or 'css',
                'value': meta['locator_value'],
            }
        if meta.get('backup_locators') is not None and 'backup_locators' not in step_result:
            step_result['backup_locators'] = meta.get('backup_locators') or []
    return step_result

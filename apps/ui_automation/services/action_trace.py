"""Extract and normalize browser-use / recording action traces."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = re.compile(
    r'(password|passwd|pwd|token|secret|api[_-]?key|authorization|credential)',
    re.I,
)


def _safe_str(value: Any, limit: int = 500) -> str:
    if value is None:
        return ''
    text = value if isinstance(value, str) else str(value)
    return text[:limit]


def _dictify(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _dictify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_dictify(v) for v in obj]
    if hasattr(obj, 'model_dump'):
        try:
            return _dictify(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, 'dict'):
        try:
            return _dictify(obj.dict())
        except Exception:
            pass
    if hasattr(obj, '__dict__'):
        data = {}
        for key, value in vars(obj).items():
            if key.startswith('_'):
                continue
            if callable(value):
                continue
            try:
                data[key] = _dictify(value)
            except Exception:
                data[key] = _safe_str(value)
        return data
    return _safe_str(obj)


def _extract_locators_from_element(element: Any) -> List[Dict[str, str]]:
    """Promote interacted_element attrs into stable locator candidates."""
    locators: List[Dict[str, str]] = []
    data = _dictify(element) or {}
    if not isinstance(data, dict):
        return locators

    attrs = data.get('attributes') or data.get('attrs') or {}
    if isinstance(attrs, dict):
        test_id = attrs.get('data-testid') or attrs.get('data-test-id') or attrs.get('data-qa')
        if test_id:
            locators.append({'strategy': 'test-id', 'value': str(test_id)})
        if attrs.get('id'):
            locators.append({'strategy': 'id', 'value': str(attrs['id'])})
        if attrs.get('name'):
            locators.append({'strategy': 'name', 'value': str(attrs['name'])})
        if attrs.get('placeholder'):
            locators.append({'strategy': 'placeholder', 'value': str(attrs['placeholder'])})
        if attrs.get('aria-label'):
            locators.append({'strategy': 'label', 'value': str(attrs['aria-label'])})
        if attrs.get('title'):
            locators.append({'strategy': 'title', 'value': str(attrs['title'])})
        if attrs.get('role') and (attrs.get('name') or attrs.get('aria-label')):
            locators.append({
                'strategy': 'role',
                'value': f"{attrs.get('role')}|{attrs.get('name') or attrs.get('aria-label')}",
            })

    for key in ('css_selector', 'css', 'selector'):
        if data.get(key):
            locators.append({'strategy': 'css', 'value': str(data[key])})
            break

    for key in ('xpath', 'x_path'):
        if data.get(key):
            locators.append({'strategy': 'xpath', 'value': str(data[key])})
            break

    text = data.get('text') or data.get('inner_text') or data.get('node_value')
    if text and isinstance(text, str) and 0 < len(text.strip()) <= 80:
        locators.append({'strategy': 'text', 'value': text.strip()})

    # Deduplicate
    seen = set()
    unique = []
    for loc in locators:
        key = (loc['strategy'], loc['value'])
        if key in seen or not loc['value']:
            continue
        seen.add(key)
        unique.append(loc)
    return unique


def _parse_action_item(action: Any) -> Optional[Dict[str, Any]]:
    data = _dictify(action)
    if data is None:
        return None

    action_name = None
    params: Dict[str, Any] = {}

    if isinstance(data, dict):
        # pydantic ActionModel often looks like {click_element: {...}} or {go_to_url: {...}}
        if len(data) == 1:
            action_name = next(iter(data.keys()))
            params = data[action_name] if isinstance(data[action_name], dict) else {'value': data[action_name]}
        else:
            action_name = data.get('action') or data.get('name') or data.get('type')
            params = data.get('params') or {k: v for k, v in data.items() if k not in ('action', 'name', 'type')}
    else:
        action_name = _safe_str(data)
        params = {}

    if not action_name:
        return None

    mapped = map_browser_use_action(str(action_name), params)
    return mapped


def map_browser_use_action(action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Map browser-use / recording action names to TestCaseStep action_type."""
    name = action_name.lower().replace('-', '_')
    params = params or {}

    text_value = params.get('text') or params.get('value') or params.get('input_value') or ''
    url = params.get('url') or params.get('href') or ''
    index = params.get('index')

    if name in ('go_to_url', 'navigate', 'open_url', 'goto'):
        return {
            'action_type': 'navigate',
            'description': f'打开 {url}' if url else '打开页面',
            'input_value': _safe_str(url),
            'needs_element': False,
            'raw_action': action_name,
            'params': params,
        }

    if name in ('click_element', 'click_element_by_index', 'click', 'left_click'):
        return {
            'action_type': 'click',
            'description': params.get('description') or f'点击元素 index={index}' if index is not None else '点击元素',
            'input_value': '',
            'needs_element': True,
            'element_index': index,
            'raw_action': action_name,
            'params': params,
        }

    if name in ('input_text', 'input', 'fill', 'type_text', 'send_keys'):
        return {
            'action_type': 'fill',
            'description': params.get('description') or '输入文本',
            'input_value': _safe_str(text_value),
            'needs_element': True,
            'element_index': index,
            'raw_action': action_name,
            'params': params,
            'sensitive': bool(SENSITIVE_KEYS.search(_safe_str(params))),
        }

    if name in ('scroll', 'scroll_down', 'scroll_up'):
        return {
            'action_type': 'scroll',
            'description': '滚动页面',
            'input_value': _safe_str(params.get('amount') or params.get('direction') or ''),
            'needs_element': False,
            'raw_action': action_name,
            'params': params,
        }

    if name in ('wait', 'wait_for'):
        return {
            'action_type': 'wait',
            'description': '等待',
            'input_value': '',
            'wait_time': int(float(params.get('seconds') or params.get('time') or 1) * 1000),
            'needs_element': False,
            'raw_action': action_name,
            'params': params,
        }

    if name in ('switch_tab', 'switch'):
        return {
            'action_type': 'switchTab',
            'description': '切换标签页',
            'input_value': _safe_str(params.get('page_id') or params.get('tab_id') or ''),
            'needs_element': False,
            'raw_action': action_name,
            'params': params,
        }

    if name in ('done', 'mark_task_complete', 'mark_task_failed', 'mark_task_skipped', 'update_task_status'):
        return {
            'action_type': 'meta',
            'description': f'元动作 {action_name}',
            'input_value': '',
            'needs_element': False,
            'skip': True,
            'raw_action': action_name,
            'params': params,
        }

    return {
        'action_type': 'click' if 'click' in name else 'wait',
        'description': f'动作 {action_name}',
        'input_value': _safe_str(text_value or url),
        'needs_element': 'element' in name or index is not None,
        'element_index': index,
        'raw_action': action_name,
        'params': params,
    }


def _rank_locators(locators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer stable strategies as primary."""
    priority = {
        'test-id': 0,
        'testid': 0,
        'id': 1,
        'name': 2,
        'label': 3,
        'placeholder': 4,
        'role': 5,
        'title': 6,
        'css': 7,
        'xpath': 8,
        'text': 9,
    }
    ranked = sorted(
        [l for l in (locators or []) if isinstance(l, dict) and l.get('value')],
        key=lambda l: priority.get(str(l.get('strategy') or '').lower(), 50),
    )
    return ranked


def _is_unstable_only(locators: List[Dict[str, Any]]) -> bool:
    if not locators:
        return True
    for loc in locators:
        if loc.get('unstable'):
            continue
        val = str(loc.get('value') or '')
        if 'nth=' in val and val.strip().startswith('body'):
            continue
        return False
    return True


def _bind_locators_to_actions(actions: List[Dict[str, Any]], interacted_elements: List[Dict[str, Any]]) -> None:
    """Bind each needs_element action to one interacted element (1:1 by order)."""
    element_idx = 0
    for action in actions:
        if not action.get('needs_element'):
            continue
        if action.get('locators'):
            ranked = _rank_locators(action['locators'])
            action['locators'] = ranked
            action['primary_locator'] = ranked[0] if ranked else None
            continue

        el_item = None
        # Prefer explicit element_index from browser-use params
        idx = action.get('element_index')
        if idx is None and isinstance(action.get('params'), dict):
            idx = action['params'].get('index') or action['params'].get('element_index')
        if idx is not None:
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                idx = None
        if idx is not None and 0 <= idx < len(interacted_elements):
            el_item = interacted_elements[idx]
        elif element_idx < len(interacted_elements):
            el_item = interacted_elements[element_idx]
            element_idx += 1

        if not el_item:
            continue
        ranked = _rank_locators(el_item.get('locators') or [])
        if not ranked:
            continue
        action['locators'] = ranked[:5]
        action['primary_locator'] = ranked[0]
        raw = el_item.get('raw') or {}
        if isinstance(raw, dict):
            hint = (
                raw.get('text') or raw.get('inner_text')
                or (raw.get('attributes') or {}).get('aria-label')
                or (raw.get('attributes') or {}).get('placeholder')
                or (raw.get('attributes') or {}).get('name')
            )
            if hint and not action.get('description'):
                action['description'] = _safe_str(hint, 80)


def build_step_trace_from_history(history: Any) -> List[Dict[str, Any]]:
    """Serialize browser-use AgentHistory into step-level traces (keeps interacted_elements)."""
    steps_raw = []
    if history is None:
        return []

    if hasattr(history, 'history'):
        steps_raw = list(history.history or [])
    elif hasattr(history, 'steps'):
        steps_raw = list(history.steps or [])
    elif isinstance(history, list):
        steps_raw = history
    else:
        return []

    trace: List[Dict[str, Any]] = []
    for i, step in enumerate(steps_raw):
        model_output = getattr(step, 'model_output', None)
        actions = []
        if model_output is not None:
            action_list = getattr(model_output, 'action', None)
            if action_list is None and isinstance(_dictify(model_output), dict):
                action_list = _dictify(model_output).get('action')
            if action_list is None:
                action_list = [model_output]
            if not isinstance(action_list, (list, tuple)):
                action_list = [action_list]
            for action in action_list:
                mapped = _parse_action_item(action)
                if mapped:
                    actions.append(mapped)

        interacted = getattr(step, 'state', None)
        interacted_elements = []
        if interacted is not None:
            els = getattr(interacted, 'interacted_element', None) or getattr(interacted, 'interacted_elements', None)
            if els:
                if not isinstance(els, (list, tuple)):
                    els = [els]
                for el in els:
                    interacted_elements.append({
                        'raw': _dictify(el),
                        'locators': _rank_locators(_extract_locators_from_element(el)),
                    })

        step_el = getattr(step, 'interacted_element', None)
        if step_el:
            if not isinstance(step_el, (list, tuple)):
                step_el = [step_el]
            for el in step_el:
                interacted_elements.append({
                    'raw': _dictify(el),
                    'locators': _rank_locators(_extract_locators_from_element(el)),
                })

        result = getattr(step, 'result', None)
        error = None
        if result is not None:
            if isinstance(result, (list, tuple)) and result:
                first = result[0]
                error = getattr(first, 'error', None) or (_dictify(first) or {}).get('error')
            else:
                error = getattr(result, 'error', None)

        _bind_locators_to_actions(actions, interacted_elements)

        if not actions and not interacted_elements:
            actions = [{
                'action_type': 'meta',
                'description': _safe_str(model_output)[:200] or f'step_{i}',
                'skip': True,
                'raw_action': 'unknown',
                'params': {},
            }]

        trace.append({
            'step': i,
            'actions': actions,
            'interacted_elements': interacted_elements,
            'error': _safe_str(error) if error else None,
            'url': _safe_str(getattr(getattr(step, 'state', None), 'url', '') or ''),
        })

    return trace


def extract_action_trace_from_history(history: Any) -> List[Dict[str, Any]]:
    """Serialize browser-use AgentHistory into flat normalized_actions."""
    return normalize_actions_from_trace(build_step_trace_from_history(history))


def normalize_actions_from_trace(trace: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten step-level trace into ordered normalized_actions for compiler."""
    normalized: List[Dict[str, Any]] = []
    order = 1
    for step in trace:
        for action in step.get('actions') or []:
            if action.get('skip'):
                continue
            locators = action.get('locators') or (
                [action['primary_locator']] if action.get('primary_locator') else []
            )
            locators = _rank_locators(locators)
            # Unstable-only fallback for element actions
            if action.get('needs_element') and not locators:
                idx = action.get('element_index')
                if idx is None and isinstance(action.get('params'), dict):
                    idx = action['params'].get('index')
                if idx is not None:
                    locators = [{'strategy': 'css', 'value': f'body >> nth={idx}', 'unstable': True}]
                    action['description'] = (action.get('description') or '') + ' (不稳定定位，请人工确认)'

            item = {
                'order': order,
                'action_type': action.get('action_type') or 'click',
                'description': action.get('description') or '',
                'input_value': action.get('input_value') or '',
                'wait_time': action.get('wait_time', 1000),
                'needs_element': bool(action.get('needs_element')),
                'locators': locators,
                'primary_locator': locators[0] if locators else None,
                'raw_action': action.get('raw_action'),
                'params': action.get('params') or {},
                'sensitive': bool(action.get('sensitive')),
                'url': step.get('url') or '',
                'step_index': step.get('step'),
                'unstable': _is_unstable_only(locators),
            }
            normalized.append(item)
            order += 1
    return normalized


def normalize_recording_events(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Playwright recording events into normalized_actions."""
    normalized: List[Dict[str, Any]] = []
    order = 1
    for event in raw_events or []:
        etype = (event.get('type') or event.get('action') or '').lower()
        selectors = event.get('selectors') or event.get('locators') or []
        if isinstance(selectors, str):
            selectors = [{'strategy': 'css', 'value': selectors}]
        locators = []
        for sel in selectors:
            if isinstance(sel, str):
                locators.append({'strategy': 'css', 'value': sel})
            elif isinstance(sel, dict) and sel.get('value'):
                locators.append({
                    'strategy': sel.get('strategy') or sel.get('name') or 'css',
                    'value': sel['value'],
                })

        if etype in ('goto', 'navigate', 'open'):
            action_type, needs_element = 'navigate', False
            input_value = event.get('url') or event.get('value') or ''
            description = f"打开 {input_value}"
        elif etype in ('fill', 'type', 'input'):
            action_type, needs_element = 'fill', True
            input_value = event.get('value') or event.get('text') or ''
            description = event.get('description') or '输入文本'
        elif etype in ('click', 'dblclick'):
            action_type, needs_element = 'click', True
            input_value = ''
            description = event.get('description') or '点击元素'
        elif etype in ('hover', 'mouseover', 'mouseenter'):
            action_type, needs_element = 'hover', True
            input_value = ''
            description = event.get('description') or '悬停元素'
        elif etype in ('scroll',):
            # Page/container scroll: input_value = "x,y"; optional container locators
            sx = event.get('scrollX')
            sy = event.get('scrollY')
            if sx is None or sy is None:
                raw_val = event.get('value') or ''
                if isinstance(raw_val, str) and ',' in raw_val:
                    parts = raw_val.split(',', 1)
                    try:
                        sx, sy = int(float(parts[0])), int(float(parts[1]))
                    except (TypeError, ValueError):
                        sx, sy = 0, 0
                else:
                    sx, sy = 0, 0
            action_type = 'scroll'
            needs_element = bool(locators)
            input_value = f'{int(sx)},{int(sy)}'
            description = event.get('description') or f'滚动到 ({int(sx)}, {int(sy)})'
        elif etype in ('switchtab', 'switch_tab', 'switch'):
            action_type, needs_element = 'switchTab', False
            input_value = str(event.get('value') if event.get('value') is not None else '')
            description = event.get('description') or (
                f'切换到标签页 {input_value}' if input_value != '' else '切换标签页'
            )
        elif etype in ('wait',):
            action_type, needs_element = 'wait', False
            input_value = ''
            description = '等待'
        else:
            action_type, needs_element = 'click', bool(locators)
            input_value = event.get('value') or ''
            description = event.get('description') or etype or '操作'

        # 密码等敏感字段：优先信任采集端标记，其次用字段名启发式（勿把明文写进轨迹）
        locator_blob = ' '.join(
            f"{(l.get('strategy') or '')} {(l.get('value') or '')}" for l in locators
        )
        sensitive = bool(event.get('sensitive')) or (
            action_type == 'fill'
            and bool(SENSITIVE_KEYS.search(
                f'{description} {locator_blob} {_safe_str(event.get("name"))}'
            ))
        )
        if sensitive and action_type == 'fill':
            input_value = '******'

        normalized.append({
            'order': order,
            'action_type': action_type,
            'description': description,
            'input_value': _safe_str(input_value),
            'wait_time': int(event.get('wait_time') or 1000),
            'needs_element': needs_element,
            'locators': locators,
            'primary_locator': locators[0] if locators else None,
            'raw_action': etype,
            'params': {k: v for k, v in (event or {}).items() if k != 'value'} if sensitive else event,
            'sensitive': sensitive,
            'url': event.get('url') or '',
        })
        order += 1
    return normalized


def enhance_step_info(step: Any, step_index: int) -> Dict[str, Any]:
    """Richer step summary for steps_completed JSON."""
    info: Dict[str, Any] = {'step': step_index}
    model_output = getattr(step, 'model_output', None)
    actions = []
    if model_output is not None:
        action_list = getattr(model_output, 'action', None)
        if action_list is None:
            action_list = [model_output]
        if not isinstance(action_list, (list, tuple)):
            action_list = [action_list]
        for action in action_list:
            mapped = _parse_action_item(action)
            if mapped:
                actions.append({
                    'action_type': mapped.get('action_type'),
                    'description': mapped.get('description'),
                    'raw_action': mapped.get('raw_action'),
                    'locators': mapped.get('locators') or (
                        [mapped['primary_locator']] if mapped.get('primary_locator') else []
                    ),
                })
    info['actions'] = actions
    if actions:
        info['action'] = actions[0].get('description') or actions[0].get('raw_action')
    else:
        info['action'] = _safe_str(model_output)[:300] or f'step_{step_index}'

    state = getattr(step, 'state', None)
    if state is not None:
        info['url'] = _safe_str(getattr(state, 'url', '') or '')
    return info

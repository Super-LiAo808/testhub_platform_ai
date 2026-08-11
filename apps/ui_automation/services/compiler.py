"""Compile normalized actions into Element + TestCase + TestCaseStep."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

from apps.ui_automation.models import (
    TestCase,
    TestCaseStep,
    UIActionTrace,
    UiProject,
)
from apps.ui_automation.services.action_trace import SENSITIVE_KEYS
from apps.ui_automation.services.element_sync import (
    get_or_create_strategy,
    guess_element_type,
    upsert_element_from_action,
)

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = {
    'click', 'fill', 'getText', 'waitFor', 'hover', 'scroll',
    'screenshot', 'assert', 'wait', 'switchTab',
}


def _get_or_create_strategy(name: str):
    return get_or_create_strategy(name)


def _guess_element_type(action_type: str) -> str:
    return guess_element_type(action_type)


def _sanitize_input(value: str, sensitive: bool = False) -> str:
    if sensitive or SENSITIVE_KEYS.search(value or ''):
        return ''
    return value or ''


def preview_compile(normalized_actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a dry preview without writing DB."""
    steps = []
    warnings = []
    for action in normalized_actions or []:
        action_type = action.get('action_type')
        if action_type == 'navigate':
            action_type = 'wait'
            warnings.append(f"步骤{action.get('order')}: navigate 将映射为 wait，URL 写入 input_value")
        if action_type == 'meta' or action.get('skip'):
            continue
        if action_type not in SUPPORTED_ACTIONS:
            warnings.append(f"步骤{action.get('order')}: 不支持的动作 {action_type}，将跳过")
            continue
        locators = action.get('locators') or []
        unstable = any(l.get('unstable') for l in locators if isinstance(l, dict)) or action.get('unstable')
        if action.get('needs_element') and not locators:
            warnings.append(f"步骤{action.get('order')}: 缺少定位器，需人工补全")
        if unstable:
            warnings.append(f"步骤{action.get('order')}: 定位器不稳定，请确认")
        steps.append({
            'step_number': action.get('order'),
            'action_type': action_type,
            'description': action.get('description') or '',
            'input_value': _sanitize_input(action.get('input_value') or '', action.get('sensitive')),
            'wait_time': action.get('wait_time') or 1000,
            'locators': locators,
            'needs_element': action.get('needs_element'),
        })
    return {'steps': steps, 'warnings': warnings, 'step_count': len(steps)}


def _find_or_create_element(
    project: UiProject,
    action: Dict[str, Any],
    created_by,
    name_suffix: str,
):
    disc = action.get('discovery_source') or 'ai_discovered'
    return upsert_element_from_action(
        project,
        action,
        created_by=created_by,
        source=disc,
        name_suffix=name_suffix,
        skip_unstable=False,
    )


@transaction.atomic
def compile_actions_to_testcase(
    *,
    project: UiProject,
    normalized_actions: List[Dict[str, Any]],
    name: str,
    description: str = '',
    source: str = 'ai_compiled',
    created_by=None,
    commit: bool = True,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """
    Compile actions into TestCase.
    If commit=False, only returns preview dict (testcase=None).
    """
    preview = preview_compile(normalized_actions)
    if not commit:
        return None, preview

    if not preview['steps']:
        raise ValueError('没有可编译的有效步骤')

    test_case = TestCase.objects.create(
        name=name[:200],
        description=description or '',
        project=project,
        status='draft',
        priority='medium',
        source=source,
        created_by=created_by,
    )

    disc = 'recorded' if source == 'recorded' else 'ai_discovered'
    step_number = 1
    for action in normalized_actions or []:
        action_type = action.get('action_type')
        if action_type == 'navigate':
            TestCaseStep.objects.create(
                test_case=test_case,
                step_number=step_number,
                action_type='wait',
                element=None,
                input_value=_sanitize_input(action.get('input_value') or '', False),
                wait_time=action.get('wait_time') or 1000,
                description=action.get('description') or f"导航到 {action.get('input_value') or ''}",
            )
            step_number += 1
            continue
        if action_type == 'meta' or action.get('skip'):
            continue
        if action_type not in SUPPORTED_ACTIONS:
            continue

        element = None
        if action.get('needs_element') or action_type in (
            'click', 'fill', 'hover', 'waitFor', 'getText', 'assert', 'scroll'
        ):
            if action.get('locators') or action.get('primary_locator'):
                element = _find_or_create_element(
                    project,
                    {**action, 'discovery_source': disc},
                    created_by,
                    str(step_number),
                )

        TestCaseStep.objects.create(
            test_case=test_case,
            step_number=step_number,
            action_type=action_type,
            element=element,
            input_value=_sanitize_input(action.get('input_value') or '', action.get('sensitive')),
            wait_time=action.get('wait_time') or 1000,
            description=action.get('description') or '',
        )
        step_number += 1

    preview['test_case_id'] = test_case.id
    return test_case, preview


def compile_trace_to_testcase(
    trace: UIActionTrace,
    *,
    name: str,
    description: str = '',
    created_by=None,
    commit: bool = True,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    if not trace.project:
        raise ValueError('轨迹未关联 UI 项目，无法编译')
    actions = trace.normalized_actions or []
    source = 'recorded' if trace.source == 'recording' else 'ai_compiled'
    return compile_actions_to_testcase(
        project=trace.project,
        normalized_actions=actions,
        name=name,
        description=description,
        source=source,
        created_by=created_by,
        commit=commit,
    )

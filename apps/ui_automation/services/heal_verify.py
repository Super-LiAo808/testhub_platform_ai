"""Post-apply verification (re-run) for self-healing proposals."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


def _build_steps_data(test_case):
    steps_data = []
    for step in test_case.steps.select_related('element', 'element__locator_strategy').order_by('step_number'):
        element_data = None
        if step.element_id:
            el = step.element
            element_data = {
                'id': el.id,
                'name': el.name,
                'locator_value': el.locator_value,
                'locator_strategy': el.locator_strategy.name if el.locator_strategy_id else 'css',
                'backup_locators': el.backup_locators or [],
                'wait_timeout': el.wait_timeout,
                'force_action': el.force_action,
            }
        steps_data.append({
            'step': step,
            'action_type': step.action_type,
            'description': step.description or '',
            'element_data': element_data,
        })
    return steps_data


def _run_testcase_sync(test_case, *, engine: str, browser: str, headless: bool, user) -> Dict[str, Any]:
    """Compact sync re-run used for heal verification (not a full UI response)."""
    from apps.ui_automation.models import TestCaseExecution

    engine = (engine or 'playwright').lower()
    browser = browser or 'chrome'
    execution = TestCaseExecution.objects.create(
        test_case=test_case,
        project=test_case.project,
        execution_source='manual',
        status='running',
        engine=engine,
        browser=browser,
        headless=bool(headless),
        created_by=user,
        started_at=timezone.now(),
    )
    start = time.time()
    step_results = []
    error_message = ''
    status = 'passed'
    try:
        steps_data = _build_steps_data(test_case)
        if engine == 'selenium':
            from apps.ui_automation.selenium_engine import SeleniumTestEngine
            eng = SeleniumTestEngine(browser_type=browser, headless=bool(headless))
            eng.start()
            try:
                if test_case.project.base_url:
                    ok, nav_log = eng.navigate(test_case.project.base_url)
                    if not ok:
                        status = 'failed'
                        error_message = nav_log or '导航失败'
                    else:
                        for i, info in enumerate(steps_data, 1):
                            success, step_log, _ = eng.execute_step(info['step'], info['element_data'] or {})
                            step_results.append({
                                'step_number': i,
                                'step_id': info['step'].id,
                                'action_type': info['action_type'],
                                'success': success,
                                'error': None if success else step_log,
                                'element_id': (info['element_data'] or {}).get('id'),
                            })
                            if not success:
                                status = 'failed'
                                error_message = step_log or f'步骤 {i} 失败'
                                break
            finally:
                try:
                    eng.stop()
                except Exception:
                    pass
        else:
            import asyncio
            from apps.ui_automation.playwright_engine import PlaywrightTestEngine

            async def _async_run():
                nonlocal status, error_message
                eng = PlaywrightTestEngine(browser_type=browser, headless=bool(headless))
                await eng.start()
                try:
                    if test_case.project.base_url:
                        ok, nav_log = await eng.navigate(test_case.project.base_url)
                        if not ok:
                            status = 'failed'
                            error_message = nav_log or '导航失败'
                            return
                    for i, info in enumerate(steps_data, 1):
                        success, step_log, _ = await eng.execute_step(info['step'], info['element_data'] or {})
                        step_results.append({
                            'step_number': i,
                            'step_id': info['step'].id,
                            'action_type': info['action_type'],
                            'success': success,
                            'error': None if success else step_log,
                            'element_id': (info['element_data'] or {}).get('id'),
                        })
                        if not success:
                            status = 'failed'
                            error_message = step_log or f'步骤 {i} 失败'
                            return
                finally:
                    try:
                        await eng.stop()
                    except Exception:
                        pass

            loop = asyncio.new_event_loop()
            try:
                from apps.ui_automation.playwright_engine import ensure_windows_proactor_event_loop
                ensure_windows_proactor_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_async_run())
            finally:
                loop.close()
    except Exception as exc:
        logger.exception('heal verify re-run failed')
        status = 'failed'
        error_message = str(exc)

    import json
    execution.status = status
    execution.error_message = error_message
    execution.execution_logs = json.dumps(step_results, ensure_ascii=False)
    execution.execution_time = round(time.time() - start, 2)
    execution.finished_at = timezone.now()
    execution.save()
    return {
        'execution_id': execution.id,
        'status': status,
        'error_message': error_message,
        'passed': status == 'passed',
    }


def verify_proposal_by_rerun(proposal, user=None) -> Dict[str, Any]:
    """Re-run related test case / script after applying a fix. Updates proposal.verify_* fields."""
    from apps.ui_automation.models import (
        AIExecutionRecord,
        TestCase,
        TestCaseExecution,
        TestExecution,
        TestScript,
    )
    from apps.ui_automation.services.heal_settings import get_project_heal_settings

    diagnosis = proposal.diagnosis
    project = diagnosis.project
    settings = get_project_heal_settings(project)
    if not settings.get('verify_rerun', True):
        proposal.verify_status = 'skipped'
        proposal.save(update_fields=['verify_status', 'updated_at'])
        return {'verify_status': 'skipped', 'reason': 'verify_rerun disabled'}

    # 独立脚本：直接重跑脚本内容（与用户「运行脚本」一致）
    if diagnosis.execution_type == 'script':
        orig = TestExecution.objects.filter(id=diagnosis.execution_id).select_related('test_script').first()
        script = orig.test_script if orig else None
        if not script:
            script_id = (proposal.patch_payload or {}).get('test_script_id')
            if script_id:
                script = TestScript.objects.filter(id=script_id).first()
        if not script:
            case_id = (proposal.patch_payload or {}).get('test_case_id')
            if case_id:
                script = TestScript.objects.filter(source_test_case_id=case_id).first()
        if not script:
            proposal.verify_status = 'skipped'
            proposal.save(update_fields=['verify_status', 'updated_at'])
            return {'verify_status': 'skipped', 'reason': 'no linked script'}

        from apps.ui_automation.services.script_runner import run_script_sync

        headless = True if not orig or orig.headless is None else bool(orig.headless)
        verify_exec = TestExecution.objects.create(
            project=script.project,
            test_script=script,
            environment=(orig.environment if orig else 'CHROME'),
            status='PENDING',
            engine=script.framework or 'playwright',
            browser=(orig.browser if orig else 'chrome'),
            headless=headless,
            executed_by=user or proposal.reviewed_by or proposal.created_by,
            total_cases=1,
        )
        run_script_sync(script, execution=verify_exec, headless=headless)
        verify_exec.refresh_from_db()
        passed = verify_exec.status == 'SUCCESS'
        proposal.verify_execution_type = 'script'
        proposal.verify_execution_id = verify_exec.id
        proposal.verify_status = 'passed' if passed else 'failed'
        proposal.save(update_fields=[
            'verify_status', 'verify_execution_type', 'verify_execution_id', 'updated_at',
        ])
        return {
            'verify_status': proposal.verify_status,
            'verify_execution_id': verify_exec.id,
            'verify_execution_type': 'script',
            'error_message': verify_exec.error_message or '',
        }

    test_case = None
    engine = 'playwright'
    browser = 'chrome'
    headless = True

    if diagnosis.execution_type == 'testcase':
        orig = TestCaseExecution.objects.filter(id=diagnosis.execution_id).select_related('test_case').first()
        if orig:
            test_case = orig.test_case
            engine = orig.engine or engine
            browser = orig.browser or browser
            headless = True if orig.headless is None else orig.headless
    elif diagnosis.execution_type == 'ai':
        ai = AIExecutionRecord.objects.filter(id=diagnosis.execution_id).first()
        if ai and ai.derived_test_case_id:
            test_case = ai.derived_test_case
        elif ai and ai.ai_case_id and getattr(ai.ai_case, 'linked_test_case_id', None):
            test_case = ai.ai_case.linked_test_case

    if not test_case:
        # Try element → any case step
        element_id = (proposal.patch_payload or {}).get('element_id')
        if element_id:
            from apps.ui_automation.models import TestCaseStep
            step = TestCaseStep.objects.filter(element_id=element_id).select_related('test_case').first()
            if step:
                test_case = step.test_case

    if not test_case:
        proposal.verify_status = 'skipped'
        proposal.save(update_fields=['verify_status', 'updated_at'])
        return {'verify_status': 'skipped', 'reason': 'no linked test case'}

    user = user or proposal.reviewed_by or proposal.created_by
    if not user:
        proposal.verify_status = 'skipped'
        proposal.save(update_fields=['verify_status', 'updated_at'])
        return {'verify_status': 'skipped', 'reason': 'no user for re-run'}

    result = _run_testcase_sync(
        test_case, engine=engine, browser=browser, headless=headless, user=user
    )
    proposal.verify_execution_type = 'testcase'
    proposal.verify_execution_id = result['execution_id']
    proposal.verify_status = 'passed' if result.get('passed') else 'failed'
    proposal.save(update_fields=[
        'verify_status', 'verify_execution_type', 'verify_execution_id', 'updated_at',
    ])
    return {
        'verify_status': proposal.verify_status,
        'verify_execution_id': proposal.verify_execution_id,
        'verify_execution_type': 'testcase',
        'error_message': result.get('error_message') or '',
    }

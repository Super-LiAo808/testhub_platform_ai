"""UI automation signals — auto failure diagnosis after executions fail."""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='ui_automation.TestCaseExecution')
def on_testcase_execution_saved(sender, instance, **kwargs):
    if instance.status not in ('failed', 'error'):
        return
    if not instance.finished_at:
        return
    try:
        from .services.diagnosis import auto_diagnose_testcase_execution
        auto_diagnose_testcase_execution(instance, created_by=getattr(instance, 'created_by', None), use_llm=False)
    except Exception:
        logger.exception('auto diagnose testcase execution #%s failed', instance.id)


@receiver(post_save, sender='ui_automation.AIExecutionRecord')
def on_ai_execution_saved(sender, instance, **kwargs):
    if instance.status != 'failed':
        return
    if not getattr(instance, 'end_time', None):
        return
    try:
        from .services.diagnosis import auto_diagnose_ai_execution
        auto_diagnose_ai_execution(instance, created_by=getattr(instance, 'executed_by', None), use_llm=False)
    except Exception:
        logger.exception('auto diagnose AI execution #%s failed', instance.id)


@receiver(post_save, sender='ui_automation.TestExecution')
def on_suite_or_script_execution_saved(sender, instance, **kwargs):
    """Independent script runs use TestExecution with test_script_id."""
    status = (instance.status or '').upper()
    if status != 'FAILED':
        return
    if not instance.finished_at:
        return
    if not instance.test_script_id:
        return
    try:
        from .services.diagnosis import auto_diagnose_script_execution
        auto_diagnose_script_execution(instance, created_by=getattr(instance, 'executed_by', None), use_llm=False)
    except Exception:
        logger.exception('auto diagnose script execution #%s failed', instance.id)

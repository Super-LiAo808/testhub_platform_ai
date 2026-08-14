"""APP automation signals — auto diagnose failed executions."""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='app_automation.AppTestExecution')
def on_app_execution_saved(sender, instance, **kwargs):
    from apps.app_automation.constants import ExecutionResult
    if getattr(instance, 'result', None) != ExecutionResult.FAILED:
        return
    if not getattr(instance, 'finished_at', None):
        return
    try:
        from apps.ui_automation.services.diagnosis import diagnose_failure, has_diagnosis
        if has_diagnosis('app', instance.id):
            return
        logs = getattr(instance, 'error_message', '') or ''
        diagnose_failure(
            execution_type='app',
            execution_id=instance.id,
            project=None,
            logs=logs,
            error_message=logs,
            context={
                'test_case_id': instance.test_case_id,
                'device_id': instance.device_id,
                'result': instance.result,
            },
            created_by=getattr(instance, 'user', None),
            use_llm=False,
            auto_apply=False,
        )
    except Exception:
        logger.exception('auto diagnose APP execution #%s failed', instance.id)

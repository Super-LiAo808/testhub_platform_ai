"""Async worker for page element scan jobs."""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)


def _update_job(job_id: int, **fields) -> None:
    from apps.ui_automation.models import PageElementScanJob

    try:
        PageElementScanJob.objects.filter(id=job_id).update(**fields, updated_at=timezone.now())
    except Exception as exc:
        logger.warning('update scan job %s failed: %s', job_id, exc)


def _persist_scan_result(job, scan_result: Dict[str, Any]) -> Dict[str, Any]:
    """将扫描候选写入元素库，返回可序列化 result。"""
    from apps.ui_automation.services.element_sync import (
        ensure_page_scan_group,
        sync_elements_from_scan,
    )
    from apps.ui_automation.operation_logger import log_operation

    project = job.project
    group = ensure_page_scan_group(
        project,
        scan_result.get('url') or job.url,
        group_id=job.target_group_id,
        title=scan_result.get('title') or '',
    )
    sync_stats = sync_elements_from_scan(
        project,
        scan_result.get('candidates') or [],
        group=group,
        created_by=job.created_by,
        source='page_scan',
    )
    result = {
        'url': scan_result.get('url') or job.url,
        'requested_url': scan_result.get('requested_url') or job.url,
        'title': scan_result.get('title') or '',
        'scanned_count': scan_result.get('count') or len(scan_result.get('candidates') or []),
        'created': sync_stats.get('created') or 0,
        'updated': sync_stats.get('updated') or 0,
        'skipped': sync_stats.get('skipped') or 0,
        'total': sync_stats.get('total') or 0,
        'group_id': group.id,
        'group_name': group.name,
        'element_ids': sync_stats.get('element_ids') or [],
        'preview': sync_stats.get('preview') or [],
        'partial': bool(scan_result.get('partial')),
    }

    try:
        user = job.created_by
        if user:
            log_operation(
                'create', 'element', group.id, group.name, user,
                description=f'页面扫描入库「{group.name}」'
                + ('（部分结果）' if result['partial'] else ''),
            )
    except Exception as exc:
        logger.debug('log_operation after scan failed: %s', exc)

    return result


def run_page_scan_job(job_id: int) -> None:
    """Execute one scan job (intended to run in a background thread)."""
    from apps.ui_automation.models import PageElementScanJob
    from apps.ui_automation.services.page_element_scanner import (
        PageScanPartialError,
        scan_page_elements,
    )

    close_old_connections()
    job = PageElementScanJob.objects.select_related('project', 'created_by', 'target_group').filter(id=job_id).first()
    if not job:
        return
    if job.status in ('success', 'cancelled'):
        return

    _update_job(
        job_id,
        status='running',
        progress=5,
        message='正在排队获取扫描槽位…',
        started_at=timezone.now(),
        error_message='',
    )

    try:
        def _on_progress(phase, message, progress, _partial):
            _update_job(
                job_id,
                progress=max(15, min(int(progress or 15), 69)),
                message=str(message or phase)[:500],
            )

        _update_job(job_id, progress=15, message='正在启动扫描进程…')
        scan_result = scan_page_elements(
            job.url,
            headless=bool(job.headless),
            max_elements=int(job.max_elements or 200),
            progress_callback=_on_progress,
        )

        _update_job(job_id, progress=70, message='正在写入元素库…')
        result = _persist_scan_result(job, scan_result)
        _update_job(
            job_id,
            status='success',
            progress=100,
            message=f"扫描完成：发现 {result['scanned_count']} 个元素，"
                    f"新建 {result['created']}，更新 {result['updated']}",
            result=result,
            finished_at=timezone.now(),
            error_message='',
        )

    except PageScanPartialError as exc:
        logger.warning('page scan job %s partial: %s', job_id, exc)
        scan_result = exc.data or {}
        result = {}
        try:
            if scan_result.get('candidates'):
                _update_job(job_id, progress=70, message='扫描未完整完成，正在写入已抽取元素…')
                result = _persist_scan_result(job, {**scan_result, 'partial': True})
        except Exception as sync_exc:
            logger.exception('partial persist failed for job %s: %s', job_id, sync_exc)
            _update_job(
                job_id,
                status='failed',
                progress=100,
                message='扫描失败，且部分结果入库失败',
                error_message=f'{exc}; 入库错误: {sync_exc}'[:2000],
                finished_at=timezone.now(),
            )
            return

        saved = (result.get('created') or 0) + (result.get('updated') or 0)
        _update_job(
            job_id,
            status='failed',
            progress=100,
            message=(
                f"扫描未完整完成，已保存 {saved} 个元素"
                if saved
                else '扫描未完整完成，无可保存元素'
            ),
            result=result,
            error_message=str(exc)[:2000],
            finished_at=timezone.now(),
        )

    except Exception as exc:
        logger.exception('page scan job %s failed: %s', job_id, exc)
        _update_job(
            job_id,
            status='failed',
            progress=100,
            message='扫描失败',
            error_message=str(exc)[:2000],
            finished_at=timezone.now(),
        )
    finally:
        close_old_connections()


def start_page_scan_job_async(job_id: int) -> None:
    """Spawn a daemon thread to run the scan job."""
    thread = threading.Thread(
        target=run_page_scan_job,
        args=(job_id,),
        name=f'page-scan-job-{job_id}',
        daemon=True,
    )
    thread.start()


def serialize_scan_job(job) -> dict:
    """API-friendly representation of a scan job."""
    result = job.result if isinstance(job.result, dict) else {}
    return {
        'id': job.id,
        'project_id': job.project_id,
        'target_group_id': job.target_group_id,
        'url': job.url,
        'max_elements': job.max_elements,
        'headless': job.headless,
        'status': job.status,
        'progress': job.progress,
        'message': job.message or '',
        'error_message': job.error_message or '',
        'result': result,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'finished_at': job.finished_at.isoformat() if job.finished_at else None,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'created_by_id': job.created_by_id,
    }


def list_scan_jobs_for_user(user, *, project_id: Optional[int] = None, limit: int = 30) -> list:
    """List recent scan jobs visible to user."""
    from apps.ui_automation.models import PageElementScanJob, UiProject
    from django.db import models as dj_models

    qs = PageElementScanJob.objects.select_related('project', 'created_by').all()
    if project_id:
        project = UiProject.objects.filter(
            dj_models.Q(owner=user) | dj_models.Q(members=user),
            id=project_id,
        ).distinct().first()
        if not project:
            return []
        qs = qs.filter(project=project)
    else:
        project_ids = UiProject.objects.filter(
            dj_models.Q(owner=user) | dj_models.Q(members=user),
        ).values_list('id', flat=True)
        qs = qs.filter(project_id__in=project_ids)

    limit = max(1, min(int(limit or 30), 100))
    return [serialize_scan_job(j) for j in qs.order_by('-id')[:limit]]

# -*- coding: utf-8 -*-
"""
APP自动化测试 Celery 任务
"""
from celery import shared_task
from django.utils import timezone
import logging
import os
import threading
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import close_old_connections

logger = logging.getLogger(__name__)


def celery_workers_available(timeout: float = 0.6) -> bool:
    """探测是否有可用的 Celery worker；不可用时走本地线程兜底。"""
    try:
        from django.conf import settings
        if getattr(settings, 'APP_AUTOMATION_FORCE_THREAD', False):
            return False
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            return True
        from backend.celery import app
        insp = app.control.inspect(timeout=timeout)
        ping = insp.ping() if insp else None
        return bool(ping)
    except Exception as exc:
        logger.debug('celery worker probe failed: %s', exc)
        return False


def dispatch_app_test_execution(execution_id, package_name: str = None, scheduled_task_id: int = None) -> str:
    """提交单用例执行：优先 Celery，无 worker 时用后台线程（与 UI 自动化本地模式一致）。"""
    if celery_workers_available():
        async_result = execute_app_test_task.delay(
            execution_id, package_name=package_name, scheduled_task_id=scheduled_task_id
        )
        logger.info('APP 用例走 Celery: execution_id=%s task_id=%s', execution_id, async_result.id)
        return async_result.id

    task_id = f'thread-{execution_id}'

    def _runner():
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        close_old_connections()
        try:
            execute_app_test_task.run(
                execution_id, package_name=package_name, scheduled_task_id=scheduled_task_id
            )
        except Exception:
            logger.exception('thread execute_app_test_task failed: execution_id=%s', execution_id)
        finally:
            close_old_connections()

    threading.Thread(target=_runner, name=f'app-exec-{execution_id}', daemon=True).start()
    logger.warning(
        '未检测到 Celery worker，已用本地线程执行 APP 用例: execution_id=%s task_id=%s',
        execution_id, task_id,
    )
    return task_id


def dispatch_app_suite_execution(suite_id, execution_ids, package_name: str = None, scheduled_task_id: int = None) -> str:
    """提交套件执行：优先 Celery，无 worker 时用后台线程。"""
    if celery_workers_available():
        async_result = execute_app_suite_task.delay(
            suite_id=suite_id,
            execution_ids=execution_ids,
            package_name=package_name,
            scheduled_task_id=scheduled_task_id,
        )
        logger.info('APP 套件走 Celery: suite_id=%s task_id=%s', suite_id, async_result.id)
        return async_result.id

    task_id = f'thread-suite-{suite_id}-{execution_ids[0] if execution_ids else 0}'

    def _runner():
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        close_old_connections()
        try:
            execute_app_suite_task.run(
                suite_id=suite_id,
                execution_ids=execution_ids,
                package_name=package_name,
                scheduled_task_id=scheduled_task_id,
            )
        except Exception:
            logger.exception('thread execute_app_suite_task failed: suite_id=%s', suite_id)
        finally:
            close_old_connections()

    threading.Thread(target=_runner, name=f'app-suite-{suite_id}', daemon=True).start()
    logger.warning(
        '未检测到 Celery worker，已用本地线程执行 APP 套件: suite_id=%s task_id=%s',
        suite_id, task_id,
    )
    return task_id


def send_scheduled_task_notification(task_id, success):
    """发送定时任务执行通知（Webhook + 邮件）"""
    try:
        from .models import AppScheduledTask, AppNotificationLog

        task = AppScheduledTask.objects.get(id=task_id)

        if success and not task.notify_on_success:
            return
        if not success and not task.notify_on_failure:
            return
        if not task.notification_type:
            return

        status_text = '成功' if success else '失败'
        last_result = task.last_result or {}
        result_message = last_result.get('message', '')
        local_run_time = timezone.localtime(task.last_run_time).strftime('%Y-%m-%d %H:%M:%S') if task.last_run_time else '未知'
        device_name = (task.device.name or task.device.device_id) if task.device else '未指定'

        detail_content = (
            f"任务名称: {task.name}\n\n"
            f"执行状态: {status_text}\n\n"
            f"执行时间: {local_run_time}\n\n"
            f"任务类型: {task.get_task_type_display()}\n\n"
            f"执行设备: {device_name}"
        )
        if result_message:
            detail_content += f"\n\n执行结果: {result_message}"

        # Webhook 通知
        if task.notification_type in ['webhook', 'both']:
            _send_app_webhook_notification(task, detail_content, status_text)

        # 邮件通知
        if task.notification_type in ['email', 'both']:
            _send_app_email_notification(task, detail_content, status_text)

    except Exception as e:
        logger.error(f"发送APP定时任务通知失败: {e}", exc_info=True)


def _send_app_webhook_notification(task, detail_content, status_text):
    """发送 Webhook 通知"""
    import requests
    import json
    from .models import AppNotificationLog

    try:
        from apps.core.models import UnifiedNotificationConfig
        configs = UnifiedNotificationConfig.objects.filter(
            config_type__in=['webhook_wechat', 'webhook_feishu', 'webhook_dingtalk'],
            is_active=True
        )
    except Exception as e:
        logger.error(f"获取通知配置失败: {e}")
        return

    all_bots = []
    for config in configs:
        for bot in config.get_webhook_bots():
            if bot.get('enabled', True):
                all_bots.append(bot)

    if not all_bots:
        return

    for bot in all_bots:
        webhook_url = bot.get('webhook_url')
        if not webhook_url:
            continue

        bot_type = bot.get('type', 'unknown')
        success = status_text == '成功'

        if bot_type == 'wechat':
            message_data = {"msgtype": "markdown", "markdown": {"content": f"**APP自动化定时任务执行{status_text}**\n\n{detail_content}"}}
        elif bot_type == 'feishu':
            message_data = {"msg_type": "interactive", "card": {"elements": [{"tag": "div", "text": {"content": f"**APP自动化定时任务执行{status_text}**\n\n{detail_content}", "tag": "lark_md"}}], "header": {"title": {"content": f"APP自动化定时任务执行{status_text}", "tag": "plain_text"}, "template": "green" if success else "red"}}}
        elif bot_type == 'dingtalk':
            message_data = {"msgtype": "markdown", "markdown": {"title": f"APP自动化定时任务执行{status_text}", "text": f"**APP自动化定时任务执行{status_text}**\n\n{detail_content}"}}
            secret = bot.get('secret')
            if secret:
                import time as _time, hmac, hashlib, base64, urllib.parse
                timestamp = str(round(_time.time() * 1000))
                sign = urllib.parse.quote_plus(base64.b64encode(hmac.new(secret.encode('utf-8'), f'{timestamp}\n{secret}'.encode('utf-8'), digestmod=hashlib.sha256).digest()))
                webhook_url += f'{"&" if "?" in webhook_url else "?"}timestamp={timestamp}&sign={sign}'
        else:
            continue

        try:
            resp = requests.post(webhook_url, json=message_data, headers={'Content-Type': 'application/json'}, timeout=10)
            log_status = 'success' if resp.status_code == 200 else 'failed'
            AppNotificationLog.objects.create(
                task=task, task_name=task.name, task_type=task.task_type,
                notification_type='task_execution', sender_name='系统Webhook通知',
                sender_email='system@notification.com',
                recipient_info=[{'name': bot.get('name', 'Unknown'), 'webhook_url': webhook_url}],
                webhook_bot_info=bot,
                notification_content=json.dumps(message_data, ensure_ascii=False),
                status=log_status,
                error_message='' if log_status == 'success' else f'HTTP {resp.status_code}: {resp.text}',
                response_info={'status_code': resp.status_code, 'response': resp.text[:500]},
                sent_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"发送Webhook失败: {e}")
            AppNotificationLog.objects.create(
                task=task, task_name=task.name, task_type=task.task_type,
                notification_type='task_execution', sender_name='系统Webhook通知',
                sender_email='system@notification.com',
                recipient_info=[{'name': bot.get('name', 'Unknown')}],
                webhook_bot_info=bot,
                notification_content=json.dumps(message_data, ensure_ascii=False),
                status='failed', error_message=str(e)
            )


def _send_app_email_notification(task, detail_content, status_text):
    """发送邮件通知"""
    from .models import AppNotificationLog

    recipients = task.notify_emails if isinstance(task.notify_emails, list) else []
    if not recipients:
        return

    try:
        from django.core.mail import send_mail
        from django.conf import settings

        subject = f"APP自动化定时任务执行{status_text}: {task.name}"
        from_email = settings.DEFAULT_FROM_EMAIL

        send_mail(subject=subject, message=detail_content, from_email=from_email, recipient_list=recipients, fail_silently=False)

        AppNotificationLog.objects.create(
            task=task, task_name=task.name, task_type=task.task_type,
            notification_type='task_execution', sender_name='系统邮件通知',
            sender_email=from_email,
            recipient_info=[{'email': e} for e in recipients],
            notification_content=detail_content, status='success', sent_at=timezone.now()
        )
    except Exception as e:
        logger.error(f"发送邮件失败: {e}", exc_info=True)
        AppNotificationLog.objects.create(
            task=task, task_name=task.name, task_type=task.task_type,
            notification_type='task_execution', sender_name='系统邮件通知',
            sender_email='',
            recipient_info=[{'email': e} for e in recipients],
            notification_content=f"发送失败: {e}", status='failed', error_message=str(e)
        )


def send_execution_update(execution_id, status=None, progress=None, message=None, report_path=None, finished_at=None, result=None):
    """通过 WebSocket 发送执行状态更新"""
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        payload = {
            "type": "execution_update",
            "execution_id": int(execution_id),
            "status": status,
            "result": result,
            "progress": progress,
            "message": message,
            "report_path": report_path,
            "finished_at": finished_at.isoformat() if finished_at else None,
        }
        async_to_sync(channel_layer.group_send)(
            f"app_execution_{execution_id}",
            payload
        )
    except Exception as e:
        logger.debug(f"发送执行状态更新失败: {e}")


@shared_task
def execute_app_test_task(execution_id, package_name: str = None, scheduled_task_id: int = None):
    """
    异步执行APP测试任务
    
    Args:
        execution_id: AppTestExecution 的 ID
        package_name: 可选的应用包名
        scheduled_task_id: 可选的定时任务 ID（来自定时调度）
    """
    from django.conf import settings
    from .models import AppTestExecution, AppDevice
    from .executors.test_executor import AppTestExecutor
    
    execution = None
    device = None
    
    try:
        # 获取执行记录
        execution = AppTestExecution.objects.get(id=execution_id)
        test_case = execution.test_case
        
        device = execution.device
        
        # 更新状态为执行中
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.progress = 0
        execution.save()
        send_execution_update(execution_id, status='running', progress=0, message='任务开始执行')
        
        logger.info(f"开始执行APP测试: {test_case.name}")
        
        # 1. 检查并锁定设备
        if device.status == 'locked' and device.locked_by != execution.user:
            raise RuntimeError(f"设备 {device.device_id} 已被其他用户锁定")
        
        if device.status != 'locked':
            device.lock(execution.user)
        
        logger.info(f"设备已锁定: {device.device_id}")
        
        # 2. 由 pytest + allure 插件执行测试
        # 进度分配：0~10% 环境准备，10~90% 步骤执行（由子进程内回调动态更新），90~100% 报告生成
        execution.progress = 10
        execution.save()
        send_execution_update(execution_id, status='running', progress=10, message='正在准备测试环境')
        
        if package_name:
            final_package_name = package_name
        else:
            final_package_name = test_case.app_package.package_name if test_case.app_package else ""

        executor = AppTestExecutor()
        report_result = executor.run_tests(
            test_case_id=test_case.id,
            device_id=device.device_id,
            package_name=final_package_name,
            execution_id=execution_id,
            username=execution.user.username if execution.user else 'unknown',
        )
        
        # 从数据库重新读取最新进度（子进程中的回调可能已经更新过）
        execution.refresh_from_db()
        
        if report_result.get('report_path'):
            execution.report_path = report_result['report_path']
            logger.info(f"报告已生成: {report_result['report_path']}")
        
        test_results = report_result.get('test_results', {})
        execution.total_steps = test_results.get('total', 0)
        execution.passed_steps = test_results.get('passed', 0)
        # parser 已将 broken 算在 failed 里，直接使用
        execution.failed_steps = test_results.get('failed', 0)
        if test_results.get('broken', 0):
            logger.info(f"检测到 broken 用例 {test_results.get('broken')} 个（已计入失败统计）。")
        
        execution.progress = 95
        execution.save()
        send_execution_update(
            execution_id,
            status='running',
            progress=95,
            message='正在生成测试报告',
            report_path=execution.report_path
        )
        
        # 3. 完成测试 — 分离任务状态和测试结果
        execution.status = 'completed'
        if execution.total_steps == 0:
            execution.result = 'skipped'
        elif execution.failed_steps == 0:
            execution.result = 'passed'
        else:
            execution.result = 'failed'
        execution.finished_at = timezone.now()
        execution.duration = (execution.finished_at - execution.started_at).total_seconds()
        execution.progress = 100
        execution.save()
        send_execution_update(
            execution_id,
            status=execution.status,
            progress=100,
            message='执行完成',
            report_path=execution.report_path,
            finished_at=execution.finished_at,
            result=execution.result,
        )
        
        logger.info(f"APP测试执行完成: {test_case.name}, 状态: {execution.status}, 结果: {execution.result}")

        # 定时任务通知
        if scheduled_task_id:
            try:
                from .models import AppScheduledTask
                st = AppScheduledTask.objects.get(id=scheduled_task_id)
                is_success = execution.result == 'passed'
                if is_success:
                    st.successful_runs += 1
                else:
                    st.failed_runs += 1
                st.last_result = {'status': execution.status, 'result': execution.result, 'message': f'{test_case.name} - {execution.result or execution.status}'}
                st.save(update_fields=['successful_runs', 'failed_runs', 'last_result'])
                send_scheduled_task_notification(scheduled_task_id, success=is_success)
            except Exception as ne:
                logger.error(f"更新定时任务状态失败: {ne}")

    except AppTestExecution.DoesNotExist:
        logger.error(f"执行记录不存在: {execution_id}")
    except Exception as e:
        logger.error(f"执行APP测试失败: {str(e)}", exc_info=True)
        
        if execution:
            execution.status = 'error'       # 任务异常（非用例失败）
            execution.result = None           # 没有测试结果
            execution.error_message = str(e)
            execution.finished_at = timezone.now()
            if execution.started_at:
                execution.duration = (execution.finished_at - execution.started_at).total_seconds()
            execution.save()
            send_execution_update(
                execution_id,
                status='error',
                progress=execution.progress or 0,
                message=str(e),
                report_path=execution.report_path,
                finished_at=execution.finished_at,
                result=None,
            )
            
            # 尝试生成报告
            try:
                executor = AppTestExecutor()
                executor._generate_allure_report(execution_id=execution_id)
            except Exception:
                pass
    finally:
        # 7. 清理：释放设备
        try:
            if device and device.locked_by == execution.user:
                device.unlock()
                logger.info(f"设备已释放: {device.device_id}")
        except Exception as e:
            logger.error(f"释放设备失败: {str(e)}")


@shared_task
def execute_app_suite_task(suite_id, execution_ids, package_name=None, scheduled_task_id=None):
    """
    异步执行APP测试套件（顺序执行多个用例）

    Args:
        suite_id: AppTestSuite 的 ID
        execution_ids: AppTestExecution ID 列表（按执行顺序）
        package_name: 可选的应用包名覆盖
        scheduled_task_id: 可选的定时任务 ID
    """
    from .models import AppTestSuite, AppTestExecution, AppDevice
    from .executors.test_executor import AppTestExecutor

    suite = None
    device = None
    passed = 0
    failed = 0

    try:
        suite = AppTestSuite.objects.get(id=suite_id)
        executions = list(
            AppTestExecution.objects.filter(id__in=execution_ids)
            .select_related('test_case', 'test_case__app_package', 'device', 'user')
            .order_by('id')
        )
        # 按 execution_ids 排序
        exec_map = {e.id: e for e in executions}
        executions = [exec_map[eid] for eid in execution_ids if eid in exec_map]

        if not executions:
            logger.error(f"套件 {suite_id} 未找到执行记录")
            return

        device = executions[0].device
        user = executions[0].user

        # 锁定设备
        if device.status != 'locked':
            device.lock(user)
        logger.info(f"套件执行开始: {suite.name}, 设备: {device.device_id}, 共 {len(executions)} 个用例")

        for idx, execution in enumerate(executions):
            test_case = execution.test_case
            if not test_case:
                execution.status = 'error'
                execution.result = None
                execution.error_message = '用例不存在'
                execution.finished_at = timezone.now()
                execution.save()
                failed += 1
                continue

            try:
                # 更新为运行中
                execution.status = 'running'
                execution.started_at = timezone.now()
                execution.progress = 0
                execution.save()
                send_execution_update(
                    execution.id, status='running', progress=0,
                    message=f'开始执行 ({idx + 1}/{len(executions)})'
                )

                # 确定包名
                if package_name:
                    final_pkg = package_name
                else:
                    final_pkg = test_case.app_package.package_name if test_case.app_package else ""

                execution.progress = 10
                execution.save()
                send_execution_update(
                    execution.id, status='running', progress=10,
                    message='正在准备测试环境'
                )

                executor = AppTestExecutor()
                report_result = executor.run_tests(
                    test_case_id=test_case.id,
                    device_id=device.device_id,
                    package_name=final_pkg,
                    execution_id=execution.id,
                    username=execution.user.username if execution.user else 'unknown',
                )

                execution.refresh_from_db()

                if report_result.get('report_path'):
                    execution.report_path = report_result['report_path']

                test_results = report_result.get('test_results', {})
                execution.total_steps = test_results.get('total', 0)
                execution.passed_steps = test_results.get('passed', 0)
                execution.failed_steps = test_results.get('failed', 0)
                if test_results.get('broken', 0):
                    logger.info(f"检测到 broken 用例 {test_results.get('broken')} 个（已计入失败统计）。")

                execution.status = 'completed'
                if execution.total_steps == 0:
                    execution.result = 'skipped'
                elif execution.failed_steps == 0:
                    execution.result = 'passed'
                else:
                    execution.result = 'failed'
                execution.finished_at = timezone.now()
                execution.duration = (execution.finished_at - execution.started_at).total_seconds()
                execution.progress = 100
                execution.save()

                if execution.result == 'passed':
                    passed += 1
                else:
                    failed += 1

                send_execution_update(
                    execution.id, status=execution.status, progress=100,
                    message='执行完成',
                    report_path=execution.report_path,
                    finished_at=execution.finished_at,
                    result=execution.result,
                )

                logger.info(f"用例 {test_case.name} 执行完成: status={execution.status}, result={execution.result}")

            except Exception as e:
                logger.error(f"用例 {test_case.name} 执行失败: {str(e)}", exc_info=True)
                execution.status = 'error'
                execution.result = None
                execution.error_message = str(e)
                execution.finished_at = timezone.now()
                if execution.started_at:
                    execution.duration = (execution.finished_at - execution.started_at).total_seconds()
                execution.save()
                failed += 1
                send_execution_update(
                    execution.id, status='error',
                    progress=execution.progress or 0,
                    message=str(e),
                    finished_at=execution.finished_at,
                    result=None,
                )

        # 更新套件统计
        suite.execution_status = 'completed'
        if passed == 0 and failed == 0:
            suite.execution_result = 'skipped'
        elif failed == 0:
            suite.execution_result = 'passed'
        else:
            suite.execution_result = 'failed'
        suite.passed_count = passed
        suite.failed_count = failed
        suite.last_run_at = timezone.now()
        suite.save(update_fields=['execution_status', 'execution_result', 'passed_count', 'failed_count', 'last_run_at'])

        logger.info(f"套件执行完成: {suite.name}, 通过: {passed}, 失败: {failed}")

        # 定时任务通知
        if scheduled_task_id:
            try:
                from .models import AppScheduledTask
                st = AppScheduledTask.objects.get(id=scheduled_task_id)
                is_success = failed == 0
                if is_success:
                    st.successful_runs += 1
                else:
                    st.failed_runs += 1
                st.last_result = {
                    'status': suite.execution_status,
                    'result': suite.execution_result,
                    'message': f'通过: {passed}, 失败: {failed}'
                }
                st.save(update_fields=['successful_runs', 'failed_runs', 'last_result'])
                send_scheduled_task_notification(scheduled_task_id, success=is_success)
            except Exception as ne:
                logger.error(f"更新定时任务状态失败: {ne}")

    except AppTestSuite.DoesNotExist:
        logger.error(f"测试套件不存在: {suite_id}")
    except Exception as e:
        logger.error(f"执行套件失败: {str(e)}", exc_info=True)
        if suite:
            suite.execution_status = 'error'
            suite.execution_result = None
            suite.failed_count = failed
            suite.passed_count = passed
            suite.last_run_at = timezone.now()
            suite.save(update_fields=['execution_status', 'execution_result', 'passed_count', 'failed_count', 'last_run_at'])
    finally:
        # 释放设备
        try:
            if device:
                device.refresh_from_db()
                if device.status == 'locked':
                    device.unlock()
                    logger.info(f"设备已释放: {device.device_id}")
        except Exception as e:
            logger.error(f"释放设备失败: {str(e)}")


@shared_task
def check_and_release_expired_devices():
    """
    检查并释放过期锁定的设备
    """
    from .models import AppDevice
    
    try:
        devices = AppDevice.objects.filter(status='locked')
        released_count = 0
        
        for device in devices:
            if device.is_lock_expired():
                device.unlock()
                released_count += 1
                logger.info(f"释放过期锁定的设备: {device.device_id}")
        
        logger.info(f"检查设备锁定完成，释放 {released_count} 个设备")
        
    except Exception as e:
        logger.error(f"检查设备锁定失败: {str(e)}", exc_info=True)

"""Run TestScript CODE content as an independent executable artifact."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import threading
import traceback
from typing import Optional

from django.utils import timezone

from apps.ui_automation.models import TestExecution, TestScript

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 600
MAX_LOG_CHARS = 100_000


def _apply_runtime_overrides(content: str, *, headless: bool, framework: str) -> str:
    """Patch generated/handwritten script for runtime headless flag."""
    text = content or ''
    flag = 'True' if headless else 'False'
    if framework == 'playwright':
        if re.search(r'headless\s*=\s*(True|False)', text):
            text = re.sub(r'headless\s*=\s*(True|False)', f'headless={flag}', text)
        else:
            text = text.replace(
                '.chromium.launch()',
                f'.chromium.launch(headless={flag})',
            )
            text = text.replace(
                '.firefox.launch()',
                f'.firefox.launch(headless={flag})',
            )
            text = text.replace(
                '.webkit.launch()',
                f'.webkit.launch(headless={flag})',
            )
    elif framework == 'selenium':
        if headless:
            if 'add_argument("--headless' not in text and "add_argument('--headless" not in text:
                text = text.replace(
                    'options = Options()',
                    'options = Options()\n    options.add_argument("--headless=new")',
                    1,
                )
            text = text.replace(
                '# options.add_argument("--headless=new")',
                'options.add_argument("--headless=new")',
            )
        else:
            text = re.sub(
                r'^\s*options\.add_argument\(["\']--headless[^"\']*["\']\)\s*$',
                '    # headless disabled for this run',
                text,
                flags=re.MULTILINE,
            )
    return text


_SKIP_COMMENT_PREFIXES = (
    'noqa', 'type:', 'pylint', 'flake8', 'fmt:',
    'options.', 'headless', 'coding', '!',
)


def _inject_execution_logging(content: str) -> str:
    """Ensure scripts print step-level logs even if generated before logging existed."""
    text = content or ''
    has_helper = 'def _testhub_log(' in text

    helper = textwrap.dedent('''\
        import time as _testhub_time
        import traceback as _testhub_tb

        def _testhub_log(msg):
            print(msg, flush=True)

    ''')

    if not has_helper:
        m = re.search(r'\ndef run\s*\(', text)
        if m:
            text = text[: m.start()] + '\n' + helper + text[m.start() :]
        else:
            text = helper + '\n' + text

        def _repl_comment(match: re.Match) -> str:
            indent, comment = match.group(1), match.group(2).strip()
            low = comment.lower()
            if any(low.startswith(p) for p in _SKIP_COMMENT_PREFIXES):
                return match.group(0)
            if comment.startswith(('====', '-----')):
                return match.group(0)
            return f'{indent}_testhub_log({repr("[步骤] " + comment)})'

        text = re.sub(r'^([ \t]+)#\s*(.+)$', _repl_comment, text, flags=re.MULTILINE)

    if "if __name__ == '__main__':" in text and 'def _testhub_main(' not in text:
        # Avoid double-wrapping scripts that already log start/end inside run()
        if '_testhub_main' not in text:
            replaced = re.sub(
                r"if __name__\s*==\s*['\"]__main__['\"]\s*:\s*\n\s*run\(\)\s*\n?",
                textwrap.dedent('''\
                    def _testhub_main():
                        _testhub_log('========== 脚本进程启动 ==========')
                        _t0 = _testhub_time.time()
                        try:
                            run()
                            _testhub_log(f'========== 脚本进程结束(成功) 耗时 {_testhub_time.time()-_t0:.2f}s ==========')
                        except Exception as _e:
                            _testhub_log(f'========== 脚本进程结束(失败) 耗时 {_testhub_time.time()-_t0:.2f}s ==========')
                            _testhub_log(f'错误: {_e}')
                            _testhub_log(_testhub_tb.format_exc())
                            raise


                    if __name__ == '__main__':
                        _testhub_main()

                '''),
                text,
                count=1,
            )
            if replaced != text:
                text = replaced
            elif 'def _testhub_log(' in text and '_testhub_main' not in text:
                # Script has custom __main__; append note only
                text += '\n# testhub: custom __main__ kept as-is\n'

    return text


def _clip(text: str, limit: int = MAX_LOG_CHARS) -> str:
    if not text:
        return ''
    if len(text) <= limit:
        return text
    return text[: limit - 80] + f'\n...[日志过长，已截断，共 {len(text)} 字符]...\n'


def run_script_sync(
    script: TestScript,
    *,
    execution: TestExecution,
    headless: bool = True,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> None:
    """Execute script.content in a subprocess; update execution record."""
    framework = (script.framework or 'playwright').lower()
    content = _apply_runtime_overrides(script.content or '', headless=headless, framework=framework)
    content = _inject_execution_logging(content)
    if not content.strip():
        execution.status = 'FAILED'
        execution.error_message = '脚本内容为空'
        execution.finished_at = timezone.now()
        execution.total_cases = 1
        execution.failed_cases = 1
        execution.save()
        return

    tmp_path = None
    logs = [
        f'========== 执行独立脚本 #{script.id} ==========',
        f'名称: {script.name}',
        f'框架: {framework}',
        f'无头: {headless}',
        f'超时: {timeout}s',
        '',
    ]
    started = timezone.now()
    execution.status = 'RUNNING'
    execution.started_at = started
    execution.engine = framework
    execution.headless = headless
    execution.total_cases = 1
    execution.save(update_fields=[
        'status', 'started_at', 'engine', 'headless', 'total_cases',
    ])

    try:
        fd, tmp_path = tempfile.mkstemp(suffix='.py', prefix=f'testhub_script_{script.id}_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)

        logs.append(f'临时文件: {tmp_path}')
        logs.append('开始运行...')
        logs.append('')
        proc = subprocess.run(
            [sys.executable, '-u', tmp_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            cwd=tempfile.gettempdir(),
            env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'},
        )
        if proc.stdout:
            logs.append('--- 执行输出 (stdout) ---')
            logs.append(_clip(proc.stdout))
        else:
            logs.append('--- 执行输出 (stdout) ---')
            logs.append('(无输出)')
        if proc.stderr:
            logs.append('')
            logs.append('--- 错误输出 (stderr) ---')
            logs.append(_clip(proc.stderr))

        finished = timezone.now()
        execution.finished_at = finished
        execution.duration = (finished - started).total_seconds()
        full_log = '\n'.join(logs)
        execution.result_data = {
            'script_id': script.id,
            'script_name': script.name,
            'returncode': proc.returncode,
            'logs': full_log,
            'stdout': _clip(proc.stdout or ''),
            'stderr': _clip(proc.stderr or ''),
        }

        if proc.returncode == 0:
            execution.status = 'SUCCESS'
            execution.passed_cases = 1
            execution.failed_cases = 0
            execution.error_message = ''
            logs.append('')
            logs.append(f'✓ 脚本执行成功 (exit=0, 耗时 {execution.duration:.2f}s)')
        else:
            execution.status = 'FAILED'
            execution.passed_cases = 0
            execution.failed_cases = 1
            err_tail = (proc.stderr or proc.stdout or f'exit code {proc.returncode}')
            execution.error_message = _clip(err_tail, 4000)
            logs.append('')
            logs.append(f'✗ 脚本执行失败 (exit={proc.returncode}, 耗时 {execution.duration:.2f}s)')
        execution.result_data['logs'] = '\n'.join(logs)
    except subprocess.TimeoutExpired as exc:
        finished = timezone.now()
        out = ''
        err = ''
        try:
            out = exc.stdout.decode('utf-8', errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
            err = exc.stderr.decode('utf-8', errors='replace') if isinstance(exc.stderr, bytes) else (exc.stderr or '')
        except Exception:
            pass
        if out:
            logs.append('--- 执行输出 (stdout) ---')
            logs.append(_clip(out))
        if err:
            logs.append('--- 错误输出 (stderr) ---')
            logs.append(_clip(err))
        logs.append(f'执行超时（>{timeout}s）')
        execution.status = 'FAILED'
        execution.failed_cases = 1
        execution.passed_cases = 0
        execution.finished_at = finished
        execution.duration = (finished - started).total_seconds()
        execution.error_message = f'脚本执行超时（>{timeout}s）'
        execution.result_data = {'script_id': script.id, 'logs': '\n'.join(logs)}
    except Exception as exc:
        finished = timezone.now()
        logs.append(traceback.format_exc())
        execution.status = 'FAILED'
        execution.failed_cases = 1
        execution.passed_cases = 0
        execution.finished_at = finished
        execution.duration = (finished - started).total_seconds()
        execution.error_message = str(exc)
        execution.result_data = {'script_id': script.id, 'logs': '\n'.join(logs)}
        logger.exception('run_script_sync failed script_id=%s', script.id)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        execution.save()


def start_script_execution(
    script: TestScript,
    *,
    executed_by=None,
    headless: bool = True,
    browser: str = 'chrome',
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> TestExecution:
    """Create TestExecution and run script in a background thread."""
    env_map = {
        'chrome': 'CHROME',
        'chromium': 'CHROME',
        'firefox': 'FIREFOX',
        'safari': 'SAFARI',
        'edge': 'EDGE',
    }
    execution = TestExecution.objects.create(
        project=script.project,
        test_script=script,
        test_suite=None,
        environment=env_map.get((browser or 'chrome').lower(), 'CHROME'),
        status='PENDING',
        engine=(script.framework or 'playwright'),
        browser=browser or 'chrome',
        headless=bool(headless),
        executed_by=executed_by,
        total_cases=1,
    )

    def _worker():
        try:
            run_script_sync(script, execution=execution, headless=bool(headless), timeout=timeout)
        except Exception:
            logger.exception('script execution worker failed id=%s', execution.id)

    threading.Thread(target=_worker, daemon=True).start()
    return execution

"""Generate Playwright / Selenium source from TestCase; sync status for linked scripts."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Literal, Tuple

from apps.ui_automation.models import TestCase, TestScript


def _py_str(text: Any) -> str:
    """Safe Python string literal via repr (quotes / newlines / unicode)."""
    return repr('' if text is None else str(text))


def _comment_line(prefix: str, text: str) -> str:
    """Single-line Python comment; multiline descriptions must not leak as code."""
    safe = ' '.join(str(text or '').replace('\r', '\n').split())
    if len(safe) > 160:
        safe = safe[:157] + '...'
    return f'{prefix}# {safe}' if safe else f'{prefix}#'


def content_hash(content: str) -> str:
    return hashlib.sha256((content or '').encode('utf-8')).hexdigest()


def _locator_expr_playwright(strategy: str, value: str) -> str:
    s = (strategy or 'css').lower()
    v = value or ''
    if s == 'id':
        raw = v if str(v).startswith('#') else f'#{v}'
        return f'page.locator({_py_str(raw)})'
    if s in ('css', 'css selector'):
        return f'page.locator({_py_str(v)})'
    if s == 'xpath':
        return f'page.locator({_py_str(f"xpath={v}")})'
    if s == 'text':
        return f'page.get_by_text({_py_str(v)})'
    if s == 'name':
        return f'page.locator({_py_str(f"[name=\"{v}\"]")})'
    if s == 'placeholder':
        return f'page.get_by_placeholder({_py_str(v)})'
    if s == 'role':
        if '|' in v:
            role, name = v.split('|', 1)
            return f'page.get_by_role({_py_str(role)}, name={_py_str(name)})'
        return f'page.get_by_role({_py_str(v)})'
    if s == 'label':
        return f'page.get_by_label({_py_str(v)})'
    if s == 'title':
        return f'page.get_by_title({_py_str(v)})'
    if s in ('test-id', 'testid'):
        return f'page.get_by_test_id({_py_str(v)})'
    return f'page.locator({_py_str(v)})'


def _locator_expr_selenium(strategy: str, value: str) -> str:
    s = (strategy or 'css').lower()
    v = value or ''
    if s == 'id':
        return f'driver.find_element(By.ID, {_py_str(v)})'
    if s in ('css', 'css selector'):
        return f'driver.find_element(By.CSS_SELECTOR, {_py_str(v)})'
    if s == 'xpath':
        return f'driver.find_element(By.XPATH, {_py_str(v)})'
    if s == 'name':
        return f'driver.find_element(By.NAME, {_py_str(v)})'
    if s == 'text':
        safe = (v or '').replace('"', '')
        xpath = f'//*[contains(text(), "{safe}")]'
        return f'driver.find_element(By.XPATH, {_py_str(xpath)})'
    return f'driver.find_element(By.CSS_SELECTOR, {_py_str(v)})'


def _emit_hover(lines: list, loc: str, indent: str = '        ') -> None:
    """Strict hover — failure fails the script."""
    target = f'{loc}.first'
    lines.append(f'{indent}try:')
    lines.append(f'{indent}    {target}.scroll_into_view_if_needed(timeout=2000)')
    lines.append(f'{indent}except Exception:')
    lines.append(f'{indent}    pass')
    lines.append(f'{indent}{target}.hover(timeout=8000)')


def _emit_strict_click(lines: list, loc: str, *, force: bool = False, indent: str = '        ') -> None:
    """Strict click: visible → force → JS; still raise if all fail."""
    js_click = (
        "el => { const a = el.closest && el.closest('a'); (a || el).click(); }"
    )
    lines.append(f'{indent}try:')
    if force:
        lines.append(f'{indent}    {loc}.first.click(force=True, timeout=8000)')
    else:
        lines.append(f'{indent}    {loc}.locator("visible=true").first.click(timeout=8000)')
    lines.append(f'{indent}except Exception:')
    lines.append(f'{indent}    try:')
    lines.append(f'{indent}        {loc}.first.click(force=True, timeout=5000)')
    lines.append(f'{indent}    except Exception:')
    lines.append(f'{indent}        {loc}.first.evaluate({_py_str(js_click)}, timeout=3000)')


def _find_post_click_navigation(steps: list, idx: int):
    """If click is followed by switchTab + wait(http), return (url, absorb_indices)."""
    absorb: list = []
    nav_url = None
    for j in range(idx + 1, min(idx + 4, len(steps))):
        stj = steps[j]
        action = stj.action_type
        if action == 'switchTab':
            absorb.append(j)
            continue
        if action == 'wait' and str(stj.input_value or '').startswith('http'):
            nav_url = str(stj.input_value).strip()
            absorb.append(j)
            break
        if action == 'hover':
            continue
        break
    if nav_url:
        return nav_url, absorb
    return None, []


def _absorb_following_switch_tabs(steps: list, idx: int) -> list:
    absorb = []
    for j in range(idx + 1, min(idx + 3, len(steps))):
        if steps[j].action_type == 'switchTab':
            absorb.append(j)
            continue
        break
    return absorb


def _emit_open_recorded_url(lines: list, url: str, indent: str = '        ', loc: str = '') -> None:
    """Open recorded article URL: prefer real click (Referer/Cookie), else goto+referer."""
    js_click = (
        "el => { const a = el.closest && el.closest('a'); (a || el).click(); }"
    )
    lines.append(_comment_line(indent, 'open recorded link URL (click first; else goto+referer)'))
    lines.append(f'{indent}_ref = page.url if page else ""')
    lines.append(f'{indent}_opened = False')
    if loc:
        lines.append(f'{indent}try:')
        lines.append(f'{indent}    with context.expect_page(timeout=8000) as _ni:')
        lines.append(f'{indent}        try:')
        lines.append(f'{indent}            {loc}.locator("visible=true").first.click(timeout=5000)')
        lines.append(f'{indent}        except Exception:')
        lines.append(f'{indent}            try:')
        lines.append(f'{indent}                {loc}.first.click(force=True, timeout=3000)')
        lines.append(f'{indent}            except Exception:')
        lines.append(f'{indent}                {loc}.first.evaluate({_py_str(js_click)}, timeout=3000)')
        lines.append(f'{indent}    page = _ni.value')
        lines.append(f"{indent}    page.wait_for_load_state('domcontentloaded')")
        lines.append(f'{indent}    _opened = True')
        lines.append(f'{indent}except Exception:')
        lines.append(f'{indent}    _opened = False')
    lines.append(f'{indent}if not _opened:')
    lines.append(f'{indent}    page = context.new_page()')
    lines.append(f'{indent}    if _ref.startswith("http"):')
    lines.append(f'{indent}        page.goto({_py_str(url)}, referer=_ref)')
    lines.append(f'{indent}    else:')
    lines.append(f'{indent}        page.goto({_py_str(url)})')
    lines.append(f"{indent}    page.wait_for_load_state('domcontentloaded')")


def _emit_click_open_tab(lines: list, loc: str, indent: str = '        ') -> None:
    """Click expected to open a new tab; prefer real click, else goto href with referer."""
    js_href = (
        "el => { const a = el.closest && el.closest('a[href]'); "
        "return a ? (a.href || '') : ''; }"
    )
    js_click = (
        "el => { const a = el.closest && el.closest('a'); (a || el).click(); }"
    )
    lines.append(f'{indent}_ref = page.url if page else ""')
    lines.append(f'{indent}_href = ""')
    lines.append(f'{indent}try:')
    lines.append(
        f'{indent}    _href = {loc}.first.evaluate({_py_str(js_href)}, timeout=3000) or ""'
    )
    lines.append(f'{indent}except Exception:')
    lines.append(f'{indent}    _href = ""')
    lines.append(f'{indent}_opened = False')
    lines.append(f'{indent}try:')
    lines.append(f'{indent}    with context.expect_page(timeout=8000) as _ni:')
    lines.append(f'{indent}        try:')
    lines.append(f'{indent}            {loc}.locator("visible=true").first.click(timeout=5000)')
    lines.append(f'{indent}        except Exception:')
    lines.append(f'{indent}            try:')
    lines.append(f'{indent}                {loc}.first.click(force=True, timeout=3000)')
    lines.append(f'{indent}            except Exception:')
    lines.append(f'{indent}                {loc}.first.evaluate({_py_str(js_click)}, timeout=3000)')
    lines.append(f'{indent}    page = _ni.value')
    lines.append(f"{indent}    page.wait_for_load_state('domcontentloaded')")
    lines.append(f'{indent}    _opened = True')
    lines.append(f'{indent}except Exception:')
    lines.append(f'{indent}    _opened = False')
    lines.append(f'{indent}if not _opened and _href:')
    lines.append(f'{indent}    page = context.new_page()')
    lines.append(f'{indent}    if _ref.startswith("http"):')
    lines.append(f'{indent}        page.goto(_href, referer=_ref)')
    lines.append(f'{indent}    else:')
    lines.append(f'{indent}        page.goto(_href)')
    lines.append(f"{indent}    page.wait_for_load_state('domcontentloaded')")
    lines.append(f'{indent}elif not _opened:')
    lines.append(f'{indent}    raise RuntimeError("recorded click expected new tab but none opened and no href")')


def _emit_step_log(lines: list, step_no: int, action: str, desc: str, indent: str = '        ') -> None:
    lines.append(
        f'{indent}_testhub_log('
        f'{_py_str(f"========== 步骤 {step_no}: {action} ==========")}'
        f')'
    )
    if desc:
        lines.append(f'{indent}_testhub_log({_py_str(f"  说明: {desc}")})')


def _emit_step_ok(lines: list, detail: str = '', indent: str = '        ') -> None:
    msg = f'  ✓ 成功{(" | " + detail) if detail else ""}'
    lines.append(f'{indent}_testhub_log({_py_str(msg)})')
    lines.append(f'{indent}try:')
    lines.append(f'{indent}    _testhub_log(f"  当前URL: {{page.url}}")')
    lines.append(f'{indent}except Exception:')
    lines.append(f'{indent}    pass')


def generate_playwright_python(test_case: TestCase, base_url: str = '') -> str:
    lines = [
        '"""Auto-generated Playwright script from TestHub TestCase."""',
        'from playwright.sync_api import sync_playwright',
        'import time as _testhub_time',
        'import traceback as _testhub_tb',
        '',
        '',
        'def _testhub_log(msg):',
        '    print(msg, flush=True)',
        '',
        '',
        'def run():',
        '    _testhub_log("========== 脚本开始执行 ==========")',
        '    _run_t0 = _testhub_time.time()',
        '    page = None',
        '    browser = None',
        '    try:',
        '        with sync_playwright() as p:',
        '            browser = p.chromium.launch(headless=False)',
        '            context = browser.new_context(',
        '                locale="zh-CN",',
        '                user_agent=(',
        '                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "',
        '                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"',
        '                ),',
        '                extra_http_headers={"Accept-Language": "zh-CN,zh;q=0.9"},',
        '            )',
        '            context.add_init_script(',
        '                "Object.defineProperty(navigator, \'webdriver\', {get: () => undefined});"',
        '            )',
        '            page = context.new_page()',
        '            _testhub_log("  ✓ 浏览器已启动")',
    ]
    indent = '            '
    if base_url:
        lines.append(f'{indent}_testhub_log({_py_str(f"导航到项目地址: {base_url}")})')
        lines.append(f'{indent}page.goto({_py_str(base_url)})')
        lines.append(f"{indent}page.wait_for_load_state('domcontentloaded')")
        lines.append(f'{indent}_testhub_log(f"  ✓ 页面就绪 | URL={{page.url}}")')

    steps = list(test_case.steps.select_related('element', 'element__locator_strategy').all())
    skip_indices = set()
    visible_step_no = 0
    for idx, step in enumerate(steps):
        if idx in skip_indices:
            continue
        visible_step_no += 1
        comment = step.description or f'step {step.step_number}'
        action = step.action_type
        _emit_step_log(lines, visible_step_no, action, comment, indent=indent)
        if action == 'switchTab':
            lines.append(f'{indent}page = context.pages[-1]')
            lines.append(f'{indent}page.bring_to_front()')
            lines.append(f"{indent}page.wait_for_load_state('domcontentloaded')")
            _emit_step_ok(lines, '切换到最新标签页', indent=indent)
            continue
        if action == 'wait':
            if step.input_value and str(step.input_value).startswith('http'):
                lines.append(f'{indent}page.goto({_py_str(step.input_value)})')
                lines.append(f"{indent}page.wait_for_load_state('domcontentloaded')")
                _emit_step_ok(lines, f'导航 {step.input_value}', indent=indent)
            else:
                ms = step.wait_time or 1000
                lines.append(f'{indent}page.wait_for_timeout({ms})')
                _emit_step_ok(lines, f'等待 {ms}ms', indent=indent)
            continue
        if action == 'screenshot':
            lines.append(f'{indent}page.screenshot(path={_py_str(f"step_{step.step_number}.png")})')
            _emit_step_ok(lines, '截图', indent=indent)
            continue
        if not step.element:
            lines.append(f'{indent}_testhub_log({_py_str(f"  ✗ 跳过: 无元素绑定 ({action})")})')
            lines.append(f'{indent}raise RuntimeError({_py_str(f"步骤无元素: {comment}")})')
            continue
        strategy_name = 'css'
        if step.element.locator_strategy_id:
            strategy_name = step.element.locator_strategy.name or 'css'
        loc_val = step.element.locator_value or ''
        loc = _locator_expr_playwright(strategy_name, loc_val)
        force = bool(getattr(step.element, 'force_action', False))
        lines.append(
            f'{indent}_testhub_log('
            f'{_py_str(f"  定位器: {strategy_name}={loc_val}")}'
            f')'
        )
        if action == 'click':
            click_href = (step.input_value or '').strip()
            if click_href.startswith('http://') or click_href.startswith('https://'):
                _emit_open_recorded_url(lines, click_href, indent=indent, loc=loc)
                _emit_step_ok(lines, f'打开链接 {click_href}', indent=indent)
                skip_indices.update(_absorb_following_switch_tabs(steps, idx))
                for j in range(idx + 1, min(idx + 4, len(steps))):
                    stj = steps[j]
                    if stj.action_type == 'wait' and str(stj.input_value or '').startswith('http'):
                        if str(stj.input_value).strip() == click_href or j in skip_indices:
                            skip_indices.add(j)
                        break
                    if stj.action_type == 'switchTab':
                        continue
                    break
                continue
            nav_url, absorb = _find_post_click_navigation(steps, idx)
            if nav_url:
                _emit_open_recorded_url(lines, nav_url, indent=indent, loc=loc)
                _emit_step_ok(lines, f'打开链接 {nav_url}', indent=indent)
                skip_indices.update(absorb)
                continue
            tab_absorb = _absorb_following_switch_tabs(steps, idx)
            if tab_absorb:
                _emit_click_open_tab(lines, loc, indent=indent)
                _emit_step_ok(lines, '点击并切换新标签', indent=indent)
                skip_indices.update(tab_absorb)
                continue
            _emit_strict_click(lines, loc, force=force, indent=indent)
            _emit_step_ok(lines, '点击', indent=indent)
        elif action == 'fill':
            target = f'{loc}.first'
            if force:
                lines.append(f'{indent}{target}.fill({_py_str(step.input_value)}, force=True)')
            else:
                lines.append(f'{indent}{target}.fill({_py_str(step.input_value)})')
            _emit_step_ok(lines, '输入', indent=indent)
        elif action == 'hover':
            _emit_hover(lines, loc, indent=indent)
            _emit_step_ok(lines, '悬停', indent=indent)
        elif action == 'getText':
            lines.append(f'{indent}_txt = {loc}.first.inner_text()')
            lines.append(f'{indent}_testhub_log(f"  文本: {{_txt}}")')
            _emit_step_ok(lines, '获取文本', indent=indent)
        elif action == 'assert':
            lines.append(
                f'{indent}assert {_py_str(step.assert_value)} in ({loc}.first.inner_text() or "")'
            )
            _emit_step_ok(lines, '断言通过', indent=indent)
        elif action == 'scroll':
            if step.input_value and ',' in str(step.input_value):
                parts = str(step.input_value).split(',', 1)
                try:
                    sx, sy = int(float(parts[0])), int(float(parts[1]))
                except (TypeError, ValueError):
                    sx, sy = 0, 0
                lines.append(
                    f'{indent}page.evaluate("window.scrollTo({sx}, {sy})")'
                )
                _emit_step_ok(lines, f'滚动到 ({sx}, {sy})', indent=indent)
            else:
                lines.append(f'{indent}{loc}.first.scroll_into_view_if_needed()')
                _emit_step_ok(lines, '滚动到元素', indent=indent)
        else:
            lines.append(f'{indent}_testhub_log({_py_str(f"  ✗ 不支持的动作: {action}")})')
            lines.append(f'{indent}raise RuntimeError({_py_str(f"unsupported action: {action}")})')

    lines.extend([
        f'{indent}_testhub_log(f"========== 全部步骤成功 耗时 {{_testhub_time.time()-_run_t0:.2f}}s ==========")',
        '            browser.close()',
        '    except Exception as _err:',
        '        _testhub_log(f"========== 脚本执行失败 耗时 {_testhub_time.time()-_run_t0:.2f}s ==========")',
        '        _testhub_log(f"错误: {_err}")',
        '        try:',
        '            if page is not None:',
        '                _testhub_log(f"失败时URL: {page.url}")',
        '        except Exception:',
        '            pass',
        '        _testhub_log(_testhub_tb.format_exc())',
        '        try:',
        '            if browser is not None:',
        '                browser.close()',
        '        except Exception:',
        '            pass',
        '        raise',
        '',
        '',
        "if __name__ == '__main__':",
        '    run()',
        '',
    ])
    return '\n'.join(lines)


def generate_selenium_python(test_case: TestCase, base_url: str = '') -> str:
    lines = [
        '"""Auto-generated Selenium script from TestHub TestCase."""',
        'from selenium import webdriver',
        'from selenium.webdriver.common.by import By',
        'from selenium.webdriver.chrome.options import Options',
        'import time',
        'import traceback as _testhub_tb',
        '',
        '',
        'def _testhub_log(msg):',
        '    print(msg, flush=True)',
        '',
        '',
        'def run():',
        '    _testhub_log("========== 脚本开始执行 ==========")',
        '    _run_t0 = time.time()',
        '    options = Options()',
        '    # options.add_argument("--headless=new")',
        '    driver = webdriver.Chrome(options=options)',
        '    driver.implicitly_wait(10)',
        '    try:',
    ]
    indent = '        '
    if base_url:
        lines.append(f'{indent}_testhub_log({_py_str(f"导航到: {base_url}")})')
        lines.append(f'{indent}driver.get({_py_str(base_url)})')

    step_no = 0
    for step in test_case.steps.select_related('element', 'element__locator_strategy').all():
        step_no += 1
        comment = step.description or f'step {step.step_number}'
        action = step.action_type
        lines.append(f'{indent}_testhub_log({_py_str(f"========== 步骤 {step_no}: {action} ==========")})')
        lines.append(f'{indent}_testhub_log({_py_str(f"  说明: {comment}")})')
        if action == 'wait':
            if step.input_value and str(step.input_value).startswith('http'):
                lines.append(f'{indent}driver.get({_py_str(step.input_value)})')
                lines.append(f'{indent}_testhub_log({_py_str("  ✓ 导航成功")})')
            else:
                sec = max(0.1, (step.wait_time or 1000) / 1000.0)
                lines.append(f'{indent}time.sleep({sec})')
                lines.append(f'{indent}_testhub_log({_py_str(f"  ✓ 等待 {sec}s")})')
            continue
        if not step.element:
            lines.append(f'{indent}raise RuntimeError({_py_str(f"步骤无元素: {comment}")})')
            continue
        strategy_name = 'css'
        if step.element.locator_strategy_id:
            strategy_name = step.element.locator_strategy.name or 'css'
        loc_val = step.element.locator_value or ''
        loc = _locator_expr_selenium(strategy_name, loc_val)
        lines.append(
            f'{indent}_testhub_log('
            f'{_py_str(f"  定位器: {strategy_name}={loc_val}")}'
            f')'
        )
        if action == 'click':
            lines.append(f'{indent}{loc}.click()')
            lines.append(f'{indent}_testhub_log({_py_str("  ✓ 点击成功")})')
        elif action == 'fill':
            lines.append(f'{indent}el = {loc}')
            lines.append(f'{indent}el.clear()')
            lines.append(f'{indent}el.send_keys({_py_str(step.input_value)})')
            lines.append(f'{indent}_testhub_log({_py_str("  ✓ 输入成功")})')
        else:
            lines.append(f'{indent}raise RuntimeError({_py_str(f"unsupported action: {action}")})')

    lines.extend([
        f'{indent}_testhub_log(f"========== 全部步骤成功 耗时 {{time.time()-_run_t0:.2f}}s ==========")',
        '    except Exception as _err:',
        '        _testhub_log(f"========== 脚本执行失败 ==========")',
        '        _testhub_log(f"错误: {_err}")',
        '        _testhub_log(_testhub_tb.format_exc())',
        '        raise',
        '    finally:',
        '        driver.quit()',
        '',
        '',
        "if __name__ == '__main__':",
        '    run()',
        '',
    ])
    return '\n'.join(lines)


def generate_script_content(
    test_case: TestCase,
    engine: Literal['playwright', 'selenium'] = 'playwright',
) -> Tuple[str, str]:
    """Return (content, framework)."""
    base_url = getattr(test_case.project, 'base_url', '') or ''
    if engine == 'selenium':
        return generate_selenium_python(test_case, base_url), 'selenium'
    return generate_playwright_python(test_case, base_url), 'playwright'


SYNC_STATUS_LABELS = {
    'independent': '独立脚本',
    'synced': '与用例一致',
    'case_ahead': '用例已变更',
    'script_ahead': '脚本已修改',
    'diverged': '双方均已变更',
}


def get_script_sync_status(script: TestScript) -> Dict[str, Any]:
    """Compare linked script content against what the case would generate now."""
    if not script.source_test_case_id:
        return {
            'status': 'independent',
            'label': SYNC_STATUS_LABELS['independent'],
            'source_test_case_id': None,
            'inconsistent': False,
        }

    case = script.source_test_case
    engine = (script.framework or 'playwright').lower()
    if engine not in ('playwright', 'selenium'):
        engine = 'playwright'
    expected, _ = generate_script_content(case, engine)  # type: ignore[arg-type]
    expected_hash = content_hash(expected)
    current_hash = content_hash(script.content or '')
    snapshot = (script.synced_content_hash or '').strip()

    if current_hash == expected_hash:
        status = 'synced'
    elif snapshot and current_hash == snapshot and expected_hash != snapshot:
        status = 'case_ahead'
    elif snapshot and current_hash != snapshot and expected_hash == snapshot:
        status = 'script_ahead'
    else:
        status = 'diverged'

    return {
        'status': status,
        'label': SYNC_STATUS_LABELS[status],
        'source_test_case_id': case.id,
        'source_test_case_name': case.name,
        'inconsistent': status in ('case_ahead', 'script_ahead', 'diverged'),
        'current_hash': current_hash,
        'expected_hash': expected_hash,
        'synced_content_hash': snapshot,
    }


def export_testcase_to_script(
    test_case: TestCase,
    engine: Literal['playwright', 'selenium'] = 'playwright',
    *,
    force: bool = False,
) -> Tuple[TestScript, Dict[str, Any]]:
    """Create or optionally overwrite the linked script.

    - 无配套脚本：创建并写入同步快照
    - 已有脚本且内容一致：仅刷新快照/元数据
    - 已有脚本且不一致：默认不覆盖（force=False），返回 skipped
    - force=True：用用例重新生成并覆盖
    """
    content, framework = generate_script_content(test_case, engine)
    digest = content_hash(content)
    name = f'{test_case.name} ({framework})'
    description = f'由用例 #{test_case.id} 生成的独立脚本（可单独运行）'

    script = TestScript.objects.filter(source_test_case=test_case).first()
    meta: Dict[str, Any] = {
        'created': False,
        'updated': False,
        'skipped': False,
        'force': force,
    }

    if script is None:
        script = TestScript.objects.create(
            project=test_case.project,
            name=name,
            description=description,
            script_type='CODE',
            content=content,
            language='python',
            framework=framework,
            source_test_case=test_case,
            synced_content_hash=digest,
        )
        meta['created'] = True
        meta['sync_status'] = get_script_sync_status(script)
        return script, meta

    current_hash = content_hash(script.content or '')
    if current_hash == digest:
        script.synced_content_hash = digest
        script.name = name
        script.description = description
        script.framework = framework
        script.save(update_fields=[
            'synced_content_hash', 'name', 'description', 'framework', 'updated_at',
        ])
        meta['updated'] = True
        meta['sync_status'] = get_script_sync_status(script)
        return script, meta

    if not force:
        meta['skipped'] = True
        meta['sync_status'] = get_script_sync_status(script)
        meta['message'] = '脚本与用例不一致，已跳过覆盖；请显式同步（force=true）'
        return script, meta

    script.project = test_case.project
    script.name = name
    script.description = description
    script.script_type = 'CODE'
    script.content = content
    script.language = 'python'
    script.framework = framework
    script.synced_content_hash = digest
    script.save(update_fields=[
        'project', 'name', 'description', 'script_type', 'content',
        'language', 'framework', 'synced_content_hash', 'updated_at',
    ])
    meta['updated'] = True
    meta['sync_status'] = get_script_sync_status(script)
    return script, meta

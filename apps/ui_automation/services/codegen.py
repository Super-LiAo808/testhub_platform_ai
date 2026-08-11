"""Generate Playwright / Selenium source from TestCase."""
from __future__ import annotations

from typing import Literal

from apps.ui_automation.models import TestCase, TestScript


def _escape(text: str) -> str:
    return (text or '').replace('\\', '\\\\').replace("'", "\\'")


def _locator_expr_playwright(strategy: str, value: str) -> str:
    s = (strategy or 'css').lower()
    v = _escape(value)
    if s == 'id':
        return f"page.locator('#{v}')"
    if s in ('css', 'css selector'):
        return f"page.locator('{v}')"
    if s == 'xpath':
        return f"page.locator('xpath={v}')"
    if s == 'text':
        return f"page.get_by_text('{v}')"
    if s == 'name':
        return f"page.locator('[name=\"{v}\"]')"
    if s == 'placeholder':
        return f"page.get_by_placeholder('{v}')"
    if s == 'role':
        if '|' in value:
            role, name = value.split('|', 1)
            return f"page.get_by_role('{_escape(role)}', name='{_escape(name)}')"
        return f"page.get_by_role('{v}')"
    if s == 'label':
        return f"page.get_by_label('{v}')"
    if s == 'title':
        return f"page.get_by_title('{v}')"
    if s in ('test-id', 'testid'):
        return f"page.get_by_test_id('{v}')"
    return f"page.locator('{v}')"


def _locator_expr_selenium(strategy: str, value: str) -> str:
    s = (strategy or 'css').lower()
    v = _escape(value)
    if s == 'id':
        return f"driver.find_element(By.ID, '{v}')"
    if s in ('css', 'css selector'):
        return f"driver.find_element(By.CSS_SELECTOR, '{v}')"
    if s == 'xpath':
        return f"driver.find_element(By.XPATH, '{v}')"
    if s == 'name':
        return f"driver.find_element(By.NAME, '{v}')"
    if s == 'text':
        return f"driver.find_element(By.XPATH, \"//*[contains(text(), '{v}')]\")"
    return f"driver.find_element(By.CSS_SELECTOR, '{v}')"


def generate_playwright_python(test_case: TestCase, base_url: str = '') -> str:
    lines = [
        '"""Auto-generated Playwright script from TestHub TestCase."""',
        'from playwright.sync_api import sync_playwright',
        '',
        '',
        'def run():',
        '    with sync_playwright() as p:',
        "        browser = p.chromium.launch(headless=False)",
        '        page = browser.new_page()',
    ]
    if base_url:
        lines.append(f"        page.goto('{_escape(base_url)}')")

    for step in test_case.steps.select_related('element', 'element__locator_strategy').all():
        comment = step.description or f'step {step.step_number}'
        lines.append(f'        # {comment}')
        action = step.action_type
        if action == 'wait':
            # navigation encoded as wait with URL
            if step.input_value and str(step.input_value).startswith('http'):
                lines.append(f"        page.goto('{_escape(step.input_value)}')")
            else:
                ms = step.wait_time or 1000
                lines.append(f'        page.wait_for_timeout({ms})')
            continue
        if action == 'screenshot':
            lines.append(f"        page.screenshot(path='step_{step.step_number}.png')")
            continue
        if action == 'switchTab':
            idx = (step.input_value or '').strip()
            if idx.isdigit():
                lines.append(f'        page = context.pages[{idx}]')
            else:
                lines.append('        page = context.pages[-1]')
            lines.append('        page.bring_to_front()')
            continue
        if not step.element:
            lines.append(f'        # skipped: no element for {action}')
            continue
        loc = _locator_expr_playwright(step.element.locator_strategy.name, step.element.locator_value)
        if action == 'click':
            lines.append(f'        {loc}.click()')
        elif action == 'fill':
            lines.append(f"        {loc}.fill('{_escape(step.input_value)}')")
        elif action == 'hover':
            lines.append(f'        {loc}.hover()')
        elif action == 'waitFor':
            lines.append(f'        {loc}.wait_for()')
        elif action == 'assert':
            lines.append(f'        assert {loc}.is_visible()')
        else:
            lines.append(f'        # unsupported action: {action}')

    lines.extend([
        '        browser.close()',
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
        'import time',
        'from selenium import webdriver',
        'from selenium.webdriver.common.by import By',
        '',
        '',
        'def run():',
        '    driver = webdriver.Chrome()',
    ]
    if base_url:
        lines.append(f"    driver.get('{_escape(base_url)}')")

    for step in test_case.steps.select_related('element', 'element__locator_strategy').all():
        comment = step.description or f'step {step.step_number}'
        lines.append(f'    # {comment}')
        action = step.action_type
        if action == 'wait':
            if step.input_value and str(step.input_value).startswith('http'):
                lines.append(f"    driver.get('{_escape(step.input_value)}')")
            else:
                lines.append(f'    time.sleep({(step.wait_time or 1000) / 1000.0})')
            continue
        if not step.element:
            lines.append(f'    # skipped: no element for {action}')
            continue
        loc = _locator_expr_selenium(step.element.locator_strategy.name, step.element.locator_value)
        if action == 'click':
            lines.append(f'    {loc}.click()')
        elif action == 'fill':
            lines.append(f"    el = {loc}")
            lines.append('    el.clear()')
            lines.append(f"    el.send_keys('{_escape(step.input_value)}')")
        else:
            lines.append(f'    # unsupported action: {action}')

    lines.extend([
        '    driver.quit()',
        '',
        '',
        "if __name__ == '__main__':",
        '    run()',
        '',
    ])
    return '\n'.join(lines)


def export_testcase_to_script(
    test_case: TestCase,
    engine: Literal['playwright', 'selenium'] = 'playwright',
) -> TestScript:
    base_url = getattr(test_case.project, 'base_url', '') or ''
    if engine == 'selenium':
        content = generate_selenium_python(test_case, base_url)
        framework = 'selenium'
    else:
        content = generate_playwright_python(test_case, base_url)
        framework = 'playwright'

    script = TestScript.objects.create(
        project=test_case.project,
        name=f'{test_case.name} ({framework})',
        description=f'从用例 #{test_case.id} 自动导出',
        script_type='CODE',
        content=content,
        language='python',
        framework=framework,
    )
    return script

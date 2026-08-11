"""Scan a web page with Playwright and extract interactive element candidates."""
from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Global Chromium spawn limit (shared across Daphne workers in-process only).
_SCAN_MAX_CONCURRENT = max(1, int(os.environ.get('UI_SCAN_MAX_CONCURRENT', '2') or 2))
# 排队等待扫描槽位（秒）
_SCAN_ACQUIRE_TIMEOUT = max(5.0, float(os.environ.get('UI_SCAN_ACQUIRE_TIMEOUT', '120') or 120))
# 单页 Playwright 导航/抽取超时（毫秒），默认 3 分钟，上限 10 分钟
_SCAN_PAGE_TIMEOUT_MS = max(
    30000,
    min(int(os.environ.get('UI_SCAN_PAGE_TIMEOUT_MS', '180000') or 180000), 600000),
)
# 进程总等待相对 page timeout 的额外缓冲（秒）
_SCAN_PROCESS_BUFFER_S = max(30.0, float(os.environ.get('UI_SCAN_PROCESS_BUFFER_S', '120') or 120))
_SCAN_FORCE_HEADLESS = (os.environ.get('UI_SCAN_FORCE_HEADLESS', '1') or '1').strip().lower() not in (
    '0', 'false', 'no',
)


class PageScanPartialError(RuntimeError):
    """扫描未完整成功，但已拿到部分候选元素。"""

    def __init__(self, message: str, data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.data = data or {}
_scan_sema = threading.BoundedSemaphore(_SCAN_MAX_CONCURRENT)
_scan_active_lock = threading.Lock()
_scan_active = 0

# Injected into the page: returns list of element dicts
_EXTRACT_JS = r"""
() => {
  const SELECTOR = [
    'a[href]',
    'button',
    'input:not([type="hidden"])',
    'textarea',
    'select',
    '[role="button"]',
    '[role="link"]',
    '[role="tab"]',
    '[role="menuitem"]',
    '[role="checkbox"]',
    '[role="radio"]',
    '[role="textbox"]',
    '[role="combobox"]',
    '[contenteditable="true"]',
    '[onclick]'
  ].join(',');

  const LANDMARKS = new Set(['HEADER', 'NAV', 'ASIDE', 'MAIN', 'FOOTER', 'FORM', 'SECTION']);

  function isVisible(el) {
    if (!el || !(el instanceof Element)) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    return true;
  }

  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/([ !"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, '\\$1');
  }

  function nearestRegion(el) {
    let cur = el;
    while (cur && cur !== document.body && cur !== document.documentElement) {
      if (LANDMARKS.has(cur.tagName)) {
        const label = cur.getAttribute('aria-label')
          || cur.getAttribute('name')
          || cur.id
          || cur.tagName.toLowerCase();
        return String(label).slice(0, 80);
      }
      const role = (cur.getAttribute('role') || '').toLowerCase();
      if (['navigation', 'banner', 'main', 'contentinfo', 'complementary', 'form', 'region'].includes(role)) {
        return (cur.getAttribute('aria-label') || role).slice(0, 80);
      }
      cur = cur.parentElement;
    }
    return 'main';
  }

  function buildCssPath(el) {
    if (el.id) return '#' + cssEscape(el.id);
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && parts.length < 5) {
      let part = cur.tagName.toLowerCase();
      if (cur.id) {
        parts.unshift('#' + cssEscape(cur.id));
        break;
      }
      const parent = cur.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
        if (siblings.length > 1) {
          part += ':nth-of-type(' + (siblings.indexOf(cur) + 1) + ')';
        }
      }
      parts.unshift(part);
      cur = parent;
    }
    return parts.join(' > ');
  }

  function elementType(el) {
    const tag = (el.tagName || '').toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const typ = (el.getAttribute('type') || '').toLowerCase();
    if (tag === 'a' || role === 'link') return 'LINK';
    if (tag === 'input') {
      if (['checkbox', 'radio'].includes(typ)) return typ.toUpperCase();
      if (typ === 'submit' || typ === 'button') return 'BUTTON';
      return 'INPUT';
    }
    if (tag === 'textarea') return 'TEXTAREA';
    if (tag === 'select' || role === 'combobox') return 'SELECT';
    if (tag === 'button' || role === 'button') return 'BUTTON';
    return 'BUTTON';
  }

  function nameOf(el) {
    return (
      el.getAttribute('aria-label')
      || el.getAttribute('placeholder')
      || el.getAttribute('title')
      || el.getAttribute('name')
      || el.getAttribute('alt')
      || (el.innerText || '').trim()
      || el.id
      || el.tagName
      || ''
    ).slice(0, 180);
  }

  function locatorsOf(el) {
    const locs = [];
    const testId = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-qa');
    if (testId) locs.push({ strategy: 'test-id', value: testId });
    if (el.id) locs.push({ strategy: 'id', value: el.id });
    if (el.getAttribute('name')) locs.push({ strategy: 'name', value: el.getAttribute('name') });
    const aria = el.getAttribute('aria-label');
    if (aria) locs.push({ strategy: 'label', value: aria });
    const ph = el.getAttribute('placeholder');
    if (ph) locs.push({ strategy: 'placeholder', value: ph });
    const path = buildCssPath(el);
    if (path) locs.push({ strategy: 'css', value: path });
    const text = (el.innerText || '').trim().slice(0, 80);
    if (text && text.length >= 2 && text.length <= 40) {
      locs.push({ strategy: 'text', value: text });
    }
    return locs;
  }

  const out = [];
  const seen = new Set();
  const nodes = Array.from(document.querySelectorAll(SELECTOR));
  for (const el of nodes) {
    if (!isVisible(el)) continue;
    const locs = locatorsOf(el);
    if (!locs.length) continue;
    const primary = locs[0];
    const key = (primary.strategy || '') + '|' + (primary.value || '');
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      name: nameOf(el),
      element_type: elementType(el),
      component_name: nearestRegion(el),
      locators: locs,
      primary_locator: primary,
      tag: (el.tagName || '').toLowerCase(),
      href: el.getAttribute('href') || '',
    });
    if (out.length >= 500) break;
  }
  return out;
}
"""


_BLOCKED_HOST_SUFFIXES = (
    '.local',
    '.internal',
    '.localhost',
    '.lan',
)
_BLOCKED_HOSTS = {
    'localhost',
    'metadata',
    'metadata.google.internal',
    'kubernetes.default',
    'kubernetes.default.svc',
}


def _is_private_or_reserved_ip(ip) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in ipaddress.ip_network('169.254.0.0/16'))
        or (ip.version == 6 and ip in ipaddress.ip_network('fc00::/7'))
    )


def _host_is_blocked(hostname: str) -> bool:
    host = (hostname or '').strip().lower().rstrip('.')
    if not host:
        return True
    if host in _BLOCKED_HOSTS:
        return True
    if any(host.endswith(suf) for suf in _BLOCKED_HOST_SUFFIXES):
        return True
    # Bare IPv4/IPv6 in hostname
    try:
        ip = ipaddress.ip_address(host.strip('[]'))
        return _is_private_or_reserved_ip(ip)
    except ValueError:
        pass
    return False


def _resolve_and_validate_host(hostname: str) -> None:
    """Resolve DNS and reject private / metadata / loopback targets (SSRF)."""
    host = (hostname or '').strip().lower().rstrip('.')
    if _host_is_blocked(host):
        raise ValueError(f'不允许扫描内网或本地地址: {hostname}')

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f'无法解析主机名: {hostname}') from exc

    if not infos:
        raise ValueError(f'无法解析主机名: {hostname}')

    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_private_or_reserved_ip(ip):
            raise ValueError(f'不允许扫描解析到私网/保留地址的主机: {hostname} -> {ip_str}')


def _normalize_url(url: str) -> str:
    url = (url or '').strip()
    if not url:
        raise ValueError('URL 不能为空')
    parsed = urlparse(url)
    if not parsed.scheme:
        url = 'https://' + url
        parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('仅支持 http/https URL')
    if not parsed.netloc:
        raise ValueError('URL 无效')
    # Strip credentials from URL for safety
    hostname = parsed.hostname
    if not hostname:
        raise ValueError('URL 无效')
    _resolve_and_validate_host(hostname)
    # Rebuild without userinfo
    netloc = hostname
    if parsed.port:
        netloc = f'{hostname}:{parsed.port}'
    return parsed._replace(netloc=netloc).geturl()


def _prepare_windows_event_loop() -> None:
    """Daphne/Twisted 可能把全局策略设成 Selector，导致 Playwright 无法拉起子进程。"""
    import asyncio
    import sys

    if not sys.platform.startswith('win'):
        return
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass


def _write_partial_result(path: Optional[str], payload: Dict[str, Any]) -> None:
    if not path:
        return
    try:
        import json
        from pathlib import Path

        Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    except Exception as exc:
        logger.debug('write partial scan result failed: %s', exc)


def _read_partial_result(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    try:
        import json
        from pathlib import Path

        p = Path(path)
        if not p.is_file() or p.stat().st_size < 2:
            return None
        data = json.loads(p.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.debug('read partial scan result failed: %s', exc)
    return None


def _write_stage(path: Optional[str], phase: str, message: str, progress: int = 0, **extra) -> None:
    payload = {
        'phase': phase,
        'message': message,
        'progress': progress,
        **extra,
    }
    # 保留已有 candidates，避免 stage 覆盖抽到的元素
    prev = _read_partial_result(path) or {}
    if 'candidates' in prev and 'candidates' not in payload:
        payload['candidates'] = prev.get('candidates')
        payload['count'] = prev.get('count', len(prev.get('candidates') or []))
        payload['url'] = prev.get('url') or payload.get('url')
        payload['title'] = prev.get('title') or payload.get('title')
        payload['requested_url'] = prev.get('requested_url') or payload.get('requested_url')
    _write_partial_result(path, payload)


def _scan_page_elements_core(
    url: str,
    *,
    headless: bool = True,
    max_elements: int = 200,
    timeout_ms: int = 180000,
    settle_ms: int = 500,
    partial_path: Optional[str] = None,
) -> Dict[str, Any]:
    """纯 Playwright 扫描（可在独立进程中运行）。"""
    _prepare_windows_event_loop()
    from playwright.sync_api import sync_playwright

    candidates: List[Dict[str, Any]] = []
    final_url = url
    title = ''
    use_headless = True if _SCAN_FORCE_HEADLESS else bool(headless)
    # 导航单独限时，避免重站点把默认超时拖满
    nav_timeout = max(15000, min(int(timeout_ms), 90000))

    _write_stage(partial_path, 'launching', '正在启动浏览器…', 18)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=use_headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-background-networking',
            ],
        )
        try:
            context = browser.new_context(
                viewport={'width': 1440, 'height': 900},
                locale='zh-CN',
                java_script_enabled=True,
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/122.0.0.0 Safari/537.36'
                ),
            )

            # 屏蔽图片/字体/媒体，加快 CSDN 等重站点加载（保留 stylesheet，避免可见性判断失真）
            def _route_handler(route):
                try:
                    if route.request.resource_type in ('image', 'media', 'font'):
                        return route.abort()
                except Exception:
                    pass
                return route.continue_()

            try:
                context.route('**/*', _route_handler)
            except Exception as exc:
                logger.debug('route setup skipped: %s', exc)

            page = context.new_page()
            page.set_default_timeout(nav_timeout)

            _write_stage(partial_path, 'navigating', f'正在打开页面（超时 {nav_timeout // 1000}s）…', 25)
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=nav_timeout)
            except Exception as exc:
                raise RuntimeError(f'打开页面失败: {exc}') from exc

            try:
                landed = page.url or url
                landed_host = urlparse(landed).hostname
                if landed_host:
                    _resolve_and_validate_host(landed_host)
            except ValueError:
                raise
            except Exception as exc:
                logger.debug('post-nav SSRF check skipped: %s', exc)

            # 不再等 networkidle（广告/长连接会导致接近卡死）
            if settle_ms > 0:
                _write_stage(partial_path, 'settling', '等待页面短暂稳定…', 40)
                page.wait_for_timeout(int(settle_ms))

            final_url = page.url or url
            try:
                title = page.title() or ''
            except Exception:
                title = ''

            _write_stage(partial_path, 'extracting', '正在抽取页面元素…', 55, url=final_url, title=title)
            try:
                raw = page.evaluate(_EXTRACT_JS) or []
            except Exception as exc:
                raise RuntimeError(f'页面元素抽取失败: {exc}') from exc

            if not isinstance(raw, list):
                raw = []

            for item in raw:
                if not isinstance(item, dict):
                    continue
                primary = item.get('primary_locator') or {}
                if not primary.get('value'):
                    continue
                name = re.sub(r'\s+', ' ', str(item.get('name') or '')).strip()[:180]
                candidates.append({
                    'name': name or f"元素_{len(candidates)+1}",
                    'element_type': item.get('element_type') or 'BUTTON',
                    'component_name': str(item.get('component_name') or 'main')[:100],
                    'locators': item.get('locators') or [primary],
                    'primary_locator': primary,
                    'url': final_url,
                    'tag': item.get('tag') or '',
                    'href': item.get('href') or '',
                    'description': f"扫描自 {title or final_url}".strip()[:500],
                })
                if len(candidates) >= max_elements:
                    break

            result = {
                'url': final_url,
                'requested_url': url,
                'title': title,
                'candidates': candidates,
                'count': len(candidates),
                'partial': False,
                'phase': 'extracted',
                'message': f'已抽取 {len(candidates)} 个元素，正在关闭浏览器…',
                'progress': 65,
            }
            # 关键：先落盘再关浏览器。browser.close() 在部分站点会挂起，
            # 父进程靠 phase=extracted 提前回收结果。
            _write_partial_result(partial_path, result)
        finally:
            _write_stage(partial_path, 'closing', '正在关闭浏览器…', 68)
            try:
                browser.close()
            except Exception:
                pass

    logger.info(
        'page scan done url=%s final=%s candidates=%s title=%s',
        url, final_url, len(candidates), title[:80],
    )
    result = {
        'url': final_url,
        'requested_url': url,
        'title': title,
        'candidates': candidates,
        'count': len(candidates),
        'partial': False,
        'phase': 'done',
        'message': f'扫描完成：{len(candidates)} 个元素',
        'progress': 70,
    }
    _write_partial_result(partial_path, result)
    return result


def _mp_scan_worker(kwargs: Dict[str, Any], queue) -> None:
    """multiprocessing spawn 子进程入口（与 Daphne 事件循环完全隔离）。"""
    try:
        data = _scan_page_elements_core(**kwargs)
        # 只回传轻量信号，完整结果已写在 partial_path，避免 Queue 大数据死锁
        queue.put({
            'ok': True,
            'partial_path': kwargs.get('partial_path'),
            'count': (data or {}).get('count') or 0,
        })
    except Exception as exc:
        partial = _read_partial_result(kwargs.get('partial_path'))
        queue.put({
            'ok': False,
            'error': f'{type(exc).__name__}: {exc}',
            'partial_path': kwargs.get('partial_path'),
            'data': {
                'phase': (partial or {}).get('phase'),
                'count': len((partial or {}).get('candidates') or []),
            } if partial else None,
        })


def _kill_process_tree(proc) -> None:
    """Terminate scan worker; escalate to kill to avoid orphan Chromium."""
    if proc is None:
        return
    try:
        if not proc.is_alive():
            return
    except Exception:
        return
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.join(timeout=3)
    except Exception:
        pass
    try:
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=3)
    except Exception:
        pass


def get_scan_concurrency_status() -> Dict[str, Any]:
    with _scan_active_lock:
        active = _scan_active
    return {
        'active': active,
        'max_concurrent': _SCAN_MAX_CONCURRENT,
        'force_headless': _SCAN_FORCE_HEADLESS,
    }


def scan_page_elements(
    url: str,
    *,
    headless: bool = True,
    max_elements: int = 200,
    timeout_ms: Optional[int] = None,
    settle_ms: int = 500,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    Open url with Playwright and extract interactive elements.

    在独立进程中执行，避免 Daphne/Windows 下 sync_playwright 的 NotImplementedError。
    全局信号量限制并发 Chromium 数量；超时强制 kill 进程树。
    若超时/失败前已抽到元素，抛出 PageScanPartialError（携带 data）供调用方入库。

    progress_callback(phase, message, progress, partial_dict) 可选，用于刷新任务进度。
    """
    import multiprocessing
    import tempfile
    import time
    from pathlib import Path

    url = _normalize_url(url)
    max_elements = max(1, min(int(max_elements or 200), 500))
    if timeout_ms is None:
        timeout_ms = _SCAN_PAGE_TIMEOUT_MS
    timeout_ms = max(30000, min(int(timeout_ms), 600000))
    if _SCAN_FORCE_HEADLESS and not headless:
        logger.info('page scan: ignoring headless=false (UI_SCAN_FORCE_HEADLESS=1)')
        headless = True

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            '未安装 Playwright，请执行: pip install playwright && playwright install chromium'
        ) from exc

    acquired = _scan_sema.acquire(timeout=_SCAN_ACQUIRE_TIMEOUT)
    if not acquired:
        status = get_scan_concurrency_status()
        raise RuntimeError(
            f'页面扫描繁忙（当前并发 {status["active"]}/{status["max_concurrent"]}），请稍后重试'
        )

    global _scan_active
    with _scan_active_lock:
        _scan_active += 1

    proc = None
    partial_path = None
    try:
        fd, partial_path = tempfile.mkstemp(prefix='ui_scan_', suffix='.json')
        try:
            os.close(fd)
        except Exception:
            pass

        kwargs = {
            'url': url,
            'headless': bool(headless),
            'max_elements': max_elements,
            'timeout_ms': timeout_ms,
            'settle_ms': int(settle_ms),
            'partial_path': partial_path,
        }
        wait_s = max(60.0, (timeout_ms / 1000.0) + _SCAN_PROCESS_BUFFER_S)

        ctx = multiprocessing.get_context('spawn')
        queue = ctx.Queue()
        proc = ctx.Process(target=_mp_scan_worker, args=(kwargs, queue), daemon=True)
        proc.start()

        deadline = time.time() + wait_s
        extracted_seen_at = None
        last_phase = None
        timed_out = False
        payload = None

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                timed_out = True
                break

            # 先读队列，避免 Windows 上大对象 Queue.put 与 join 互相死锁
            if payload is None and not queue.empty():
                try:
                    payload = queue.get_nowait()
                except Exception:
                    payload = None

            proc.join(timeout=min(1.0, remaining))

            if payload is None and not queue.empty():
                try:
                    payload = queue.get_nowait()
                except Exception:
                    payload = None

            partial = _read_partial_result(partial_path) or {}
            phase = partial.get('phase')
            if phase and phase != last_phase:
                last_phase = phase
                if progress_callback:
                    try:
                        progress_callback(
                            phase,
                            partial.get('message') or phase,
                            int(partial.get('progress') or 15),
                            partial,
                        )
                    except Exception:
                        pass

            if payload is not None:
                # 子进程已回传，再稍等退出
                if proc.is_alive():
                    proc.join(timeout=3)
                break

            if not proc.is_alive():
                # 进程已退，再捞一次队列
                if payload is None and not queue.empty():
                    try:
                        payload = queue.get_nowait()
                    except Exception:
                        payload = None
                break

            # 已抽取完成但关闭浏览器/回传卡住：最多再等 12s 后回收文件结果
            if phase in ('extracted', 'closing', 'done') and (partial.get('candidates') or []):
                if extracted_seen_at is None:
                    extracted_seen_at = time.time()
                elif time.time() - extracted_seen_at >= 12:
                    logger.warning(
                        'scan worker hung after extract (phase=%s); reclaiming file result',
                        phase,
                    )
                    _kill_process_tree(proc)
                    data = dict(partial)
                    data['partial'] = False
                    data['count'] = len(data.get('candidates') or [])
                    return data

        if proc.is_alive():
            _kill_process_tree(proc)
            timed_out = True

        if payload is None and not queue.empty():
            try:
                payload = queue.get_nowait()
            except Exception:
                payload = None

        if payload and payload.get('ok'):
            data = _read_partial_result(partial_path) or {}
            if not (data.get('candidates') or []):
                # 兼容旧 worker 若仍塞了 data
                data = payload.get('data') or data
            data['partial'] = False
            data['count'] = data.get('count') or len(data.get('candidates') or [])
            return data

        partial = _read_partial_result(partial_path)
        if payload and isinstance(payload.get('data'), dict) and not (partial or {}).get('candidates'):
            # 失败时 worker 可能只回了摘要，再读文件
            partial = _read_partial_result(partial_path) or partial

        # 阶段文件里已有 candidates 也算有效结果
        if partial and (partial.get('candidates') or []) and partial.get('phase') in (
            'extracted', 'closing', 'done',
        ):
            data = dict(partial)
            data['partial'] = bool(timed_out or (payload and not payload.get('ok')))
            data['count'] = len(data.get('candidates') or [])
            if not data['partial']:
                return data
            err = (payload or {}).get('error') or (
                f'页面扫描超时（>{int(wait_s)}s），已终止扫描进程' if timed_out else '扫描进程异常'
            )
            raise PageScanPartialError(err, data)

        err = None
        if timed_out:
            err = f'页面扫描超时（>{int(wait_s)}s），已终止扫描进程'
        elif payload and payload.get('error'):
            err = payload.get('error')
        elif proc is not None and proc.exitcode not in (0, None):
            err = f'页面扫描进程异常退出（code={proc.exitcode}）'
        else:
            err = '页面扫描未返回结果'

        if partial and (partial.get('candidates') or []):
            partial = dict(partial)
            partial['partial'] = True
            partial['count'] = len(partial.get('candidates') or [])
            raise PageScanPartialError(err, partial)
        raise RuntimeError(err)
    finally:
        _kill_process_tree(proc)
        with _scan_active_lock:
            _scan_active = max(0, _scan_active - 1)
        try:
            _scan_sema.release()
        except ValueError:
            pass
        if partial_path:
            try:
                Path(partial_path).unlink(missing_ok=True)
            except Exception:
                pass

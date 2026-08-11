"""Playwright-based recording session helper.

Playwright sync API keeps an asyncio loop in its worker thread, so Django ORM
calls there raise SynchronousOnlyOperation. All DB I/O must run in a plain
thread via `_db_call`. Event capture relies on DOM buffer + polling (not binding).
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

_RUNTIME: Dict[int, Dict[str, Any]] = {}
_LAST_EVENTS: Dict[int, List[Dict[str, Any]]] = {}
_LOCK = threading.Lock()

T = TypeVar('T')

INJECT_SCRIPT = r"""
(() => {
  if (window.__testhubRecorderInstalled) return;
  window.__testhubRecorderInstalled = true;
  window.__testhubEvents = window.__testhubEvents || [];

  const cssPath = (el) => {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) {
      return '#' + String(el.id).replace(/([ !"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, '\\$1');
    }
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && parts.length < 6) {
      let part = cur.tagName.toLowerCase();
      if (cur.classList && cur.classList.length) {
        const cls = Array.from(cur.classList).slice(0, 2).join('.');
        if (cls) part += '.' + cls;
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
  };

  const buildSelectors = (t) => {
    const sels = [];
    if (!t || !t.getAttribute) return sels;
    const testId = t.getAttribute('data-testid') || t.getAttribute('data-test') || t.getAttribute('data-qa');
    if (testId) sels.push({ strategy: 'test-id', value: testId });
    if (t.id) sels.push({ strategy: 'id', value: t.id });
    if (t.getAttribute('name')) sels.push({ strategy: 'name', value: t.getAttribute('name') });
    if (t.getAttribute('placeholder')) sels.push({ strategy: 'placeholder', value: t.getAttribute('placeholder') });
    if (t.getAttribute('aria-label')) sels.push({ strategy: 'label', value: t.getAttribute('aria-label') });
    const path = cssPath(t);
    if (path) sels.push({ strategy: 'css', value: path });
    return sels;
  };

  const push = (payload) => {
    window.__testhubEvents.push(Object.assign({ ts: Date.now(), url: location.href }, payload));
  };

  const interesting = (el) => {
    if (!el || el.nodeType !== 1) return false;
    const tag = (el.tagName || '').toLowerCase();
    if (['html', 'body', 'script', 'style', 'meta', 'link', 'path', 'svg'].includes(tag)) return false;
    return true;
  };

  const labelOf = (t) => ((t.innerText || t.value || t.getAttribute('aria-label') || t.getAttribute('title') || t.tagName || '') + '').trim().slice(0, 80);

  const hoverable = (el) => {
    if (!interesting(el)) return false;
    const tag = (el.tagName || '').toLowerCase();
    if (['html', 'body', 'main', 'section', 'article', 'form'].includes(tag)) return false;
    if (el.matches && el.matches('a,button,li,[role="menuitem"],[role="button"],[role="tab"],[role="link"],[aria-haspopup],.el-submenu,.el-submenu__title,.el-dropdown,.el-dropdown-selfdefine,.ant-dropdown-trigger,.menu-item,.nav-item')) {
      return true;
    }
    if (el.closest && el.closest('nav, [role="menubar"], [role="menu"], .el-menu, .ant-menu, .dropdown, .menu')) return true;
    if (el.onmouseover || el.getAttribute('onmouseover') || el.getAttribute('aria-haspopup')) return true;
    try {
      const cur = window.getComputedStyle(el).cursor;
      if (cur === 'pointer') return true;
    } catch (err) {}
    return false;
  };

  document.addEventListener('click', (e) => {
    let t = e.target;
    if (!interesting(t)) {
      t = e.target && e.target.closest ? e.target.closest('a,button,input,select,textarea,[role="button"],[onclick]') : t;
    }
    if (!interesting(t)) return;
    push({
      type: 'click',
      selectors: buildSelectors(t),
      description: labelOf(t),
    });
  }, true);

  // Hover: only emit after mouse stays ~450ms on a menu/nav-like target (avoid flood)
  let hoverTimer = null;
  let hoverTarget = null;
  let lastHoverKey = '';
  const resolveHoverTarget = (el) => {
    if (!el || !el.closest) return null;
    const preferred = el.closest('a,button,li,[role="menuitem"],[role="button"],[role="tab"],[aria-haspopup],.el-submenu__title,.el-dropdown,.ant-dropdown-trigger,.menu-item');
    const t = preferred || el;
    return hoverable(t) ? t : null;
  };
  document.addEventListener('mouseover', (e) => {
    const t = resolveHoverTarget(e.target);
    if (!t) {
      if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
      hoverTarget = null;
      return;
    }
    if (hoverTarget === t) return;
    hoverTarget = t;
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      hoverTimer = null;
      if (hoverTarget !== t) return;
      const sels = buildSelectors(t);
      const key = (sels[0] && sels[0].value) || labelOf(t);
      if (!key || key === lastHoverKey) return;
      lastHoverKey = key;
      push({
        type: 'hover',
        selectors: sels,
        description: '悬停 ' + (labelOf(t) || t.tagName),
      });
    }, 450);
  }, true);
  document.addEventListener('mouseout', (e) => {
    if (!hoverTarget) return;
    const related = e.relatedTarget;
    if (related && hoverTarget.contains && hoverTarget.contains(related)) return;
    if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
    hoverTarget = null;
  }, true);

  const isSensitiveInput = (t) => {
    if (!t || !t.getAttribute) return false;
    const typ = (t.getAttribute('type') || '').toLowerCase();
    if (typ === 'password') return true;
    const blob = [
      t.getAttribute('name') || '',
      t.getAttribute('id') || '',
      t.getAttribute('autocomplete') || '',
      t.getAttribute('aria-label') || '',
      t.getAttribute('placeholder') || '',
    ].join(' ').toLowerCase();
    return /pass|pwd|token|secret|credential|api[_-]?key/.test(blob);
  };

  const onInputCommit = (t) => {
    if (!interesting(t)) return;
    const tag = (t.tagName || '').toLowerCase();
    if (!['input', 'textarea', 'select'].includes(tag) && t.getAttribute('contenteditable') !== 'true') return;
    const raw = t.value != null ? String(t.value) : (t.innerText || '');
    const sensitive = isSensitiveInput(t);
    push({
      type: 'fill',
      value: sensitive ? '******' : raw,
      sensitive: !!sensitive,
      selectors: buildSelectors(t),
      description: ((t.getAttribute('placeholder') || t.getAttribute('name') || t.getAttribute('aria-label') || '输入') + '').slice(0, 80),
    });
  };

  document.addEventListener('change', (e) => onInputCommit(e.target), true);
  document.addEventListener('blur', (e) => {
    const t = e.target;
    if (!t) return;
    const tag = (t.tagName || '').toLowerCase();
    if (['input', 'textarea'].includes(tag)) onInputCommit(t);
  }, true);

  // Scroll: debounce until idle, record final position (window or scrollable container)
  let scrollTimer = null;
  let lastScrollKey = '';
  const emitScroll = (target) => {
    let x = 0, y = 0, sels = [], desc = '';
    if (!target || target === document || target === document.documentElement || target === document.body || target === window) {
      x = window.scrollX || document.documentElement.scrollLeft || 0;
      y = window.scrollY || document.documentElement.scrollTop || 0;
      desc = '页面滚动到 (' + Math.round(x) + ', ' + Math.round(y) + ')';
    } else if (target.nodeType === 1) {
      x = target.scrollLeft || 0;
      y = target.scrollTop || 0;
      sels = buildSelectors(target);
      desc = '容器滚动到 (' + Math.round(x) + ', ' + Math.round(y) + ')';
    } else {
      return;
    }
    // ignore tiny jitter
    if (Math.abs(x) < 2 && Math.abs(y) < 2 && !sels.length) return;
    const key = (sels[0] && sels[0].value ? sels[0].value : 'window') + ':' + Math.round(x) + ',' + Math.round(y);
    if (key === lastScrollKey) return;
    lastScrollKey = key;
    push({
      type: 'scroll',
      selectors: sels,
      scrollX: Math.round(x),
      scrollY: Math.round(y),
      value: Math.round(x) + ',' + Math.round(y),
      description: desc,
    });
  };
  document.addEventListener('scroll', (e) => {
    const target = e.target === document ? window : e.target;
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => emitScroll(target), 350);
  }, true);

  // Tab focus: when this page becomes visible again, record switchTab
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      push({
        type: 'switchTab',
        description: '切换标签页',
      });
    }
  });
})();
"""


def _db_call(func: Callable[..., T], *args, **kwargs) -> T:
    """Run Django ORM in a fresh thread without Playwright's event loop."""
    box: Dict[str, Any] = {}

    def runner():
        # Playwright worker may inherit async markers; force allow in DB thread too
        os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
        close_old_connections()
        try:
            box['result'] = func(*args, **kwargs)
        except Exception as exc:
            box['error'] = exc
        finally:
            close_old_connections()

    t = threading.Thread(target=runner, name='recording-db', daemon=True)
    t.start()
    t.join(timeout=60)
    if t.is_alive():
        raise TimeoutError('recording DB call timed out')
    if 'error' in box:
        raise box['error']
    return box.get('result')


def _set_runtime(session_id: int, **kwargs):
    with _LOCK:
        state = _RUNTIME.setdefault(session_id, {})
        state.update(kwargs)
        if 'raw_events' in kwargs:
            _LAST_EVENTS[session_id] = list(kwargs['raw_events'] or [])


def _get_runtime(session_id: int) -> Dict[str, Any]:
    with _LOCK:
        return dict(_RUNTIME.get(session_id) or {})


def _clear_runtime(session_id: int, *, keep_events: bool = True):
    with _LOCK:
        state = _RUNTIME.pop(session_id, None) or {}
        if keep_events and 'raw_events' in state:
            _LAST_EVENTS[session_id] = list(state.get('raw_events') or [])


def _get_saved_events(session_id: int) -> List[Dict[str, Any]]:
    with _LOCK:
        live = (_RUNTIME.get(session_id) or {}).get('raw_events')
        if live:
            return list(live)
        return list(_LAST_EVENTS.get(session_id) or [])


def _event_key(ev: Dict[str, Any]) -> tuple:
    sels = ev.get('selectors') or []
    sel0 = ''
    if sels and isinstance(sels[0], dict):
        sel0 = f"{sels[0].get('strategy')}:{sels[0].get('value')}"
    return (
        ev.get('type'),
        ev.get('url'),
        ev.get('description'),
        ev.get('value'),
        sel0,
    )


def _dedupe_events(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    for ev in raw_events:
        if deduped and _event_key(deduped[-1]) == _event_key(ev):
            continue
        deduped.append(ev)
    return deduped


def _persist_events(trace_id: int, raw_events: List[Dict[str, Any]]):
    if not trace_id:
        return

    def _do():
        from apps.ui_automation.models import UIActionTrace
        UIActionTrace.objects.filter(id=trace_id).update(raw_events=list(raw_events))

    try:
        _db_call(_do)
    except Exception as exc:
        logger.warning('persist recording events failed: %s', exc)


def start_recording_session(session) -> None:
    from apps.ui_automation.models import UIActionTrace
    from apps.ui_automation.services.action_trace import normalize_recording_events

    start_url = session.start_url or (session.project.base_url if session.project_id else '') or 'about:blank'
    initial_events: List[Dict[str, Any]] = [{
        'type': 'navigate',
        'url': start_url,
        'selectors': [],
        'description': f'打开 {start_url}',
        'ts': int(time.time() * 1000),
    }]

    # Start is called from Django request thread — ORM is fine here
    trace = UIActionTrace.objects.create(
        project=session.project,
        source='recording',
        raw_events=initial_events,
        normalized_actions=normalize_recording_events(initial_events),
        created_by=session.created_by,
    )
    session.action_trace = trace
    session.status = 'recording'
    session.started_at = timezone.now()
    session.error_message = ''
    session.save(update_fields=['action_trace', 'status', 'started_at', 'error_message', 'updated_at'])

    session_id = session.id
    trace_id = trace.id
    event_queue: queue.Queue = queue.Queue()
    _LAST_EVENTS[session_id] = list(initial_events)

    def worker():
        # Allow unsafe ORM fallback if any call slips through
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

        playwright = None
        browser = None
        raw_events: List[Dict[str, Any]] = list(initial_events)
        last_persist = 0.0
        last_url = start_url

        def drain_queue():
            nonlocal last_persist
            changed = False
            while True:
                try:
                    payload = event_queue.get_nowait()
                except queue.Empty:
                    break
                if isinstance(payload, dict):
                    raw_events.append(payload)
                    changed = True
            if changed:
                _set_runtime(session_id, raw_events=list(raw_events))
                now = time.time()
                if now - last_persist >= 1.0:
                    last_persist = now
                    _persist_events(trace_id, raw_events)
            return changed

        def finalize_db(status: str, error_message: str = ''):
            events = _dedupe_events(raw_events)
            raw_events[:] = events
            _set_runtime(session_id, raw_events=list(events))

            def _do():
                from apps.ui_automation.models import RecordingSession, UIActionTrace
                from apps.ui_automation.services.action_trace import normalize_recording_events as normalize
                UIActionTrace.objects.filter(id=trace_id).update(
                    raw_events=events,
                    normalized_actions=normalize(events),
                )
                RecordingSession.objects.filter(id=session_id).update(
                    status=status,
                    stopped_at=timezone.now(),
                    error_message=(error_message or '')[:2000],
                )

            _db_call(_do)
            return events

        try:
            from playwright.sync_api import sync_playwright

            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=False, args=['--start-maximized'])
            context = browser.new_context(no_viewport=True)
            page = context.new_page()
            attached_ids = set()

            def page_index(p) -> int:
                try:
                    pages = list(context.pages)
                    return pages.index(p)
                except Exception:
                    return -1

            def attach_page(p):
                nonlocal page, last_url
                try:
                    pid = id(p)
                    if pid in attached_ids:
                        return
                    attached_ids.add(pid)

                    def on_nav(frame, _page=p):
                        nonlocal last_url, page
                        try:
                            if frame != _page.main_frame:
                                return
                            url = frame.url or ''
                            if not url or url == 'about:blank':
                                return
                            # only record navigate for the page we're currently tracking focus on,
                            # or always record with url (useful for new tabs)
                            if url == last_url and _page == page:
                                return
                            last_url = url
                            page = _page
                            event_queue.put({
                                'type': 'navigate',
                                'url': url,
                                'selectors': [],
                                'description': f'打开 {url}',
                                'ts': int(time.time() * 1000),
                            })
                        except Exception:
                            pass

                    p.on('framenavigated', on_nav)
                    try:
                        p.add_init_script(INJECT_SCRIPT)
                    except Exception:
                        pass
                    try:
                        p.evaluate(INJECT_SCRIPT)
                    except Exception:
                        pass
                except Exception as exc:
                    logger.debug('attach_page failed: %s', exc)

            def on_new_page(p):
                nonlocal page
                try:
                    attach_page(p)
                    page = p
                    idx = page_index(p)
                    event_queue.put({
                        'type': 'switchTab',
                        'value': str(idx) if idx >= 0 else '',
                        'selectors': [],
                        'description': f'切换到新标签页 {idx}' if idx >= 0 else '切换到新标签页',
                        'url': getattr(p, 'url', '') or '',
                        'ts': int(time.time() * 1000),
                    })
                except Exception as exc:
                    logger.debug('on_new_page failed: %s', exc)

            context.on('page', on_new_page)
            attach_page(page)
            page.goto(start_url, wait_until='domcontentloaded', timeout=60000)
            try:
                page.evaluate(INJECT_SCRIPT)
            except Exception as exc:
                logger.warning('initial inject failed: %s', exc)

            def poll_all_pages():
                nonlocal page
                for p in list(context.pages):
                    try:
                        attach_page(p)
                        installed = p.evaluate('() => !!window.__testhubRecorderInstalled')
                        if not installed:
                            p.evaluate(INJECT_SCRIPT)
                        batch = p.evaluate(
                            '() => { const e = window.__testhubEvents || []; window.__testhubEvents = []; return e; }'
                        )
                        if not batch:
                            continue
                        idx = page_index(p)
                        for item in batch:
                            if not isinstance(item, dict):
                                continue
                            if (item.get('type') or '').lower() in ('switchtab', 'switch_tab', 'switch'):
                                item = dict(item)
                                item['type'] = 'switchTab'
                                item['value'] = str(idx) if idx >= 0 else item.get('value') or ''
                                item['description'] = item.get('description') or (
                                    f'切换到标签页 {idx}' if idx >= 0 else '切换标签页'
                                )
                                page = p
                            event_queue.put(item)
                    except Exception as exc:
                        logger.debug('poll page error: %s', exc)

            _set_runtime(
                session_id,
                stop=False,
                page=page,
                browser=browser,
                playwright=playwright,
                raw_events=list(raw_events),
                ready=True,
            )
            _persist_events(trace_id, raw_events)
            logger.info('Recording session %s browser ready url=%s', session_id, start_url)

            while True:
                if _get_runtime(session_id).get('stop'):
                    break

                drain_queue()
                try:
                    poll_all_pages()
                    drain_queue()
                except Exception as exc:
                    logger.debug('Recording poll error: %s', exc)

                time.sleep(0.3)

            # Final drain before closing browser
            drain_queue()
            try:
                poll_all_pages()
                drain_queue()
            except Exception:
                pass

            events = finalize_db('stopped')
            logger.info('Recording session %s stopped, events=%s', session_id, len(events))
        except Exception as exc:
            logger.exception('Recording session %s failed: %s', session_id, exc)
            try:
                drain_queue()
                finalize_db('failed', str(exc))
            except Exception:
                logger.exception('Failed to mark recording session failed')
        finally:
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            try:
                if playwright:
                    playwright.stop()
            except Exception:
                pass
            # Keep last events for stop/compile salvage
            _clear_runtime(session_id, keep_events=True)

    thread = threading.Thread(target=worker, name=f'recording-{session_id}', daemon=True)
    thread.start()
    _set_runtime(
        session_id,
        thread=thread,
        stop=False,
        raw_events=list(initial_events),
        trace_id=trace_id,
        event_queue=event_queue,
    )


def stop_recording_session(session, wait_timeout: float = 60.0) -> None:
    from apps.ui_automation.models import UIActionTrace
    from apps.ui_automation.services.action_trace import normalize_recording_events

    state = _get_runtime(session.id)
    if state:
        _set_runtime(session.id, stop=True)
        thread = state.get('thread')
        if thread and thread.is_alive():
            thread.join(timeout=wait_timeout)

    session.refresh_from_db()
    salvaged = _get_saved_events(session.id)

    if session.action_trace_id and salvaged:
        def _save():
            UIActionTrace.objects.filter(id=session.action_trace_id).update(
                raw_events=salvaged,
                normalized_actions=normalize_recording_events(salvaged),
            )
        try:
            # Request thread is sync — direct ORM OK; still use _db_call for consistency
            UIActionTrace.objects.filter(id=session.action_trace_id).update(
                raw_events=salvaged,
                normalized_actions=normalize_recording_events(salvaged),
            )
        except Exception as exc:
            logger.warning('salvage persist failed: %s', exc)
            try:
                _db_call(_save)
            except Exception:
                logger.exception('salvage db_call failed')

    if session.status == 'recording':
        session.status = 'stopped'
        session.stopped_at = timezone.now()
        if not salvaged:
            session.error_message = (session.error_message or '') + '\n[System] 停止超时，且未找到事件'
        elif len(salvaged) <= 1:
            session.error_message = (session.error_message or '') + '\n[System] 停止超时，仅有初始导航事件'
        else:
            session.error_message = (session.error_message or '') + '\n[System] 停止超时，已强制落库内存事件'
        session.save(update_fields=['status', 'stopped_at', 'error_message', 'updated_at'])

    _clear_runtime(session.id, keep_events=True)


def get_live_events(session_id: int) -> List[Dict[str, Any]]:
    live = _get_saved_events(session_id)
    if live:
        return live
    try:
        from apps.ui_automation.models import RecordingSession
        session = RecordingSession.objects.select_related('action_trace').filter(id=session_id).first()
        if session and session.action_trace_id:
            return list(session.action_trace.raw_events or [])
    except Exception:
        pass
    return []


def finalize_and_compile(session, *, name: str = '', created_by=None, auto_compile: bool = True):
    from apps.ui_automation.services.action_trace import normalize_recording_events
    from apps.ui_automation.services.compiler import compile_trace_to_testcase

    session.refresh_from_db()
    if not session.action_trace_id:
        raise ValueError('没有可编译的操作轨迹，请重新录制')

    trace = session.action_trace
    raw = list(trace.raw_events or [])
    salvaged = _get_saved_events(session.id)
    if len(salvaged) > len(raw):
        raw = salvaged

    if len(raw) <= 1:
        raise ValueError(
            f'录制仅捕获到 {len(raw)} 个事件（通常只有打开页面）。'
            '请在弹出的 Chromium 窗口中完成点击/输入后再停止；'
            '若左侧事件列表一直只有 1 条，说明页面脚本未注入成功。'
        )

    raw = _dedupe_events(raw)
    trace.raw_events = raw
    trace.normalized_actions = normalize_recording_events(raw)
    trace.save(update_fields=['raw_events', 'normalized_actions', 'updated_at'])

    if not auto_compile:
        return None, {'step_count': len(trace.normalized_actions or [])}

    case_name = name or session.name or f'录制用例-{session.id}'
    test_case, preview = compile_trace_to_testcase(
        trace,
        name=case_name,
        description=f'由录制会话 #{session.id} 自动生成（{len(raw)} 个原始事件）',
        created_by=created_by or session.created_by,
        commit=True,
    )
    return test_case, preview

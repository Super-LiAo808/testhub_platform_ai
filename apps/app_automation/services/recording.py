"""APP recording: scrcpy (preferred) or screenshot mirror + adb gestures -> AppElement + ui_flow."""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

_RUNTIME: Dict[int, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_DRIVER_LOCK = threading.Lock()  # Appium driver 非线程安全：截屏与输入互斥

CROP_HALF = 90  # crop half-size around tap (device pixels)

# 投屏清晰度档位：清晰度越高，单帧越大、刷新略慢
STREAM_QUALITY_PRESETS = {
    'fast': {'max_w': 720, 'quality': 55, 'frame_interval': 0.12},
    'balanced': {'max_w': 1080, 'quality': 70, 'frame_interval': 0.16},
    'clear': {'max_w': 1280, 'quality': 82, 'frame_interval': 0.2},
}


def resolve_stream_quality(mode: Optional[str] = None) -> Dict[str, Any]:
    key = (mode or 'balanced').strip().lower()
    if key not in STREAM_QUALITY_PRESETS:
        key = 'balanced'
    preset = dict(STREAM_QUALITY_PRESETS[key])
    preset['mode'] = key
    return preset


def set_recording_stream_quality(session_id: int, mode: str) -> Dict[str, Any]:
    preset = resolve_stream_quality(mode)
    _set_runtime(
        session_id,
        stream_quality=preset['mode'],
        stream_max_w=preset['max_w'],
        stream_jpeg_quality=preset['quality'],
        frame_interval=preset['frame_interval'],
    )
    return preset


def _png_to_stream_jpeg(
    png: bytes,
    max_w: int = 1080,
    quality: int = 70,
) -> tuple:
    """Return (data_url, original_width, original_height). Falls back to PNG data URL."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png)).convert('RGB')
        ow, oh = img.size
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=max(40, min(95, int(quality))), optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        return f'data:image/jpeg;base64,{b64}', ow, oh
    except Exception:
        b64 = base64.b64encode(png).decode('ascii')
        return f'data:image/png;base64,{b64}', 0, 0


def _set_runtime(session_id: int, **kwargs):
    with _LOCK:
        state = _RUNTIME.setdefault(session_id, {})
        state.update(kwargs)


def _get_runtime(session_id: int) -> Dict[str, Any]:
    with _LOCK:
        return dict(_RUNTIME.get(session_id) or {})


def _clear_runtime(session_id: int):
    with _LOCK:
        _RUNTIME.pop(session_id, None)


def _channel_send(session_id: int, payload: Dict[str, Any]):
    try:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        async_to_sync(channel_layer.group_send)(
            f'app_recording_{session_id}',
            {'type': 'recording_update', **payload},
        )
    except Exception as exc:
        logger.debug('recording channel send failed: %s', exc)


def _resolve_adb_path() -> str:
    try:
        from apps.app_automation.views.device_views import get_adb_path
        return get_adb_path() or 'adb'
    except Exception:
        try:
            from apps.app_automation.models import AppTestConfig
            cfg = AppTestConfig.objects.first()
            if cfg and getattr(cfg, 'adb_path', None):
                return cfg.adb_path
        except Exception:
            pass
    return 'adb'


def _adb(device_id: str, *args, timeout: float = 30) -> subprocess.CompletedProcess:
    adb = _resolve_adb_path()
    cmd = [adb, '-s', device_id, *args]
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _adb_is_online(device_id: str) -> bool:
    """轻量探测，避免频繁 dumpsys / screencap 压垮 USB。"""
    try:
        proc = _adb(device_id, 'get-state', timeout=4)
        out = (proc.stdout or b'').decode('utf-8', errors='ignore').strip().lower()
        return proc.returncode == 0 and out == 'device'
    except Exception:
        return False


def _normalize_png(data: bytes) -> Optional[bytes]:
    if not data:
        return None
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        data = data.replace(b'\r\n', b'\n')
    if data[:8] == b'\x89PNG\r\n\x1a\n' or data[:4] == b'\x89PNG':
        return data
    return None


def _screencap_adb_fallback(device_id: str) -> Optional[bytes]:
    """Short-timeout adb fallback when Appium screenshot fails."""
    try:
        proc = _adb(device_id, 'exec-out', 'screencap', '-p', timeout=6)
        if proc.returncode == 0:
            return _normalize_png(proc.stdout or b'')
    except Exception as exc:
        logger.debug('adb screencap fallback failed: %s', exc)
    return None


def _wm_size(device_id: str) -> tuple:
    """主屏（display 0）当前逻辑分辨率，与 adb input / screencap 一致。

    注意：scrcpy 会额外创建虚拟屏（如 1280x856），dumpsys 里可能排在 display 0 前面；
    若误用虚拟屏尺寸，点击会被夹到错误坐标系，表现为「点了没反应」。
    """
    import re

    physical = None
    override = None
    try:
        proc = _adb(device_id, 'shell', 'wm', 'size', timeout=8)
        out = (proc.stdout or b'').decode('utf-8', errors='ignore')
        for part in out.replace('\r', '').split('\n'):
            line = part.strip()
            if not line or 'x' not in line.lower():
                continue
            dims = line.split(':')[-1].strip()
            parts = dims.lower().split('x')
            if len(parts) < 2:
                continue
            try:
                w, h = int(parts[0].strip()), int(parts[1].strip())
            except ValueError:
                continue
            low = line.lower()
            if 'override' in low:
                override = (w, h)
            elif 'physical' in low:
                physical = (w, h)
            elif physical is None and override is None:
                physical = (w, h)
        if override:
            return override
    except Exception:
        pass

    # 只读主屏 displayId=0 的 cur=（忽略 scrcpy 虚拟屏）
    try:
        proc = _adb(device_id, 'shell', 'dumpsys', 'window', 'displays', timeout=10)
        out = (proc.stdout or b'').decode('utf-8', errors='ignore')
        # 优先：Display: mDisplayId=0 ... cur=WxH
        m0 = re.search(
            r'Display:\s*mDisplayId=0\b[\s\S]*?\bcur=(\d+)x(\d+)',
            out,
        )
        if m0:
            return int(m0.group(1)), int(m0.group(2))
        # 其次：init=物理 与 cur=当前 同行（主屏特征常为 init 匹配 physical）
        for m in re.finditer(r'\binit=(\d+)x(\d+)\b[^\\n]*\bcur=(\d+)x(\d+)', out):
            iw, ih, cw, ch = (int(m.group(i)) for i in range(1, 5))
            if physical and (iw, ih) == physical:
                return cw, ch
            # 跳过明显的 scrcpy 小虚拟屏（相对物理尺寸过小）
            if physical:
                pw, ph = physical
                if cw * ch < (pw * ph) * 0.4:
                    continue
            return cw, ch
    except Exception:
        pass

    if physical:
        return physical
    return 0, 0


def _publish_device_size(session_id: int, width: int, height: int, mirror_mode: str = '') -> None:
    """把最新逻辑分辨率写入 runtime / DB，并通知前端重算坐标映射。"""
    if not width or not height:
        return
    # 拒绝明显的 scrcpy 虚拟屏尺寸覆盖已有主屏尺寸
    state = _get_runtime(session_id)
    prev_w = int(state.get('device_width') or 0)
    prev_h = int(state.get('device_height') or 0)
    if prev_w > 0 and prev_h > 0:
        if width * height < int(prev_w * prev_h * 0.5):
            logger.debug(
                'ignore tiny size update session=%s keep=%sx%s skip=%sx%s',
                session_id, prev_w, prev_h, width, height,
            )
            return
    _set_runtime(session_id, device_width=width, device_height=height)
    if prev_w == width and prev_h == height:
        return
    logger.info(
        'recording size update session=%s %sx%s -> %sx%s',
        session_id, prev_w, prev_h, width, height,
    )
    try:
        from apps.app_automation.models import AppRecordingSession
        AppRecordingSession.objects.filter(id=session_id).update(
            screen_width=width, screen_height=height,
        )
    except Exception:
        pass
    payload = {
        'event': 'status',
        'status': 'recording',
        'screen_width': width,
        'screen_height': height,
        'device_width': width,
        'device_height': height,
        'message': f'分辨率已更新为 {width}x{height}',
    }
    if mirror_mode:
        payload['mirror_mode'] = mirror_mode
    _channel_send(session_id, payload)


def _driver_screenshot(driver) -> Optional[bytes]:
    if driver is None:
        return None
    try:
        with _DRIVER_LOCK:
            data = driver.get_screenshot_as_png()
        return _normalize_png(data) or data
    except Exception as exc:
        logger.warning('Appium screenshot failed: %s', exc)
        return None


def _driver_window_size(driver) -> tuple:
    if driver is None:
        return 0, 0
    try:
        size = driver.get_window_size()
        return int(size.get('width') or 0), int(size.get('height') or 0)
    except Exception:
        return 0, 0


def _text_needs_unicode(text: str) -> bool:
    """adb shell input text 仅可靠支持 ASCII，中文等必须走剪贴板/Appium。"""
    return any(ord(ch) > 127 for ch in (text or ''))


def _get_default_ime(device_id: str) -> str:
    try:
        proc = _adb(device_id, 'shell', 'settings', 'get', 'secure', 'default_input_method', timeout=5)
        if proc.returncode == 0:
            return (proc.stdout or b'').decode('utf-8', errors='ignore').strip()
    except Exception:
        pass
    return ''


def _encode_imap_utf7(text: str) -> str:
    """Modified UTF-7 (RFC 3501 / x-IMAP-mailbox-name)，供 UnicodeIME 解码。

    标准 utf-7 用 '+' 移位；UnicodeIME 用 '&'，否则会原样显示成乱码。
    """
    import re

    raw = (text or '').replace('&', '&-')
    utf7 = raw.encode('utf-7').decode('ascii')
    imap = utf7.replace('+', '&')
    return re.sub(
        r'&([A-Za-z0-9+/]+)-',
        lambda m: '&' + m.group(1).replace('/', ',') + '-',
        imap,
    )


def _adb_input_unicode_ime(device_id: str, text: str) -> bool:
    """用 io.appium.settings UnicodeIME + IMAP UTF-7 输入中文，不启动 Appium、不抢前台。

    旧路径会 prepare Appium Settings（按 HOME + 打开 Settings），表现为「页面闪退」。
    """
    if not text:
        return True
    ime = 'io.appium.settings/.UnicodeIME'
    prev = _get_default_ime(device_id)
    try:
        en = _adb(device_id, 'shell', 'ime', 'enable', ime, timeout=8)
        if en.returncode != 0:
            logger.debug('enable UnicodeIME failed: %s', (en.stderr or b'')[:200])
            return False
        st = _adb(device_id, 'shell', 'ime', 'set', ime, timeout=8)
        if st.returncode != 0:
            logger.debug('set UnicodeIME failed: %s', (st.stderr or b'')[:200])
            return False
        time.sleep(0.15)
        encoded = _encode_imap_utf7(text).replace(' ', '%s')
        # & 对 device shell 有特殊含义，必须整体加引号
        safe = encoded.replace("'", "'\\''")
        proc = _adb(device_id, 'shell', f"input text '{safe}'", timeout=12)
        ok = proc.returncode == 0
        if ok:
            logger.info('已通过 UnicodeIME 输入文本，len=%s enc=%s', len(text), encoded[:40])
        else:
            logger.warning(
                'UnicodeIME input text failed rc=%s err=%s',
                proc.returncode, (proc.stderr or b'')[:200],
            )
        return ok
    except Exception as exc:
        logger.warning('UnicodeIME input failed: %s', exc)
        return False
    finally:
        if prev and prev != ime:
            try:
                _adb(device_id, 'shell', 'ime', 'set', prev, timeout=8)
            except Exception:
                pass


def _adb_paste_unicode(device_id: str, text: str) -> bool:
    """尽量用 adb 写剪贴板再粘贴；多数机型无 root 会失败，仅作次选。"""
    if not text:
        return True
    try:
        # 部分 ROM 支持（失败则忽略）
        b64 = base64.b64encode(text.encode('utf-8')).decode('ascii')
        for args in (
            ('shell', 'cmd', 'clipboard', 'set-text', text),
            ('shell', 'service', 'call', 'clipboard', '2', 'i32', '1', 'i32', '1', 's16', text),
        ):
            try:
                proc = _adb(device_id, *args, timeout=6)
                if proc.returncode == 0:
                    break
            except Exception:
                continue
        else:
            # Appium Settings 无公开 set-clipboard broadcast 时跳过
            _ = b64
            return False
        proc = _adb(device_id, 'shell', 'input', 'keyevent', '279', timeout=5)
        return proc.returncode == 0
    except Exception as exc:
        logger.debug('adb paste unicode failed: %s', exc)
        return False


def _appium_input_unicode(driver, text: str) -> bool:
    """通过 Appium 输入 Unicode（含中文）：优先剪贴板粘贴，其次 mobile: type。"""
    if driver is None or not text:
        return False
    with _DRIVER_LOCK:
        # 1) 剪贴板 + 粘贴（KEYCODE_PASTE=279）
        try:
            if hasattr(driver, 'set_clipboard_text'):
                driver.set_clipboard_text(text)
            else:
                driver.execute_script('mobile: setClipboard', {
                    'content': text,
                    'contentType': 'plaintext',
                })
            time.sleep(0.08)
            try:
                driver.press_keycode(279)
            except Exception:
                driver.execute_script('mobile: pressKey', {'keycode': 279})
            time.sleep(0.05)
            logger.info('已通过 Appium 剪贴板粘贴输入 Unicode 文本，len=%s', len(text))
            return True
        except Exception as exc:
            logger.debug('Appium clipboard paste failed: %s', exc)

        # 2) mobile: type
        try:
            driver.execute_script('mobile: type', {'text': text})
            logger.info('已通过 mobile: type 输入 Unicode 文本，len=%s', len(text))
            return True
        except Exception as exc:
            logger.debug('mobile: type failed: %s', exc)

        # 3) active element send_keys
        try:
            el = driver.switch_to.active_element
            if el:
                el.send_keys(text)
                logger.info('已通过 active_element.send_keys 输入，len=%s', len(text))
                return True
        except Exception as exc:
            logger.debug('active_element send_keys failed: %s', exc)
    return False


def _adb_input_ascii(device_id: str, text: str) -> bool:
    """仅用于 ASCII；空格用 %s。"""
    safe = (text or '').replace(' ', '%s').replace("'", '')
    if not safe:
        return True
    try:
        proc = _adb(device_id, 'shell', 'input', 'text', safe, timeout=8)
        return proc.returncode == 0
    except Exception as exc:
        logger.debug('adb input text failed: %s', exc)
        return False


def ensure_recording_appium(session_id: int, device_id: str):
    """按需拉起 Appium（仅作中文输入兜底）。成功则写入 runtime.driver。

    注意：不要调用会按 HOME / 打开 Settings 的 prepare，否则前台 App 会「闪退」。
    """
    state = _get_runtime(session_id)
    driver = state.get('driver')
    if driver is not None:
        return driver

    with _DRIVER_LOCK:
        state = _get_runtime(session_id)
        driver = state.get('driver')
        if driver is not None:
            return driver
        if state.get('stop'):
            return None

        from apps.app_automation.services.appium_server import (
            create_android_driver,
            ensure_appium_running,
            ensure_device_appium_apks,
        )

        _set_runtime(session_id, screencap_error='正在按需启动 Appium（中文输入兜底）…')
        _channel_send(session_id, {
            'event': 'status',
            'status': 'recording',
            'message': '正在按需启动 Appium（中文输入兜底）…',
        })
        try:
            server_url = ensure_appium_running(timeout=60.0)
            ensure_device_appium_apks(device_id)
            driver = create_android_driver(
                device_id,
                server_url=server_url,
                steal_focus=False,
            )
            _set_runtime(session_id, driver=driver, screencap_error='')
            _channel_send(session_id, {
                'event': 'status',
                'status': 'recording',
                'message': 'Appium 已就绪（可用于中文输入）',
            })
            return driver
        except Exception as exc:
            logger.exception('lazy Appium start failed: %s', exc)
            _set_runtime(session_id, screencap_error=f'Appium 按需启动失败: {exc}')
            _channel_send(session_id, {
                'event': 'error',
                'message': f'中文输入需要 Appium，启动失败: {exc}',
            })
            return None


def _fast_input_text(device_id: str, text: str, driver=None, session_id: int = 0) -> bool:
    """
    输入文本。中文优先 UnicodeIME（adb），避免启动 Appium Settings 导致闪退。
    """
    text = text or ''
    if not text:
        return True

    if _text_needs_unicode(text):
        if _adb_input_unicode_ime(device_id, text):
            return True
        if _adb_paste_unicode(device_id, text):
            return True
        if driver is None and session_id:
            driver = ensure_recording_appium(session_id, device_id)
        if _appium_input_unicode(driver, text):
            return True
        logger.warning(
            '无法输入中文/Unicode 文本：UnicodeIME/剪贴板/Appium 均失败。'
            '请确认已安装 io.appium.settings，且输入框已聚焦。'
        )
        return False

    # ASCII：adb 更快
    if _adb_input_ascii(device_id, text):
        return True
    if driver is None and session_id:
        driver = ensure_recording_appium(session_id, device_id)
    if driver is not None and _appium_input_unicode(driver, text):
        return True
    return False


def _clamp_xy(device_id: str, x: int, y: int, session_id: int = None) -> tuple:
    """按主屏逻辑分辨率夹紧坐标，避免旋转后点到屏外。"""
    w = h = 0
    if session_id is not None:
        st = _get_runtime(session_id)
        w = int(st.get('device_width') or 0)
        h = int(st.get('device_height') or 0)
    if not w or not h:
        w, h = _wm_size(device_id)
    xi, yi = int(x), int(y)
    if w > 0 and h > 0:
        xi = max(0, min(w - 1, xi))
        yi = max(0, min(h - 1, yi))
    return xi, yi


def _fast_tap(device_id: str, x: int, y: int, driver=None, session_id: int = None):
    """Prefer adb tap (low latency); Appium only as fallback."""
    x, y = _clamp_xy(device_id, x, y, session_id=session_id)
    attempts = (
        ('touchscreen tap', ['shell', 'input', 'touchscreen', 'tap', str(x), str(y)]),
        ('input tap', ['shell', 'input', 'tap', str(x), str(y)]),
    )
    last_err = ''
    for label, args in attempts:
        try:
            proc = _adb(device_id, *args, timeout=3)
            if proc.returncode == 0:
                logger.info('adb %s ok device=%s (%s,%s)', label, device_id, x, y)
                return
            last_err = (proc.stderr or proc.stdout or b'')[:300]
            logger.warning('adb %s rc=%s err=%s', label, proc.returncode, last_err)
        except Exception as exc:
            last_err = str(exc)
            logger.warning('adb %s failed: %s', label, exc)
    if driver is not None:
        try:
            with _DRIVER_LOCK:
                driver.execute_script('mobile: clickGesture', {'x': int(x), 'y': int(y)})
            return
        except Exception as exc:
            logger.warning('Appium clickGesture failed: %s', exc)
    if last_err:
        logger.warning('tap exhausted device=%s (%s,%s) last=%s', device_id, x, y, last_err)


def _fast_swipe(device_id: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 200, driver=None, session_id: int = None):
    duration_ms = max(50, int(duration_ms))
    x1, y1 = _clamp_xy(device_id, x1, y1, session_id=session_id)
    x2, y2 = _clamp_xy(device_id, x2, y2, session_id=session_id)
    try:
        proc = _adb(
            device_id, 'shell', 'input', 'swipe',
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(duration_ms),
            timeout=5,
        )
        if proc.returncode == 0:
            return
    except Exception as exc:
        logger.debug('adb swipe failed, fallback Appium: %s', exc)
    if driver is None:
        return
    try:
        driver.execute_script('mobile: dragGesture', {
            'startX': int(x1),
            'startY': int(y1),
            'endX': int(x2),
            'endY': int(y2),
            'speed': max(800, int(1000 * 300 / max(duration_ms, 50))),
        })
    except Exception:
        left = min(int(x1), int(x2))
        top = min(int(y1), int(y2))
        width = max(1, abs(int(x2) - int(x1)))
        height = max(1, abs(int(y2) - int(y1)))
        if abs(x2 - x1) >= abs(y2 - y1):
            direction = 'right' if x2 >= x1 else 'left'
        else:
            direction = 'down' if y2 >= y1 else 'up'
        driver.execute_script('mobile: swipeGesture', {
            'left': left,
            'top': top,
            'width': width,
            'height': height,
            'direction': direction,
            'percent': 1.0,
        })


def get_latest_frame(session_id: int) -> Dict[str, Any]:
    """HTTP polling fallback when WebSocket is unavailable (e.g. runserver)."""
    state = _get_runtime(session_id)
    image = state.get('last_frame') or ''
    screencap_ok = state.get('screencap_ok')
    screencap_error = state.get('screencap_error') or ''
    device_width = state.get('device_width') or 0
    device_height = state.get('device_height') or 0
    steps = list(state.get('steps') or [])
    runtime_alive = bool(state) and not state.get('stop')
    mirror_mode = state.get('mirror_mode') or 'screenshot'

    session_status = None
    try:
        from apps.app_automation.models import AppRecordingSession
        session = AppRecordingSession.objects.select_related('device').filter(id=session_id).first()
        if session:
            session_status = session.status
            if session.status == 'failed' and not screencap_error:
                screencap_ok = False
                screencap_error = session.error_message or '录制会话已失败'
            if not device_width:
                device_width = session.screen_width or 0
            if not device_height:
                device_height = session.screen_height or 0
            if not steps and session.ui_flow:
                steps = list(session.ui_flow or [])
    except Exception:
        session = None

    if not image and runtime_alive:
        driver = state.get('driver')
        device_serial = state.get('device_id') or ''
        # Only try live capture after Appium session is ready
        if state.get('ready'):
            png = _driver_screenshot(driver)
            if not png and device_serial:
                png = _screencap_adb_fallback(device_serial)
            if png:
                max_w = int(state.get('stream_max_w') or 1080)
                jpeg_q = int(state.get('stream_jpeg_quality') or 70)
                image, iw, ih = _png_to_stream_jpeg(png, max_w=max_w, quality=jpeg_q)
                device_width = device_width or iw
                device_height = device_height or ih
                screencap_ok = True
                screencap_error = ''
                _set_runtime(
                    session_id,
                    last_frame=image,
                    device_width=device_width,
                    device_height=device_height,
                    screencap_ok=True,
                    screencap_error='',
                )

    return {
        'ready': bool(state.get('ready')) or bool(image) or mirror_mode == 'scrcpy',
        'image': image,
        'device_width': device_width,
        'device_height': device_height,
        'steps': steps,
        'screencap_ok': screencap_ok,
        'screencap_error': screencap_error,
        'status': 'recording' if runtime_alive else (session_status or 'stopped'),
        'session_status': session_status,
        'mirror_mode': mirror_mode,
        'stream_quality': state.get('stream_quality') or 'balanced',
    }


def _template_dir() -> Path:
    base = Path(settings.BASE_DIR) / 'apps' / 'app_automation' / 'Template' / 'recorded'
    base.mkdir(parents=True, exist_ok=True)
    return base


def _create_image_element(project, name: str, png_bytes: bytes, created_by=None):
    from apps.app_automation.models import AppElement
    from apps.app_automation.constants import ElementType

    file_hash = hashlib.md5(png_bytes).hexdigest()
    existing = AppElement.objects.filter(project=project, config__file_hash=file_hash, is_active=True).first()
    if existing:
        return existing, False

    # ASCII 文件名，避免部分环境下中文路径导致 Airtest 匹配异常
    filename = f"rec_{int(time.time())}_{file_hash[:10]}.png"
    path = _template_dir() / filename
    path.write_bytes(png_bytes)
    rel = f'recorded/{filename}'
    unique_name = f'{name}_{file_hash[:8]}_{int(time.time())}'[:200]
    el = AppElement.objects.create(
        project=project,
        name=unique_name,
        element_type=ElementType.IMAGE,
        config={
            'image_path': rel,
            'image_category': 'recorded',
            'threshold': 0.55,
            'image_threshold': 0.55,
            'rgb': False,
            'file_hash': file_hash,
        },
        created_by=created_by,
        is_active=True,
        tags=['recorded'],
    )
    return el, True


def _crop_around(
    png_bytes: bytes,
    x: int,
    y: int,
    half: int = CROP_HALF,
    win_w: int = 0,
    win_h: int = 0,
) -> Optional[bytes]:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png_bytes))
        w, h = img.size
        # 窗口坐标 -> 截图像素坐标（Appium window_size 与 screenshot 分辨率常不一致）
        if win_w and win_h and (w != win_w or h != win_h):
            x = int(round(x * w / float(win_w)))
            y = int(round(y * h / float(win_h)))
        left = max(0, int(x) - half)
        top = max(0, int(y) - half)
        right = min(w, int(x) + half)
        bottom = min(h, int(y) + half)
        if right - left < 10 or bottom - top < 10:
            return None
        cropped = img.crop((left, top, right, bottom))
        buf = io.BytesIO()
        cropped.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as exc:
        logger.warning('crop failed: %s', exc)
        return None


def start_app_recording_session(session, stream_quality: str = 'balanced') -> None:
    """Spawn recording worker: prefer scrcpy mirror, fallback to Appium screenshots.

    Heavy work runs in background so the HTTP create API returns quickly.
    """
    from apps.app_automation.models import AppRecordingSession
    from apps.app_automation.services.appium_server import (
        create_android_driver,
        ensure_adb_device_online,
        ensure_appium_running,
        ensure_device_appium_apks,
    )
    from apps.app_automation.services.scrcpy_mirror import ScrcpyMirrorSession

    if not session.device_id:
        raise ValueError('必须选择 Android 设备')

    device = session.device
    device_id = device.device_id
    session_id = session.id
    project_id = session.project_id
    user = session.created_by
    quality_preset = resolve_stream_quality(stream_quality)

    session.screen_width = session.screen_width or 0
    session.screen_height = session.screen_height or 0
    session.status = 'recording'
    session.started_at = timezone.now()
    session.error_message = ''
    session.ui_flow = []
    session.save(update_fields=[
        'screen_width', 'screen_height', 'status', 'started_at',
        'error_message', 'ui_flow', 'updated_at',
    ])

    try:
        if hasattr(device, 'lock'):
            device.lock(user)
    except Exception as exc:
        logger.warning('device lock failed: %s', exc)

    event_queue: queue.Queue = queue.Queue()
    steps: List[Dict[str, Any]] = []

    _set_runtime(
        session_id,
        stop=False,
        ready=False,
        event_queue=event_queue,
        steps=steps,
        device_id=device_id,
        device_width=0,
        device_height=0,
        screencap_ok=None,
        screencap_error='正在连接设备…',
        driver=None,
        mirror_mode='pending',
        stream_quality=quality_preset['mode'],
        stream_max_w=quality_preset['max_w'],
        stream_jpeg_quality=quality_preset['quality'],
        frame_interval=quality_preset['frame_interval'],
    )

    def worker():
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        last_frame_b64 = ''
        dev_w, dev_h = 0, 0
        driver = None
        server_url = None
        mirror_mode = 'screenshot'
        scrcpy_session = None
        try:
            close_old_connections()
            _channel_send(session_id, {
                'event': 'status',
                'status': 'recording',
                'message': '正在检查设备连接…',
            })

            _set_runtime(session_id, screencap_error='正在检查设备 adb 连接…')
            ensure_adb_device_online(device_id, timeout=45.0)

            try:
                w0, h0 = _wm_size(device_id)
                if w0 and h0:
                    dev_w, dev_h = w0, h0
                    _publish_device_size(session_id, dev_w, dev_h)
            except Exception:
                pass

            # --- Prefer scrcpy realtime mirror ---
            h264_relay_q: queue.Queue = queue.Queue(maxsize=3)

            def _on_h264_chunk(chunk: bytes):
                """背压：队列满时丢弃最旧帧，避免 Channels/Redis 堆积。"""
                if not chunk or _get_runtime(session_id).get('stop'):
                    return
                try:
                    h264_relay_q.put_nowait(chunk)
                except queue.Full:
                    try:
                        h264_relay_q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        h264_relay_q.put_nowait(chunk)
                    except queue.Full:
                        pass

            def _h264_relay_loop():
                while not _get_runtime(session_id).get('stop'):
                    try:
                        chunk = h264_relay_q.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    if not chunk:
                        continue
                    try:
                        _channel_send(session_id, {
                            'event': 'h264',
                            'data': base64.b64encode(chunk).decode('ascii'),
                            'device_width': _get_runtime(session_id).get('device_width') or 0,
                            'device_height': _get_runtime(session_id).get('device_height') or 0,
                        })
                    except Exception as exc:
                        logger.debug('h264 relay send failed: %s', exc)

            h264_relay_thread = threading.Thread(
                target=_h264_relay_loop,
                name=f'app-recording-h264-{session_id}',
                daemon=True,
            )
            h264_relay_thread.start()
            _set_runtime(session_id, h264_relay_thread=h264_relay_thread)

            def _on_scrcpy_status(msg: str):
                _set_runtime(session_id, screencap_error=msg)
                _channel_send(session_id, {
                    'event': 'status',
                    'status': 'recording',
                    'message': msg,
                })

            _set_runtime(session_id, screencap_error='正在尝试启动 scrcpy 实时投屏…')
            scrcpy_session = ScrcpyMirrorSession(
                device_id=device_id,
                session_id=session_id,
                on_chunk=_on_h264_chunk,
                on_status=_on_scrcpy_status,
            )
            if scrcpy_session.start(timeout=18.0):
                mirror_mode = 'scrcpy'
                _set_runtime(
                    session_id,
                    ready=True,
                    mirror_mode='scrcpy',
                    scrcpy_mirror=scrcpy_session,
                    device_width=dev_w,
                    device_height=dev_h,
                    screencap_ok=True,
                    screencap_error='',
                )
                _channel_send(session_id, {
                    'event': 'mirror_mode',
                    'mirror_mode': 'scrcpy',
                    'screen_width': dev_w,
                    'screen_height': dev_h,
                })
                _channel_send(session_id, {
                    'event': 'status',
                    'status': 'recording',
                    'screen_width': dev_w,
                    'screen_height': dev_h,
                    'mirror_mode': 'scrcpy',
                    'message': '录制已开始（scrcpy 实时投屏）',
                })
            else:
                err = scrcpy_session.error or 'scrcpy 不可用'
                logger.warning('scrcpy mirror failed, fallback screenshot: %s', err)
                try:
                    scrcpy_session.stop()
                except Exception:
                    pass
                scrcpy_session = None
                mirror_mode = 'screenshot'
                _channel_send(session_id, {
                    'event': 'mirror_mode',
                    'mirror_mode': 'screenshot',
                    'message': f'scrcpy 不可用，回退截屏投屏：{err}',
                })

                # Screenshot path: start Appium for screenshots
                _set_runtime(session_id, screencap_error='正在启动 Appium Server（截屏回退）…')
                _channel_send(session_id, {
                    'event': 'status',
                    'status': 'recording',
                    'message': '正在启动 Appium（截屏回退）…',
                })
                server_url = ensure_appium_running(timeout=60.0)

                _set_runtime(session_id, screencap_error='正在检测/安装设备端 Appium 组件…')
                ensure_device_appium_apks(device_id)
                # 不调用 prepare_appium_settings（会按 HOME），避免回退截屏时抢前台

                _set_runtime(session_id, screencap_error='正在创建 Appium 设备会话…')
                driver = create_android_driver(
                    device_id, server_url=server_url, steal_focus=False,
                )
                dw, dh = _driver_window_size(driver)
                if dw and dh:
                    dev_w, dev_h = dw, dh
                    AppRecordingSession.objects.filter(id=session_id).update(
                        screen_width=dev_w, screen_height=dev_h,
                    )

                _set_runtime(
                    session_id,
                    ready=True,
                    driver=driver,
                    mirror_mode='screenshot',
                    device_width=dev_w,
                    device_height=dev_h,
                    screencap_error='',
                )
                _channel_send(session_id, {
                    'event': 'status',
                    'status': 'recording',
                    'screen_width': dev_w,
                    'screen_height': dev_h,
                    'mirror_mode': 'screenshot',
                    'message': '录制已开始（截屏回退）',
                })

            fail_count = 0
            dirty_steps = False
            steps_lock = threading.Lock()
            project = None
            try:
                from apps.app_automation.models import AppProject
                project = AppProject.objects.filter(id=project_id).first()
            except Exception:
                project = None

            def _flush_steps_db(force: bool = False):
                nonlocal dirty_steps
                if not dirty_steps and not force:
                    return
                try:
                    with steps_lock:
                        snapshot = list(steps)
                    AppRecordingSession.objects.filter(id=session_id).update(ui_flow=snapshot)
                    dirty_steps = False
                except Exception as exc:
                    logger.debug('flush steps db failed: %s', exc)

            def _capture_frame_screenshot():
                nonlocal last_frame_b64, fail_count, dev_w, dev_h
                if not event_queue.empty():
                    return False
                png = _driver_screenshot(driver) or _screencap_adb_fallback(device_id)
                if png:
                    fail_count = 0
                    worker._last_png = png
                    st = _get_runtime(session_id)
                    max_w = int(st.get('stream_max_w') or quality_preset['max_w'])
                    jpeg_q = int(st.get('stream_jpeg_quality') or quality_preset['quality'])
                    image_data, iw, ih = _png_to_stream_jpeg(png, max_w=max_w, quality=jpeg_q)
                    # 触摸坐标只用主屏 wm size；截图像素仅作兜底（且不可小于已有主屏）
                    try:
                        cw, ch = _wm_size(device_id)
                        if cw and ch:
                            if cw != dev_w or ch != dev_h:
                                dev_w, dev_h = cw, ch
                                _publish_device_size(session_id, dev_w, dev_h, mirror_mode='screenshot')
                    except Exception:
                        if (not dev_w or not dev_h) and iw and ih:
                            dev_w, dev_h = iw, ih
                            _publish_device_size(session_id, dev_w, dev_h, mirror_mode='screenshot')
                    b64 = image_data.split(',', 1)[-1] if ',' in image_data else image_data
                    with steps_lock:
                        steps_snap = list(steps)
                    _set_runtime(
                        session_id,
                        last_frame=image_data,
                        device_width=dev_w,
                        device_height=dev_h,
                        screencap_ok=True,
                        screencap_error='',
                        steps=steps_snap,
                    )
                    if b64 != last_frame_b64:
                        last_frame_b64 = b64
                        _channel_send(session_id, {
                            'event': 'frame',
                            'image': image_data,
                            'device_width': dev_w or 0,
                            'device_height': dev_h or 0,
                        })
                    return True
                fail_count += 1
                if fail_count == 1 or fail_count % 8 == 0:
                    err = (
                        f'截图失败（连续 {fail_count} 次）。'
                        f'请检查设备连接。设备={device_id}'
                    )
                    _set_runtime(session_id, screencap_ok=False, screencap_error=err)
                    _channel_send(session_id, {'event': 'error', 'message': err})
                return False

            def _capture_crop_frame_adb():
                """低频 adb 截屏：供元素裁剪 + HTTP 轮询兜底（不影响 scrcpy 显示）。"""
                nonlocal last_frame_b64, dev_w, dev_h
                # 横竖屏切换时刷新主屏逻辑分辨率（忽略 scrcpy 虚拟屏）
                try:
                    cw, ch = _wm_size(device_id)
                    if cw and ch and (cw != dev_w or ch != dev_h):
                        dev_w, dev_h = cw, ch
                        _publish_device_size(session_id, dev_w, dev_h, mirror_mode='scrcpy')
                except Exception:
                    pass
                png = _screencap_adb_fallback(device_id)
                if not png:
                    return False
                worker._last_png = png
                st = _get_runtime(session_id)
                max_w = int(st.get('stream_max_w') or quality_preset['max_w'])
                jpeg_q = int(st.get('stream_jpeg_quality') or quality_preset['quality'])
                image_data, iw, ih = _png_to_stream_jpeg(png, max_w=max_w, quality=jpeg_q)
                b64 = image_data.split(',', 1)[-1] if ',' in image_data else image_data
                _set_runtime(
                    session_id,
                    last_frame=image_data,
                    device_width=dev_w,
                    device_height=dev_h,
                    screencap_ok=True,
                )
                # HTTP 轮询客户端也能看到画面（runserver 无 WS 时）
                if b64 != last_frame_b64:
                    last_frame_b64 = b64
                    if not _get_runtime(session_id).get('ws_preferred'):
                        _channel_send(session_id, {
                            'event': 'frame',
                            'image': image_data,
                            'device_width': dev_w or 0,
                            'device_height': dev_h or 0,
                            'mirror_mode': 'scrcpy',
                        })
                return True

            def gesture_loop():
                nonlocal dirty_steps
                os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
                close_old_connections()
                while not _get_runtime(session_id).get('stop'):
                    try:
                        ev = event_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    batch = [ev]
                    while True:
                        try:
                            batch.append(event_queue.get_nowait())
                        except queue.Empty:
                            break
                    for item in batch:
                        if (item.get('type') or '').lower() == '_stop':
                            continue
                        try:
                            with steps_lock:
                                runtime_driver = _get_runtime(session_id).get('driver')
                                _handle_gesture(
                                    session_id=session_id,
                                    project=project,
                                    project_id=project_id,
                                    device_id=device_id,
                                    driver=runtime_driver,
                                    event=item,
                                    steps=steps,
                                    last_frame_png=getattr(worker, '_last_png', None),
                                    created_by=user,
                                    steps_lock=steps_lock,
                                )
                            dirty_steps = True
                        except Exception as exc:
                            logger.exception('gesture handle failed: %s', exc)
                            _channel_send(session_id, {'event': 'error', 'message': str(exc)})
                    if dirty_steps:
                        _flush_steps_db()
                close_old_connections()

            gesture_thread = threading.Thread(
                target=gesture_loop,
                name=f'app-recording-gesture-{session_id}',
                daemon=True,
            )
            gesture_thread.start()
            _set_runtime(session_id, gesture_thread=gesture_thread, steps_lock=steps_lock)

            last_size_ts = 0.0
            last_health_ts = 0.0
            last_crop_ts = 0.0
            recover_fail_count = 0
            while not _get_runtime(session_id).get('stop'):
                if mirror_mode == 'scrcpy':
                    now = time.time()
                    # 低频 adb 截屏：供元素裁剪 + HTTP 轮询兜底（避免打挂 USB）
                    if now - last_crop_ts >= 2.5:
                        last_crop_ts = now
                        try:
                            _capture_crop_frame_adb()
                        except Exception as exc:
                            logger.debug('crop frame capture failed: %s', exc)

                    # 健康检查：ADB 掉线 / scrcpy 挂了则自动恢复（勿 kill-server）
                    health_interval = min(15.0, 3.0 + recover_fail_count * 2.0)
                    if now - last_health_ts >= health_interval:
                        last_health_ts = now
                        online = _adb_is_online(device_id)
                        alive = bool(scrcpy_session and scrcpy_session.is_alive())
                        if not online or not alive:
                            msg = (
                                'ADB 连接中断，正在重连…'
                                if not online
                                else '投屏中断，正在恢复 scrcpy…'
                            )
                            logger.warning(
                                'recording recover session=%s online=%s scrcpy_alive=%s fail=%s',
                                session_id, online, alive, recover_fail_count,
                            )
                            _set_runtime(session_id, screencap_error=msg)
                            _channel_send(session_id, {
                                'event': 'status',
                                'status': 'recording',
                                'message': msg,
                            })
                            try:
                                if scrcpy_session:
                                    try:
                                        scrcpy_session.stop()
                                    except Exception:
                                        pass
                                    scrcpy_session = None
                                # 退避：避免 USB 抖动时疯狂重连
                                if recover_fail_count > 0:
                                    time.sleep(min(8.0, 0.8 * (2 ** min(recover_fail_count, 3))))
                                ensure_adb_device_online(device_id, timeout=25.0)
                                scrcpy_session = ScrcpyMirrorSession(
                                    device_id=device_id,
                                    session_id=session_id,
                                    on_chunk=_on_h264_chunk,
                                    on_status=_on_scrcpy_status,
                                )
                                if scrcpy_session.start(timeout=18.0):
                                    recover_fail_count = 0
                                    _set_runtime(
                                        session_id,
                                        scrcpy_mirror=scrcpy_session,
                                        screencap_ok=True,
                                        screencap_error='',
                                    )
                                    _channel_send(session_id, {
                                        'event': 'status',
                                        'status': 'recording',
                                        'mirror_mode': 'scrcpy',
                                        'message': '投屏已恢复',
                                    })
                                else:
                                    recover_fail_count += 1
                                    err = getattr(scrcpy_session, 'error', '') or 'scrcpy 恢复失败'
                                    _set_runtime(session_id, screencap_error=err)
                                    _channel_send(session_id, {
                                        'event': 'status',
                                        'status': 'recording',
                                        'message': err,
                                    })
                            except Exception as exc:
                                recover_fail_count += 1
                                logger.warning('recording adb/scrcpy recover failed: %s', exc)
                                _set_runtime(session_id, screencap_error=str(exc))
                                _channel_send(session_id, {
                                    'event': 'status',
                                    'status': 'recording',
                                    'message': f'重连失败: {exc}',
                                })

                    # 分辨率用轻量 wm/dumpsys，不要靠全屏截图（截图极易把 USB 打挂）
                    if now - last_size_ts >= 5.0:
                        last_size_ts = now
                        try:
                            cw, ch = _wm_size(device_id)
                            if cw and ch and (cw != dev_w or ch != dev_h):
                                dev_w, dev_h = cw, ch
                                _publish_device_size(session_id, dev_w, dev_h, mirror_mode='scrcpy')
                        except Exception:
                            pass

                    if dirty_steps:
                        _flush_steps_db()
                    time.sleep(0.25)
                else:
                    if event_queue.empty():
                        _capture_frame_screenshot()
                    if dirty_steps:
                        _flush_steps_db()
                    interval = float(
                        _get_runtime(session_id).get('frame_interval')
                        or quality_preset['frame_interval']
                    )
                    time.sleep(max(0.08, interval))

            try:
                gesture_thread.join(timeout=5)
            except Exception:
                pass

            while True:
                try:
                    ev = event_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    with steps_lock:
                        _handle_gesture(
                            session_id=session_id,
                            project=project,
                            project_id=project_id,
                            device_id=device_id,
                            driver=_get_runtime(session_id).get('driver'),
                            event=ev,
                            steps=steps,
                            last_frame_png=getattr(worker, '_last_png', None),
                            created_by=user,
                            steps_lock=steps_lock,
                        )
                    dirty_steps = True
                except Exception:
                    pass
            _flush_steps_db(force=True)

            close_old_connections()
            final_steps = normalize_recorded_steps(list(steps))
            AppRecordingSession.objects.filter(id=session_id).update(
                status='stopped',
                ui_flow=final_steps,
                stopped_at=timezone.now(),
                error_message='',
            )
            _channel_send(session_id, {
                'event': 'status',
                'status': 'stopped',
                'steps': final_steps,
                'message': f'录制已停止，共 {len(final_steps)} 步',
            })
        except Exception as exc:
            logger.exception('app recording worker failed: %s', exc)
            try:
                close_old_connections()
                AppRecordingSession.objects.filter(id=session_id).update(
                    status='failed',
                    ui_flow=normalize_recorded_steps(list(steps)),
                    stopped_at=timezone.now(),
                    error_message=str(exc)[:2000],
                )
                _set_runtime(session_id, screencap_ok=False, screencap_error=str(exc)[:500])
                _channel_send(session_id, {'event': 'status', 'status': 'failed', 'message': str(exc)})
            except Exception:
                pass
        finally:
            if scrcpy_session is not None:
                try:
                    scrcpy_session.stop()
                except Exception:
                    pass
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            try:
                close_old_connections()
                from apps.app_automation.models import AppDevice
                d = AppDevice.objects.filter(id=device.id).first()
                if d and hasattr(d, 'unlock'):
                    d.unlock()
            except Exception:
                pass
            _clear_runtime(session_id)
            close_old_connections()

    thread = threading.Thread(target=worker, name=f'app-recording-{session_id}', daemon=True)
    thread.start()
    _set_runtime(
        session_id,
        thread=thread,
        stop=False,
        event_queue=event_queue,
        steps=steps,
        device_id=device_id,
    )


def _persist_steps(session_id: int, steps: List[Dict[str, Any]], step: Dict[str, Any], *, write_db: bool = False):
    """Update runtime immediately; DB write is optional to keep taps snappy."""
    from apps.app_automation.models import AppRecordingSession

    _set_runtime(session_id, steps=list(steps))
    _channel_send(session_id, {'event': 'step_added', 'step': step, 'steps': list(steps)})
    if write_db:
        try:
            AppRecordingSession.objects.filter(id=session_id).update(ui_flow=list(steps))
        except Exception as exc:
            logger.debug('persist steps db failed: %s', exc)


def _normalize_recorded_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """将旧录制格式 (action/text) 转为 SceneBuilder / UiFlowRunner 格式 (type/config)。"""
    if not isinstance(step, dict):
        return step
    if step.get('type') and isinstance(step.get('config'), dict):
        # 兼容旧字段：input 曾用 text
        cfg = dict(step['config'])
        if step.get('type') == 'input' and 'value' not in cfg and step.get('text') is not None:
            cfg['value'] = step['text']
            return {**step, 'config': cfg}
        return step

    action = (step.get('type') or step.get('action') or '').lower()
    name = step.get('name') or action or '步骤'
    if action in ('click', 'touch', 'tap'):
        element_id = step.get('element_id')
        if element_id:
            return {
                'type': 'click',
                'name': name,
                'config': {
                    'selector_type': 'image',
                    'selector': step.get('selector') or '',
                    'element_id': element_id,
                    'image_scope': step.get('image_scope') or 'recorded',
                    'image_threshold': step.get('image_threshold', 0.7),
                    'timeout': step.get('timeout', 5),
                },
            }
        x, y = step.get('x'), step.get('y')
        selector = step.get('selector')
        if selector is None and x is not None and y is not None:
            selector = [int(x), int(y)]
        return {
            'type': 'click',
            'name': name,
            'config': {
                'selector_type': 'pos',
                'selector': selector if selector is not None else '',
                'timeout': step.get('timeout', 5),
            },
        }
    if action == 'swipe':
        start = step.get('start')
        end = step.get('end')
        duration = step.get('duration', 0.3)
        return {
            'type': 'swipe',
            'name': name,
            'config': {
                'selector_type': 'pos',
                'start': start,
                'end': end,
                'duration': duration,
                'direction': step.get('direction') or 'up',
            },
        }
    if action in ('input', 'text'):
        return {
            'type': 'input',
            'name': name,
            'config': {
                'selector_type': step.get('selector_type') or 'pos',
                'selector': step.get('selector') or '',
                'value': step.get('value') if step.get('value') is not None else (step.get('text') or ''),
                'send_enter': bool(step.get('send_enter', False)),
                'image_scope': step.get('image_scope') or 'common',
                'image_threshold': step.get('image_threshold', 0.7),
            },
        }
    # 未知结构：尽量补 type，避免执行时被忽略
    if not step.get('type') and action:
        return {**step, 'type': action, 'config': step.get('config') or {}}
    return step


def normalize_recorded_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_normalize_recorded_step(s) for s in (steps or [])]


def _handle_gesture(*, session_id, project=None, project_id=None, device_id, driver, event, steps, last_frame_png, created_by, mark_dirty=None, steps_lock=None):
    """先执行设备操作，再写录制步骤。项目缺失时仍要点击/滑动，只是不落库裁图。"""
    from apps.app_automation.models import AppProject
    from contextlib import nullcontext

    etype = (event.get('type') or '').lower()
    if project is None and project_id:
        try:
            project = AppProject.objects.filter(id=project_id).first()
        except Exception:
            project = None
    lock_cm = steps_lock or _get_runtime(session_id).get('steps_lock')
    step_guard = lock_cm if lock_cm is not None else nullcontext()

    if etype in ('tap', 'click'):
        x, y = int(event['x']), int(event['y'])
        png_before = last_frame_png
        # 立刻点设备；裁图/建元素放到后台，不堵下一次点击
        logger.info('recording tap session=%s device=%s xy=(%s,%s)', session_id, device_id, x, y)
        _fast_tap(device_id, x, y, driver=driver, session_id=session_id)

        if not project:
            logger.warning('recording tap: project missing (project_id=%s), skip step persist', project_id)
            return

        element_name = event.get('name') or f'录制点击_{len(steps)+1}'
        step = {
            'type': 'click',
            'name': element_name,
            'config': {
                'selector_type': 'pos',
                'selector': [x, y],
                'timeout': 5,
            },
        }
        steps.append(step)
        step_ref = step
        _persist_steps(session_id, steps, step, write_db=False)

        if png_before:
            state = _get_runtime(session_id)
            win_w = int(state.get('device_width') or 0)
            win_h = int(state.get('device_height') or 0)

            def _bind_element(png=png_before, sx=x, sy=y, ref=step_ref, pname=element_name, ww=win_w, wh=win_h):
                os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
                close_old_connections()
                try:
                    # scrcpy 模式下不轮询截屏；点击后再按需截一张做元素裁剪
                    frame = png
                    if frame is None:
                        frame = _screencap_adb_fallback(device_id)
                    cropped = _crop_around(frame, sx, sy, win_w=ww, win_h=wh) if frame else None
                    if not cropped:
                        return
                    el, _ = _create_image_element(project, pname, cropped, created_by=created_by)
                    image_path = (el.config or {}).get('image_path') or ''
                    image_file = image_path.split('/')[-1] if image_path else ''
                    with step_guard:
                        ref['name'] = el.name
                        # 保留坐标兜底：图片匹配失败时仍可按录制点点击
                        ref['config'] = {
                            'selector_type': 'image',
                            'selector': image_file,
                            'element_id': el.id,
                            'image_scope': 'recorded',
                            'image_threshold': 0.55,
                            'timeout': 4,
                            'fallback_pos': [sx, sy],
                        }
                        _persist_steps(session_id, steps, ref, write_db=False)
                except Exception as exc:
                    logger.warning('async bind element failed: %s', exc)
                finally:
                    close_old_connections()

            threading.Thread(
                target=_bind_element,
                name=f'rec-el-{session_id}-{len(steps)}',
                daemon=True,
            ).start()
        else:
            # 无缓存帧时仍异步截一张用于元素裁剪
            state = _get_runtime(session_id)
            win_w = int(state.get('device_width') or 0)
            win_h = int(state.get('device_height') or 0)

            def _bind_element_lazy(sx=x, sy=y, ref=step_ref, pname=element_name, ww=win_w, wh=win_h):
                os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
                close_old_connections()
                try:
                    frame = _screencap_adb_fallback(device_id)
                    cropped = _crop_around(frame, sx, sy, win_w=ww, win_h=wh) if frame else None
                    if not cropped:
                        return
                    el, _ = _create_image_element(project, pname, cropped, created_by=created_by)
                    image_path = (el.config or {}).get('image_path') or ''
                    image_file = image_path.split('/')[-1] if image_path else ''
                    with step_guard:
                        ref['name'] = el.name
                        ref['config'] = {
                            'selector_type': 'image',
                            'selector': image_file,
                            'element_id': el.id,
                            'image_scope': 'recorded',
                            'image_threshold': 0.55,
                            'timeout': 4,
                            'fallback_pos': [sx, sy],
                        }
                        _persist_steps(session_id, steps, ref, write_db=False)
                except Exception as exc:
                    logger.warning('async bind element failed: %s', exc)
                finally:
                    close_old_connections()

            threading.Thread(
                target=_bind_element_lazy,
                name=f'rec-el-{session_id}-{len(steps)}',
                daemon=True,
            ).start()
        return

    if etype == 'swipe':
        x1, y1 = int(event['x1']), int(event['y1'])
        x2, y2 = int(event['x2']), int(event['y2'])
        duration = int(event.get('duration_ms') or 180)
        logger.info(
            'recording swipe session=%s device=%s (%s,%s)->(%s,%s)',
            session_id, device_id, x1, y1, x2, y2,
        )
        _fast_swipe(device_id, x1, y1, x2, y2, duration, driver=driver, session_id=session_id)
        if not project:
            logger.warning('recording swipe: project missing (project_id=%s), skip step persist', project_id)
            return
        step = {
            'type': 'swipe',
            'name': event.get('name') or f'滑动_{len(steps)+1}',
            'config': {
                'selector_type': 'pos',
                'start': [x1, y1],
                'end': [x2, y2],
                'duration': max(0.05, duration / 1000.0),
                'direction': 'up',
            },
        }
        steps.append(step)
        _persist_steps(session_id, steps, step, write_db=False)
        return

    if etype in ('text', 'input'):
        text = event.get('text') or ''
        # 中文输入需要 Appium；手势线程默认不传 driver，从 runtime 取 / 按需拉起
        appium_driver = driver or _get_runtime(session_id).get('driver')
        if event.get('x') is not None and event.get('y') is not None:
            _fast_tap(device_id, int(event['x']), int(event['y']), driver=None, session_id=session_id)
            time.sleep(0.08)
        ok = _fast_input_text(device_id, text, driver=appium_driver, session_id=session_id)
        if not ok and _text_needs_unicode(text):
            _channel_send(session_id, {
                'event': 'error',
                'message': '中文输入失败：请先点击输入框聚焦；将优先用 UnicodeIME（不抢前台）',
            })
            return
        if not project:
            logger.warning('recording input: project missing (project_id=%s), skip step persist', project_id)
            return
        step = {
            'type': 'input',
            'name': event.get('name') or f'输入_{len(steps)+1}',
            'config': {
                'selector_type': 'pos',
                'selector': '',
                'value': text,
                'send_enter': False,
            },
        }
        steps.append(step)
        _persist_steps(session_id, steps, step, write_db=False)


def enqueue_recording_event(session_id: int, event: Dict[str, Any]):
    state = _get_runtime(session_id)
    q = state.get('event_queue')
    if q is None:
        raise ValueError('录制会话未在运行（可能服务重启）')
    if not state.get('ready'):
        raise ValueError('录制尚未就绪（投屏启动中），请等待画面出现后再操作')
    q.put(event)


def stop_app_recording_session(session, wait_timeout: float = 30.0):
    from apps.app_automation.models import AppRecordingSession

    state = _get_runtime(session.id)
    if state:
        _set_runtime(session.id, stop=True)
        mirror = state.get('scrcpy_mirror')
        if mirror is not None:
            try:
                mirror.stop()
            except Exception:
                pass
        # wake gesture waiter
        q = state.get('event_queue')
        if q is not None:
            try:
                q.put({'type': '_stop'})
            except Exception:
                pass
        gthread = state.get('gesture_thread')
        if gthread and gthread.is_alive():
            gthread.join(timeout=min(8.0, wait_timeout))
        thread = state.get('thread')
        if thread and thread.is_alive():
            thread.join(timeout=wait_timeout)

    session.refresh_from_db()
    if session.status == 'recording':
        steps = normalize_recorded_steps(
            _get_runtime(session.id).get('steps') or list(session.ui_flow or [])
        )
        session.status = 'stopped'
        session.ui_flow = steps
        session.stopped_at = timezone.now()
        session.error_message = (session.error_message or '') + '\n[System] 停止超时，已强制结束'
        session.save(update_fields=['status', 'ui_flow', 'stopped_at', 'error_message', 'updated_at'])
        try:
            if session.device_id and hasattr(session.device, 'unlock'):
                session.device.unlock()
        except Exception:
            pass
        _clear_runtime(session.id)


def save_recording_as_testcase(session, *, name: str = '', created_by=None):
    from apps.app_automation.models import AppTestCase

    # SceneBuilder / 执行器约定：ui_flow 为步骤列表（不是 {steps: [...]}）
    steps = normalize_recorded_steps(list(session.ui_flow or []))
    if not steps:
        raise ValueError('没有录制到任何步骤')
    case = AppTestCase.objects.create(
        project=session.project,
        name=(name or session.name or f'APP录制用例-{session.id}')[:200],
        description=f'由录制会话 #{session.id} 生成',
        ui_flow=steps,
        created_by=created_by or session.created_by,
    )
    session.test_case = case
    session.ui_flow = steps
    session.save(update_fields=['test_case', 'ui_flow', 'updated_at'])
    return case

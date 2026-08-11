"""Manage local Appium Server process for APP recording."""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_PROCESS: Optional[subprocess.Popen] = None
_STARTED_BY_US = False


def _default_config_values():
    return {
        'adb_path': 'adb',
        'appium_server_url': 'http://127.0.0.1:4723',
        'appium_command': 'appium',
        'appium_auto_start': True,
        'android_sdk_path': '',
    }


def get_appium_config():
    from apps.app_automation.models import AppTestConfig

    config, _ = AppTestConfig.objects.get_or_create(id=1, defaults=_default_config_values())
    return config


def _which_adb(adb_path: str = 'adb') -> Optional[Path]:
    adb_path = (adb_path or 'adb').strip() or 'adb'
    p = Path(adb_path)
    if p.is_file():
        return p.resolve()
    # Search PATH
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        if not folder:
            continue
        for name in ('adb.exe', 'adb'):
            cand = Path(folder) / name
            if cand.is_file():
                return cand.resolve()
    return None


def resolve_android_sdk_root(config=None) -> str:
    """Resolve ANDROID_HOME for Appium (must contain platform-tools)."""
    config = config or get_appium_config()
    configured = (getattr(config, 'android_sdk_path', None) or '').strip()
    if configured and Path(configured).is_dir():
        return str(Path(configured).resolve())

    for key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        val = (os.environ.get(key) or '').strip()
        if val and Path(val).is_dir():
            return str(Path(val).resolve())

    adb = _which_adb(getattr(config, 'adb_path', None) or 'adb')
    if adb and adb.parent.name.lower() == 'platform-tools':
        return str(adb.parent.parent.resolve())

    # Common install locations
    home = Path.home()
    candidates = [
        home / 'AppData' / 'Local' / 'Android' / 'Sdk',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Android' / 'Sdk',
        Path('C:/Android/Sdk'),
        Path('D:/Android/Sdk'),
        Path('E:/Android/Sdk'),
    ]
    for c in candidates:
        if c and (c / 'platform-tools').is_dir():
            return str(c.resolve())
    return ''


def _appium_env(config=None) -> dict:
    env = os.environ.copy()
    sdk = resolve_android_sdk_root(config)
    if sdk:
        env['ANDROID_HOME'] = sdk
        env['ANDROID_SDK_ROOT'] = sdk
        platform_tools = str(Path(sdk) / 'platform-tools')
        if platform_tools not in env.get('PATH', ''):
            env['PATH'] = platform_tools + os.pathsep + env.get('PATH', '')
        # Also set for current process so child libs see it
        os.environ['ANDROID_HOME'] = sdk
        os.environ['ANDROID_SDK_ROOT'] = sdk
        logger.info('Using ANDROID_HOME=%s for Appium', sdk)
    return env


def _resolve_adb_exe(config=None) -> str:
    config = config or get_appium_config()
    adb = _which_adb(getattr(config, 'adb_path', None) or 'adb')
    if adb:
        return str(adb)
    sdk = resolve_android_sdk_root(config)
    if sdk:
        for name in ('adb.exe', 'adb'):
            cand = Path(sdk) / 'platform-tools' / name
            if cand.is_file():
                return str(cand.resolve())
    return 'adb'


def _adb_run(udid: str, *args, timeout: float = 60, config=None) -> subprocess.CompletedProcess:
    adb = _resolve_adb_exe(config)
    cmd = [adb, '-s', udid, *args]
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _adb_run_global(*args, timeout: float = 30, config=None) -> subprocess.CompletedProcess:
    adb = _resolve_adb_exe(config)
    cmd = [adb, *args]
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _list_adb_devices(config=None) -> List[Tuple[str, str]]:
    """Return [(serial, state), ...] from `adb devices`."""
    try:
        proc = _adb_run_global('devices', timeout=15, config=config)
        out = (proc.stdout or b'').decode('utf-8', errors='ignore')
    except Exception:
        return []
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith('list of devices'):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def _device_state(udid: str, config=None) -> str:
    try:
        proc = _adb_run(udid, 'get-state', timeout=10, config=config)
        out = (proc.stdout or b'').decode('utf-8', errors='ignore').strip()
        err = (proc.stderr or b'').decode('utf-8', errors='ignore').strip()
        if proc.returncode == 0 and out:
            return out
        text = (err or out).lower()
        if 'offline' in text:
            return 'offline'
        if 'unauthorized' in text:
            return 'unauthorized'
        if 'not found' in text:
            return 'not_found'
        # Fall back to devices list
        for serial, state in _list_adb_devices(config=config):
            if serial == udid:
                return state
        return 'not_found'
    except Exception:
        return 'unknown'


def ensure_adb_device_online(udid: str, timeout: float = 45.0, config=None) -> str:
    """
    Make sure the target device is online for the configured adb binary.
    Tries reconnect for wireless (ip:port) and waits until state=device.
    """
    config = config or get_appium_config()
    udid = (udid or '').strip()
    if not udid:
        raise RuntimeError('设备序列号为空')

    deadline = time.time() + timeout
    last_state = _device_state(udid, config=config)
    if last_state == 'device':
        return last_state

    is_wireless = ':' in udid  # e.g. 192.168.1.2:5555
    attempted_reconnect = False

    while time.time() < deadline:
        last_state = _device_state(udid, config=config)
        if last_state == 'device':
            logger.info('ADB device online: %s', udid)
            return last_state

        if last_state == 'unauthorized':
            raise RuntimeError(
                f'设备 {udid} 未授权 USB 调试。请在手机上点「允许 USB 调试」，'
                '勾选始终允许后重试。'
            )

        if is_wireless and not attempted_reconnect:
            attempted_reconnect = True
            logger.info('Wireless device %s not ready (%s); trying adb connect', udid, last_state)
            try:
                _adb_run_global('disconnect', udid, timeout=10, config=config)
            except Exception:
                pass
            try:
                proc = _adb_run_global('connect', udid, timeout=20, config=config)
                logger.info(
                    'adb connect %s -> %s',
                    udid,
                    ((proc.stdout or b'') + (proc.stderr or b'')).decode('utf-8', errors='ignore')[:200],
                )
            except Exception as exc:
                logger.warning('adb connect failed: %s', exc)
            time.sleep(1.5)
            continue

        if last_state in ('offline', 'not_found', 'unknown') and not is_wireless:
            # USB: nudge transport
            try:
                _adb_run(udid, 'reconnect', timeout=10, config=config)
            except Exception:
                pass
            try:
                _adb_run_global('wait-for-device', timeout=8, config=config)
            except Exception:
                pass

        time.sleep(1.0)

    online = [f'{s}({st})' for s, st in _list_adb_devices(config=config)]
    online_txt = '、'.join(online) if online else '无'
    hint = (
        '请优先选择 USB 设备；若用无线调试，请先在设备管理里重新「无线连接」，'
        '并确认 `adb devices` 显示为 device 而不是 offline。'
    )
    raise RuntimeError(
        f'设备 {udid} 当前不可用（状态={last_state}）。在线设备: {online_txt}。{hint}'
    )


def _package_installed(udid: str, package: str, config=None) -> bool:
    try:
        proc = _adb_run(udid, 'shell', 'pm', 'path', package, timeout=15, config=config)
        out = (proc.stdout or b'').decode('utf-8', errors='ignore')
        return proc.returncode == 0 and 'package:' in out
    except Exception:
        return False


def discover_appium_helper_apks() -> Dict[str, Path]:
    """
    Locate Appium helper APKs installed with uiautomator2 driver.
    Returns map: package_name -> apk path
    """
    home = Path.home()
    search_roots = [
        home / '.appium' / 'node_modules' / 'appium-uiautomator2-driver',
        home / 'AppData' / 'Roaming' / 'npm' / 'node_modules' / 'appium',
    ]
    # npm root -g
    try:
        root = subprocess.check_output(
            'npm root -g', shell=True, text=True, errors='ignore', timeout=10,
        ).strip()
        if root:
            search_roots.append(Path(root) / 'appium')
            search_roots.append(Path(root) / 'appium-uiautomator2-driver')
    except Exception:
        pass

    found: Dict[str, Path] = {}
    patterns = {
        'io.appium.settings': ('settings_apk-debug.apk', 'settings*.apk'),
        'io.appium.uiautomator2.server': ('appium-uiautomator2-server-v*.apk',),
        'io.appium.uiautomator2.server.test': (
            'appium-uiautomator2-server-debug-androidTest.apk',
            'appium-uiautomator2-server-*-androidTest.apk',
        ),
    }

    apk_files: List[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        try:
            apk_files.extend(root.rglob('*.apk'))
        except Exception:
            continue

    def _pick(names: tuple) -> Optional[Path]:
        for pattern in names:
            for f in apk_files:
                if f.name == pattern or f.match(pattern) or Path(f.name).match(pattern):
                    # Prefer versioned server apk over test apk for server package
                    return f
        # Fuzzy by substring
        for pattern in names:
            key = pattern.replace('*', '').replace('.apk', '')
            for f in apk_files:
                if key and key.lower() in f.name.lower():
                    if 'androidTest' in pattern and 'androidtest' not in f.name.lower():
                        continue
                    if 'androidTest' not in pattern and 'androidtest' in f.name.lower():
                        continue
                    if 'settings' in pattern.lower() and 'settings' not in f.name.lower():
                        continue
                    return f
        return None

    # More reliable explicit matching
    for f in apk_files:
        name = f.name.lower()
        if 'settings_apk' in name or (name.startswith('settings') and name.endswith('.apk')):
            found.setdefault('io.appium.settings', f)
        elif 'androidtest' in name and 'uiautomator2-server' in name:
            found.setdefault('io.appium.uiautomator2.server.test', f)
        elif 'uiautomator2-server-v' in name or (
            'uiautomator2-server' in name and 'androidtest' not in name and 'test' not in name
        ):
            # Prefer versioned server apk
            cur = found.get('io.appium.uiautomator2.server')
            if cur is None or ('-v' in f.name and '-v' not in cur.name):
                found['io.appium.uiautomator2.server'] = f

    # Fill gaps via patterns
    for pkg, pats in patterns.items():
        if pkg not in found:
            picked = _pick(pats)
            if picked:
                found[pkg] = picked

    return found


def prepare_appium_settings_on_device(udid: str, config=None) -> None:
    """
    Stabilize io.appium.settings on real devices (esp. Xiaomi / Android 14+/15).

    Crash root cause (targetSdk 35):
      Starting FGS with type location requires FOREGROUND_SERVICE_LOCATION
      + ACCESS_FINE/COARSE_LOCATION, and the app must be in an eligible state
      (activity visible / has while-in-use location grant).
    """
    config = config or get_appium_config()
    pkg = 'io.appium.settings'
    ensure_adb_device_online(udid, timeout=30.0, config=config)

    # Leave split-screen so Settings can become a normal resumed activity
    try:
        _adb_run(udid, 'shell', 'input', 'keyevent', 'KEYCODE_HOME', timeout=8, config=config)
        time.sleep(0.3)
    except Exception:
        pass

    # Battery / background whitelist
    for args in (
        ('shell', 'dumpsys', 'deviceidle', 'whitelist', f'+{pkg}'),
        ('shell', 'cmd', 'appops', 'set', pkg, 'RUN_IN_BACKGROUND', 'allow'),
        ('shell', 'cmd', 'appops', 'set', pkg, 'RUN_ANY_IN_BACKGROUND', 'allow'),
        ('shell', 'appops', 'set', pkg, 'WRITE_SETTINGS', 'allow'),
        ('shell', 'appops', 'set', pkg, 'PROJECT_MEDIA', 'allow'),
        ('shell', 'appops', 'set', pkg, 'GET_USAGE_STATS', 'allow'),
        ('shell', 'cmd', 'notification', 'allow_listener', f'{pkg}/.NLService'),
    ):
        try:
            _adb_run(udid, *args, timeout=10, config=config)
        except Exception:
            pass

    # Location + FGS perms MUST be granted before starting location-type FGS
    location_perms = [
        'android.permission.ACCESS_FINE_LOCATION',
        'android.permission.ACCESS_COARSE_LOCATION',
        'android.permission.ACCESS_BACKGROUND_LOCATION',
        'android.permission.FOREGROUND_SERVICE_LOCATION',
        'android.permission.FOREGROUND_SERVICE',
        'android.permission.POST_NOTIFICATIONS',
        'android.permission.READ_PHONE_STATE',
        'android.permission.RECORD_AUDIO',
        'android.permission.BLUETOOTH_CONNECT',
        'android.permission.BLUETOOTH_SCAN',
        'android.permission.WRITE_SECURE_SETTINGS',
    ]
    for perm in location_perms:
        try:
            _adb_run(udid, 'shell', 'pm', 'grant', pkg, perm, timeout=8, config=config)
        except Exception:
            pass

    # Force appops allow — MIUI may keep pm-grant false or set Uid mode=ignore
    for op in ('FINE_LOCATION', 'COARSE_LOCATION'):
        for args in (
            ('shell', 'cmd', 'appops', 'set', pkg, op, 'allow'),
            ('shell', 'appops', 'set', pkg, op, 'allow'),
            ('shell', 'cmd', 'appops', 'set', '--uid', pkg, op, 'allow'),
        ):
            try:
                _adb_run(udid, *args, timeout=8, config=config)
            except Exception:
                pass

    # Verify location actually granted (do NOT reinstall — that clears runtime grants)
    try:
        check = _adb_run(udid, 'shell', 'dumpsys', 'package', pkg, timeout=15, config=config)
        check_out = (check.stdout or b'').decode('utf-8', errors='ignore')
        fine_ok = 'android.permission.ACCESS_FINE_LOCATION: granted=true' in check_out
        coarse_ok = 'android.permission.ACCESS_COARSE_LOCATION: granted=true' in check_out
        if not (fine_ok or coarse_ok):
            # One more grant attempt
            for perm in (
                'android.permission.ACCESS_FINE_LOCATION',
                'android.permission.ACCESS_COARSE_LOCATION',
            ):
                _adb_run(udid, 'shell', 'pm', 'grant', pkg, perm, timeout=8, config=config)
            check = _adb_run(udid, 'shell', 'dumpsys', 'package', pkg, timeout=15, config=config)
            check_out = (check.stdout or b'').decode('utf-8', errors='ignore')
            fine_ok = 'android.permission.ACCESS_FINE_LOCATION: granted=true' in check_out
            coarse_ok = 'android.permission.ACCESS_COARSE_LOCATION: granted=true' in check_out
        if not (fine_ok or coarse_ok):
            raise RuntimeError(
                '无法授予 Appium Settings 定位权限（ACCESS_FINE/COARSE_LOCATION）。'
                '请在手机上手动打开：设置 → 应用 → Appium Settings → 权限 → 位置信息 → 始终允许，然后重试。'
            )
        logger.info('Location permission ok fine=%s coarse=%s', fine_ok, coarse_ok)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning('location permission verify failed: %s', exc)

    try:
        _adb_run(udid, 'shell', 'am', 'force-stop', pkg, timeout=8, config=config)
        time.sleep(0.4)
    except Exception:
        pass

    # 1) Bring activity to foreground first (eligible state for while-in-use location)
    try:
        _adb_run(
            udid, 'shell', 'am', 'start', '-W', '-n', f'{pkg}/.Settings',
            '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LAUNCHER',
            timeout=20, config=config,
        )
    except Exception as exc:
        logger.warning('start Appium Settings activity failed: %s', exc)
    time.sleep(1.2)

    # 2) Only then start location-type ForegroundService
    for svc in (f'{pkg}/.ForegroundService', f'{pkg}/.LocationService'):
        try:
            _adb_run(
                udid, 'shell', 'am', 'start-foreground-service', '-n', svc,
                timeout=10, config=config,
            )
        except Exception:
            try:
                _adb_run(udid, 'shell', 'am', 'startservice', '-n', svc, timeout=10, config=config)
            except Exception:
                pass
        time.sleep(0.4)

    # Wait until Appium's check would pass: dumpsys shows isForeground=true
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            proc = _adb_run(
                udid, 'shell', 'dumpsys', 'activity', 'services', pkg,
                timeout=10, config=config,
            )
            out = (proc.stdout or b'').decode('utf-8', errors='ignore')
            if 'isForeground=true' in out:
                logger.info('Appium Settings ForegroundService is up on %s', udid)
                return
            # Activity still resumed? poke FGS again
            if 'ServiceRecord' not in out or 'isForeground=false' in out or 'isForeground=true' not in out:
                try:
                    _adb_run(
                        udid, 'shell', 'am', 'start', '-n', f'{pkg}/.Settings',
                        timeout=10, config=config,
                    )
                    time.sleep(0.6)
                    _adb_run(
                        udid, 'shell', 'am', 'start-foreground-service',
                        '-n', f'{pkg}/.ForegroundService',
                        timeout=10, config=config,
                    )
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)

    logger.warning(
        'Appium Settings ForegroundService not confirmed on %s. '
        '请在手机上给 Appium Settings 开启「位置信息=始终允许」，并允许自启动。',
        udid,
    )


def _settings_fgs_keepalive(udid: str, stop_event: threading.Event, config=None):
    """While Appium creates session, keep Settings activity+FGS alive with correct order."""
    pkg = 'io.appium.settings'
    while not stop_event.wait(0.8):
        try:
            # Eligible state first, then FGS (avoids SecurityException on Android 15)
            _adb_run(udid, 'shell', 'am', 'start', '-n', f'{pkg}/.Settings', timeout=8, config=config)
            time.sleep(0.3)
            _adb_run(
                udid, 'shell', 'am', 'start-foreground-service',
                '-n', f'{pkg}/.ForegroundService',
                timeout=8, config=config,
            )
        except Exception:
            pass


def ensure_device_appium_apks(udid: str, force: bool = False) -> Dict[str, Any]:
    """
    If device is missing Appium helper apps, install them via adb.
    Called before creating UiAutomator2 session.
    """
    config = get_appium_config()
    # Appium 启动可能重启 adb，先确保目标设备在线
    ensure_adb_device_online(udid, timeout=45.0, config=config)

    apks = discover_appium_helper_apks()
    if not apks:
        raise RuntimeError(
            '未找到 Appium 辅助 APK。请先在本机执行: '
            'npm i -g appium && appium driver install uiautomator2'
        )

    required = [
        'io.appium.settings',
        'io.appium.uiautomator2.server',
        'io.appium.uiautomator2.server.test',
    ]
    missing = [pkg for pkg in required if force or not _package_installed(udid, pkg, config=config)]
    installed = []
    skipped = [pkg for pkg in required if pkg not in missing]

    if not missing:
        logger.info('Device %s already has Appium helper packages', udid)
        return {'installed': [], 'skipped': skipped, 'apks': {k: str(v) for k, v in apks.items()}}

    logger.info('Installing Appium helper APKs on %s: %s', udid, missing)
    errors = []
    for pkg in missing:
        apk = apks.get(pkg)
        if not apk or not apk.is_file():
            errors.append(f'{pkg}: 本地缺少 APK 文件')
            continue
        try:
            # Re-check online before each install (wireless can drop mid-way)
            state = _device_state(udid, config=config)
            if state != 'device':
                ensure_adb_device_online(udid, timeout=30.0, config=config)

            proc = _adb_run(
                udid, 'install', '-r', '-g', '-d', str(apk),
                timeout=120, config=config,
            )
            out = ((proc.stdout or b'') + (proc.stderr or b'')).decode('utf-8', errors='ignore')
            if proc.returncode == 0 and 'Success' in out:
                installed.append(pkg)
                logger.info('Installed %s on %s', pkg, udid)
                continue

            # Offline mid-install: recover once then retry
            if 'offline' in out.lower() or 'not found' in out.lower():
                logger.warning('Install %s hit offline; recovering adb…', pkg)
                ensure_adb_device_online(udid, timeout=30.0, config=config)
                proc = _adb_run(
                    udid, 'install', '-r', '-g', '-d', str(apk),
                    timeout=120, config=config,
                )
                out = ((proc.stdout or b'') + (proc.stderr or b'')).decode('utf-8', errors='ignore')
                if proc.returncode == 0 and 'Success' in out:
                    installed.append(pkg)
                    logger.info('Installed %s on %s after reconnect', pkg, udid)
                    continue

            # Retry without -g for some OEMs
            proc2 = _adb_run(udid, 'install', '-r', '-d', str(apk), timeout=120, config=config)
            out2 = ((proc2.stdout or b'') + (proc2.stderr or b'')).decode('utf-8', errors='ignore')
            if proc2.returncode == 0 and 'Success' in out2:
                installed.append(pkg)
                logger.info('Installed %s on %s (retry without -g)', pkg, udid)
                continue
            err = (out2 or out or '').strip()[:400]
            errors.append(f'{pkg}: {err or f"install exit {proc.returncode}"}')
        except Exception as exc:
            errors.append(f'{pkg}: {exc}')

    still_missing = [pkg for pkg in required if not _package_installed(udid, pkg, config=config)]
    if still_missing:
        detail = '；'.join(errors) if errors else '未知原因'
        lower = detail.lower()
        hint = ''
        if 'offline' in lower or 'not found' in lower:
            online = [f'{s}({st})' for s, st in _list_adb_devices(config=config)]
            hint = (
                f' 设备 adb 离线。当前在线: {", ".join(online) or "无"}。'
                '请改用 USB 设备，或重新连接无线调试后再试。'
            )
        elif 'user_restricted' in lower or 'canceled by user' in lower or 'install_failed' in lower:
            hint = (
                ' 请在手机开发者选项中开启「USB 安装 / USB 调试（安全设置）」，'
                '并在弹窗中点允许；小米/红米需登录小米账号后开启「USB安装」。'
            )
        raise RuntimeError(
            f'设备缺少 Appium 组件且自动安装失败（{ ", ".join(still_missing) }）：{detail}。{hint}'
        )

    return {
        'installed': installed,
        'skipped': skipped,
        'apks': {k: str(v) for k, v in apks.items()},
    }


def _parse_host_port(server_url: str) -> Tuple[str, int]:
    parsed = urlparse(server_url if '://' in server_url else f'http://{server_url}')
    host = parsed.hostname or '127.0.0.1'
    port = parsed.port or 4723
    return host, port


def _status_url(server_url: str) -> str:
    base = (server_url or 'http://127.0.0.1:4723').rstrip('/')
    # Appium 1 used /wd/hub/status; Appium 2 uses /status
    return f'{base}/status'


def is_appium_ready(server_url: str, timeout: float = 2.0) -> bool:
    url = _status_url(server_url)
    try:
        with urlopen(url, timeout=timeout) as resp:
            return 200 <= getattr(resp, 'status', 200) < 300
    except Exception:
        # Try Appium 1 legacy path
        legacy = f'{(server_url or "").rstrip("/")}/wd/hub/status'
        try:
            with urlopen(legacy, timeout=timeout) as resp:
                return 200 <= getattr(resp, 'status', 200) < 300
        except Exception:
            return False


def _log_dir() -> Path:
    base = Path(settings.MEDIA_ROOT) / 'app-automation' / 'logs'
    base.mkdir(parents=True, exist_ok=True)
    return base


def _build_start_command(command: str, host: str, port: int) -> str:
    cmd = (command or 'appium').strip()
    # Keep as shell string so Windows can resolve appium.cmd / npx.cmd via PATH
    return f'{cmd} --address {host} --port {port} --session-override'


def _stop_managed_process():
    global _PROCESS, _STARTED_BY_US
    if _PROCESS is None:
        return
    try:
        if _PROCESS.poll() is None:
            _PROCESS.terminate()
            try:
                _PROCESS.wait(timeout=5)
            except Exception:
                _PROCESS.kill()
    except Exception:
        pass
    _PROCESS = None
    _STARTED_BY_US = False


def _start_process(command: str, host: str, port: int, config=None) -> subprocess.Popen:
    global _PROCESS, _STARTED_BY_US
    log_path = _log_dir() / 'appium-server.log'
    full_cmd = _build_start_command(command, host, port)
    env = _appium_env(config)
    if not env.get('ANDROID_HOME'):
        raise RuntimeError(
            '未检测到 Android SDK（ANDROID_HOME）。请在 APP 自动化配置中填写 '
            '「Android SDK 路径」（需包含 platform-tools），或设置系统环境变量 ANDROID_HOME。'
            '若只有 platform-tools，可填其父目录，例如 E:\\platform-tools-latest-windows'
        )
    logger.info('Starting Appium Server: %s (log=%s)', full_cmd, log_path)
    log_file = open(log_path, 'a', encoding='utf-8', errors='ignore')
    log_file.write(
        f'\n===== start {time.strftime("%Y-%m-%d %H:%M:%S")} =====\n'
        f'{full_cmd}\nANDROID_HOME={env.get("ANDROID_HOME")}\n'
    )
    log_file.flush()
    creationflags = 0
    if os.name == 'nt':
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    try:
        proc = subprocess.Popen(
            full_cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            shell=True,
            cwd=str(settings.BASE_DIR),
            env=env,
            creationflags=creationflags,
        )
    except FileNotFoundError as exc:
        log_file.close()
        raise RuntimeError(
            '无法启动 Appium：找不到命令。请先安装 Node.js 与 Appium '
            '（npm i -g appium && appium driver install uiautomator2），'
            f'并确认启动命令可用。原始错误: {exc}'
        ) from exc
    _PROCESS = proc
    _STARTED_BY_US = True
    return proc


def _candidate_commands(preferred: str) -> list:
    cmds = []
    preferred = (preferred or 'appium').strip() or 'appium'
    cmds.append(preferred)
    # Fallback when global appium is missing but Node/npx exists
    if preferred != 'npx --yes appium' and 'npx' not in preferred.split()[0]:
        cmds.append('npx --yes appium')
    # Deduplicate while preserving order
    seen = set()
    out = []
    for c in cmds:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def ensure_appium_running(timeout: float = 60.0, *, restart_if_no_sdk_env: bool = True) -> str:
    """
    Ensure Appium Server is reachable. Auto-start if configured.
    Returns the server URL to use for WebDriver sessions.
    """
    global _PROCESS

    config = get_appium_config()
    server_url = (config.appium_server_url or 'http://127.0.0.1:4723').rstrip('/')
    sdk = resolve_android_sdk_root(config)
    if sdk:
        os.environ.setdefault('ANDROID_HOME', sdk)
        os.environ.setdefault('ANDROID_SDK_ROOT', sdk)

    if is_appium_ready(server_url):
        # If we started a previous server without ANDROID_HOME, restart it
        if restart_if_no_sdk_env and _STARTED_BY_US and sdk and not os.environ.get('_TESTHUB_APPIUM_SDK_OK'):
            # Prefer restart only when current managed process exists; external servers left alone
            pass
        return server_url

    if not getattr(config, 'appium_auto_start', True):
        raise RuntimeError(
            f'Appium Server 未运行（{server_url}），且未开启自动拉起。'
            '请手动执行 appium，或在 APP 自动化配置中开启「自动拉起 Appium」。'
        )

    with _LOCK:
        if is_appium_ready(server_url):
            return server_url

        # Reuse existing process if still alive but not ready yet
        if _PROCESS is not None and _PROCESS.poll() is None:
            deadline = time.time() + min(timeout, 30)
            while time.time() < deadline:
                if is_appium_ready(server_url):
                    return server_url
                time.sleep(0.5)

        host, port = _parse_host_port(server_url)
        bind_host = host if host not in ('127.0.0.1', 'localhost') else '127.0.0.1'
        last_error = None
        for cmd in _candidate_commands(config.appium_command or 'appium'):
            try:
                _stop_managed_process()
                _start_process(cmd, bind_host, port, config=config)
            except RuntimeError as exc:
                last_error = exc
                continue
            except Exception as exc:
                last_error = RuntimeError(
                    f'启动 Appium 失败: {exc}。请确认已安装 Appium '
                    '（npm i -g appium && appium driver install uiautomator2）。'
                )
                continue

            per_try_timeout = max(25.0, timeout / 2)
            deadline = time.time() + per_try_timeout
            while time.time() < deadline:
                if _PROCESS is not None and _PROCESS.poll() is not None:
                    code = _PROCESS.returncode
                    last_error = RuntimeError(
                        f'Appium 进程异常退出（code={code}，命令={cmd}）。'
                        '请查看 media/app-automation/logs/appium-server.log；'
                        '常见原因：未安装 Appium、端口被占用、缺少 uiautomator2 driver、'
                        'ANDROID_HOME 未配置。'
                    )
                    break
                if is_appium_ready(server_url):
                    logger.info('Appium Server ready at %s (cmd=%s)', server_url, cmd)
                    return server_url
                time.sleep(0.5)
            else:
                last_error = RuntimeError(
                    f'等待 Appium 就绪超时（命令={cmd}，地址 {server_url}）。'
                    '请确认 PATH 中有 appium，或改用 npx --yes appium。'
                    '日志: media/app-automation/logs/appium-server.log'
                )
                _stop_managed_process()

        if last_error:
            raise last_error
        raise RuntimeError(
            f'等待 Appium 就绪超时（{timeout:.0f}s，地址 {server_url}）。'
            '请确认已安装: npm i -g appium && appium driver install uiautomator2。'
            '日志: media/app-automation/logs/appium-server.log'
        )


def create_android_driver(udid: str, server_url: Optional[str] = None, steal_focus: bool = True):
    """Create UiAutomator2 session attached to current device foreground (no app launch).

    steal_focus=False：录制中文输入等场景禁止按 HOME / 拉起 Settings，避免前台 App「闪退」。
    """
    try:
        from appium import webdriver
        from appium.options.android import UiAutomator2Options
    except ImportError as exc:
        raise RuntimeError(
            '未安装 Appium-Python-Client，请执行: pip install "Appium-Python-Client>=3.1.0,<5"'
        ) from exc

    config = get_appium_config()
    sdk = resolve_android_sdk_root(config)
    if sdk:
        os.environ['ANDROID_HOME'] = sdk
        os.environ['ANDROID_SDK_ROOT'] = sdk

    url = (server_url or ensure_appium_running()).rstrip('/')

    # Ensure device still online after Appium server start (adb may restart)
    ensure_adb_device_online(udid, timeout=45.0, config=config)

    # Pre-install Appium helper APKs on device if missing
    try:
        result = ensure_device_appium_apks(udid)
        if result.get('installed'):
            logger.info('Pre-installed on %s: %s', udid, result['installed'])
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning('ensure_device_appium_apks failed: %s', exc)
        # Continue — Appium session create may still try install

    ensure_adb_device_online(udid, timeout=30.0, config=config)

    # Critical on Xiaomi: keep Settings alive before Appium's hard 5s check
    # 录制场景禁止抢焦点，否则用户会看到「页面闪退」
    if steal_focus:
        try:
            prepare_appium_settings_on_device(udid, config=config)
        except Exception as exc:
            logger.warning('prepare_appium_settings_on_device: %s', exc)
    else:
        logger.info('create_android_driver steal_focus=False, skip Settings prepare for %s', udid)

    options = UiAutomator2Options()
    options.platform_name = 'Android'
    options.automation_name = 'UiAutomator2'
    options.udid = udid
    options.no_reset = True
    options.new_command_timeout = 600
    # We already tried to install helpers; still allow Appium to repair if needed
    options.set_capability('appium:skipServerInstallation', False)
    options.set_capability('appium:autoGrantPermissions', True)
    # Do not set appPackage/appActivity — attach to whatever is in foreground
    options.set_capability('appium:dontStopAppOnReset', True)
    options.set_capability('appium:uiautomator2ServerLaunchTimeout', 60000)
    options.set_capability('appium:uiautomator2ServerInstallTimeout', 60000)
    options.set_capability('appium:adbExecTimeout', 120000)
    options.set_capability('appium:disableWindowAnimation', True)
    options.set_capability('appium:skipLogcatCapture', True)
    if sdk:
        options.set_capability('appium:adbExecTimeout', 120000)

    logger.info('Creating Appium session udid=%s url=%s sdk=%s steal_focus=%s', udid, url, sdk or '(none)', steal_focus)
    stop_keepalive = threading.Event()
    keepalive = None
    if steal_focus:
        keepalive = threading.Thread(
            target=_settings_fgs_keepalive,
            args=(udid, stop_keepalive),
            kwargs={'config': config},
            name=f'appium-settings-keepalive-{udid}',
            daemon=True,
        )
        keepalive.start()
    try:
        driver = webdriver.Remote(url, options=options)
    except Exception as exc:
        raw = str(exc)
        # Keep message readable for API/frontend (drop huge stack traces)
        msg = raw.split('Stacktrace:')[0].strip()
        if len(msg) > 600:
            msg = msg[:600] + '…'
        hint = ''
        lower = raw.lower()
        if 'android_home' in lower or 'android_sdk_root' in lower:
            if getattr(config, 'appium_auto_start', True) and sdk:
                logger.warning('Appium missing ANDROID_HOME; restarting managed server with SDK env')
                _stop_managed_process()
                host, port = _parse_host_port(url)
                _kill_port(port)
                time.sleep(1)
                ensure_appium_running(timeout=60)
                try:
                    driver = webdriver.Remote(url, options=options)
                    return driver
                except Exception as exc2:
                    raw = str(exc2)
                    msg = raw.split('Stacktrace:')[0].strip()
                    if len(msg) > 600:
                        msg = msg[:600] + '…'
                    lower = raw.lower()
            hint = (
                ' 请在 APP 自动化配置填写 Android SDK 路径（ANDROID_HOME），'
                '例如含 platform-tools 的父目录，然后重新开始录制。'
            )
        elif 'settings app is not running' in lower or 'appium settings' in lower or 'foreground_service_location' in lower:
            hint = (
                ' 手机端 Appium Settings 闪退：请到系统设置 → 应用 → Appium Settings，'
                '开启「位置信息=始终允许」、自启动、关闭省电限制；并退出微信分屏后重试。'
            )
        elif 'install_failed_user_restricted' in lower or 'install canceled by user' in lower:
            hint = (
                ' 手机需开启「USB 安装 / USB 调试（安全设置）」并在弹窗中允许安装'
                ' Appium Settings / UiAutomator2 相关 APK（小米/红米等常见）。'
            )
        elif 'uiautomator2' in lower or 'could not find a driver' in lower:
            hint = ' 请执行: appium driver install uiautomator2'
        elif 'device' in lower and ('not found' in lower or 'offline' in lower):
            hint = ' 请检查 USB/无线 adb 设备是否在线（adb devices）'
        raise RuntimeError(f'创建 Appium 会话失败: {msg}.{hint}') from exc
    finally:
        stop_keepalive.set()
    return driver


def _kill_port(port: int):
    """Best-effort free Appium port on Windows/Unix."""
    try:
        if os.name == 'nt':
            out = subprocess.check_output(
                f'netstat -ano | findstr :{port}',
                shell=True, text=True, errors='ignore',
            )
            pids = set()
            for line in out.splitlines():
                parts = line.split()
                if parts and parts[-1].isdigit():
                    pids.add(parts[-1])
            for pid in pids:
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
        else:
            subprocess.run(f'fuser -k {port}/tcp', shell=True, capture_output=True)
    except Exception as exc:
        logger.debug('kill port %s failed: %s', port, exc)
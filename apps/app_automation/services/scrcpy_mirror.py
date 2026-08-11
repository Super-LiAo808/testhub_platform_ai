"""Scrcpy-based realtime screen mirror for APP recording.

Uses scrcpy-server with raw_stream=true to expose Annex-B H.264 over an adb
forwarded TCP port, then relays chunks to the recording WebSocket group.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEVICE_SERVER_PATH = '/data/local/tmp/testhub-scrcpy-server.jar'


def _env(name: str, default: str = '') -> str:
    return (os.environ.get(name) or default).strip()


def _get_config_value(attr: str, default: str = '') -> str:
    try:
        from apps.app_automation.models import AppTestConfig
        cfg = AppTestConfig.objects.first()
        if cfg and getattr(cfg, attr, None):
            return str(getattr(cfg, attr) or '').strip()
    except Exception:
        pass
    return default


def resolve_adb_path() -> str:
    try:
        from apps.app_automation.views.device_views import get_adb_path
        p = get_adb_path()
        if p:
            return p
    except Exception:
        pass
    return _get_config_value('adb_path', 'adb') or 'adb'


def _bundled_scrcpy_dirs() -> List[Path]:
    """Project-bundled scrcpy locations (tools/scrcpy)."""
    dirs: List[Path] = []
    try:
        from django.conf import settings
        base = Path(settings.BASE_DIR)
    except Exception:
        base = Path(__file__).resolve().parents[3]
    candidates = [
        base / 'tools' / 'scrcpy',
        base / 'tools' / 'scrcpy' / 'scrcpy-win64-v2.7',
        base / 'tools' / 'scrcpy' / 'scrcpy-win64-v3.1',
        base / 'tools' / 'scrcpy' / 'scrcpy-win64-v4.1',
    ]
    for d in candidates:
        if d.is_dir():
            dirs.append(d)
    return dirs


def resolve_scrcpy_bin() -> Optional[str]:
    configured = _env('SCRCPY_PATH') or _get_config_value('scrcpy_path')
    if configured:
        p = Path(configured)
        if p.is_file():
            return str(p)
        for name in ('scrcpy.exe', 'scrcpy'):
            cand = p / name
            if cand.is_file():
                return str(cand)
    found = shutil.which('scrcpy') or shutil.which('scrcpy.exe')
    if found:
        return found
    for d in _bundled_scrcpy_dirs():
        for name in ('scrcpy.exe', 'scrcpy'):
            cand = d / name
            if cand.is_file():
                return str(cand)
    return None


def resolve_scrcpy_server_jar(scrcpy_bin: Optional[str] = None) -> Optional[Path]:
    configured = _env('SCRCPY_SERVER_PATH') or _get_config_value('scrcpy_server_path')
    if configured:
        p = Path(configured)
        if p.is_file():
            return p
    bin_path = scrcpy_bin or resolve_scrcpy_bin()
    search_dirs: List[Path] = []
    if bin_path:
        search_dirs.append(Path(bin_path).resolve().parent)
    search_dirs.extend(_bundled_scrcpy_dirs())
    # Common Windows portable layouts
    for extra in (
        Path(os.environ.get('LOCALAPPDATA', '')) / 'scrcpy',
        Path('C:/scrcpy'),
        Path('C:/Program Files/scrcpy'),
        Path(os.environ.get('USERPROFILE', '')) / 'scrcpy',
    ):
        if extra and str(extra) not in ('.', '') and extra.exists():
            search_dirs.append(extra)
    names = (
        'scrcpy-server',
        'scrcpy-server.jar',
        'scrcpy-server-manual.jar',
    )
    seen = set()
    for d in search_dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key in seen:
            continue
        seen.add(key)
        for name in names:
            cand = d / name
            if cand.is_file():
                return cand
        for cand in d.glob('scrcpy-server*'):
            if cand.is_file() and cand.suffix.lower() not in ('.zip', '.bat', '.vbs'):
                return cand
    return None


def detect_scrcpy_version(scrcpy_bin: Optional[str], server_jar: Optional[Path]) -> str:
    """Return server protocol version string expected by scrcpy-server jar."""
    # 1) VERSION file next to jar / bundled dir
    for base in (
        server_jar.parent if server_jar else None,
        *(_bundled_scrcpy_dirs()),
    ):
        if not base:
            continue
        vf = Path(base) / 'VERSION'
        if vf.is_file():
            try:
                text = vf.read_text(encoding='utf-8', errors='ignore').strip()
                m = re.search(r'(\d+\.\d+(?:\.\d+)?)', text)
                if m:
                    return m.group(1)
            except Exception:
                pass
    # 2) version in path / filename
    for p in (server_jar, Path(scrcpy_bin) if scrcpy_bin else None):
        if not p:
            continue
        m = re.search(r'(\d+\.\d+(?:\.\d+)?)', str(p))
        if m:
            return m.group(1)
    # 3) scrcpy --version (may be empty when stdout is piped on Windows)
    if scrcpy_bin:
        try:
            proc = subprocess.run(
                [scrcpy_bin, '--version'],
                capture_output=True,
                timeout=8,
                text=True,
                encoding='utf-8',
                errors='ignore',
            )
            out = (proc.stdout or '') + (proc.stderr or '')
            m = re.search(r'scrcpy\s+(\d+\.\d+(?:\.\d+)?)', out, re.I)
            if m:
                return m.group(1)
        except Exception as exc:
            logger.debug('scrcpy --version failed: %s', exc)
    return '2.7'


def get_scrcpy_stream_options() -> Dict[str, Any]:
    # 默认略降码率，减轻 USB 带宽压力（小米机常见因总线过载掉线）
    max_size_raw = _env('SCRCPY_MAX_SIZE') or _get_config_value('scrcpy_max_size') or '1280'
    bit_rate = _env('SCRCPY_BIT_RATE') or _get_config_value('scrcpy_bit_rate') or '2000000'
    try:
        max_size = int(max_size_raw)
    except ValueError:
        max_size = 1280
    try:
        br = str(bit_rate).strip().upper()
        if br.endswith('M'):
            bit_rate = str(int(float(br[:-1]) * 1_000_000))
        elif br.endswith('K'):
            bit_rate = str(int(float(br[:-1]) * 1_000))
        else:
            bit_rate = str(int(br))
    except Exception:
        bit_rate = '2000000'
    return {'max_size': max_size, 'bit_rate': bit_rate}


def _adb(adb: str, device_id: str, *args, timeout: float = 30) -> subprocess.CompletedProcess:
    cmd = [adb, '-s', device_id, *args]
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return int(s.getsockname()[1])


@dataclass
class ScrcpyMirrorSession:
    device_id: str
    session_id: int
    on_chunk: Callable[[bytes], None]
    on_status: Optional[Callable[[str], None]] = None
    adb: str = field(default_factory=resolve_adb_path)
    local_port: int = 0
    abstract_name: str = ''
    server_proc: Optional[subprocess.Popen] = None
    sock: Optional[socket.socket] = None
    reader_thread: Optional[threading.Thread] = None
    stop_flag: threading.Event = field(default_factory=threading.Event)
    started: bool = False
    error: str = ''

    def start(self, timeout: float = 20.0) -> bool:
        import random

        scrcpy_bin = resolve_scrcpy_bin()
        server_jar = resolve_scrcpy_server_jar(scrcpy_bin)
        if not server_jar:
            self.error = (
                '未找到 scrcpy-server。请将 scrcpy 放到 tools/scrcpy/，'
                '或设置 SCRCPY_PATH / SCRCPY_SERVER_PATH。'
            )
            logger.warning(self.error)
            return False

        version = detect_scrcpy_version(scrcpy_bin, server_jar)
        opts = get_scrcpy_stream_options()
        self.local_port = _pick_free_port()
        scid = random.randint(1, 0xFFFFFF)
        self.abstract_name = f'scrcpy_{scid:08x}'

        try:
            if self.on_status:
                self.on_status('正在推送 scrcpy-server…')
            push = _adb(
                self.adb, self.device_id,
                'push', str(server_jar), _DEVICE_SERVER_PATH,
                timeout=60,
            )
            if push.returncode != 0:
                err = (push.stderr or b'')[:300]
                self.error = f'scrcpy-server 推送失败: {err!r}'
                return False

            try:
                # 仅清理本平台推送的 server（同设备多会话仍会互斥，但避免误杀其它 scrcpy 客户端）
                _adb(
                    self.adb, self.device_id, 'shell', 'pkill', '-f',
                    'testhub-scrcpy-server.jar',
                    timeout=5,
                )
            except Exception:
                pass
            time.sleep(0.3)

            try:
                _adb(self.adb, self.device_id, 'forward', '--remove', f'tcp:{self.local_port}', timeout=5)
            except Exception:
                pass
            fwd = _adb(
                self.adb, self.device_id,
                'forward', f'tcp:{self.local_port}', f'localabstract:{self.abstract_name}',
                timeout=10,
            )
            if fwd.returncode != 0:
                err = (fwd.stderr or b'')[:300]
                self.error = f'adb forward 失败: {err!r}'
                return False

            if self.on_status:
                self.on_status('正在启动 scrcpy-server…')

            creationflags = 0
            if os.name == 'nt':
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

            # scrcpy 2.x：tunnel_forward=true + adb forward → server 在 abstract 上 listen，主机连接
            # 必须带 scid，socket 名为 scrcpy_<scid>
            version_candidates: List[str] = []
            for v in (version, '2.7', '2.4', '3.1', '2.3'):
                if v and v not in version_candidates:
                    version_candidates.append(v)

            last_err = ''
            connected = False
            used_version = version
            for ver in version_candidates:
                if self.stop_flag.is_set():
                    break
                if self.server_proc and self.server_proc.poll() is None:
                    try:
                        self.server_proc.terminate()
                        self.server_proc.wait(timeout=2)
                    except Exception:
                        try:
                            self.server_proc.kill()
                        except Exception:
                            pass
                self.server_proc = None

                shell_cmd = (
                    f'CLASSPATH={_DEVICE_SERVER_PATH} app_process / '
                    f'com.genymobile.scrcpy.Server {ver} '
                    f'scid={scid:08x} tunnel_forward=true audio=false control=false cleanup=true '
                    f'video=true raw_stream=true '
                    f'max_size={opts["max_size"]} video_bit_rate={opts["bit_rate"]}'
                )
                self.server_proc = subprocess.Popen(
                    [self.adb, '-s', self.device_id, 'shell', shell_cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                )

                # 读 server 日志直到 Device: 或超时
                ready_flag = threading.Event()
                server_log = []

                def _drain_stdout():
                    try:
                        assert self.server_proc and self.server_proc.stdout
                        while not self.stop_flag.is_set():
                            line = self.server_proc.stdout.readline()
                            if not line:
                                break
                            server_log.append(line)
                            if b'Device:' in line:
                                ready_flag.set()
                            if b'ERROR' in line:
                                ready_flag.set()
                    except Exception:
                        ready_flag.set()

                threading.Thread(target=_drain_stdout, name='scrcpy-log', daemon=True).start()
                ready_flag.wait(timeout=min(6.0, timeout))
                time.sleep(0.25)

                attempt_deadline = time.time() + min(8.0, timeout)
                while time.time() < attempt_deadline and not self.stop_flag.is_set():
                    if self.server_proc.poll() is not None:
                        last_err = f'ver={ver} exited: {b"".join(server_log)[:300]!r}'
                        break
                    try:
                        sock = socket.create_connection(('127.0.0.1', self.local_port), timeout=1.0)
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        sock.settimeout(2.5)
                        first = b''
                        try:
                            while len(first) < 32:
                                c = sock.recv(65536)
                                if not c:
                                    break
                                first += c
                        except socket.timeout:
                            pass
                        if not first:
                            sock.close()
                            last_err = f'ver={ver} connected but no video data'
                            time.sleep(0.25)
                            continue
                        sock.settimeout(None)
                        self.sock = sock
                        self._pending_first = first
                        used_version = ver
                        connected = True
                        break
                    except OSError as exc:
                        last_err = str(exc)
                        time.sleep(0.2)
                if connected:
                    break

            if not connected:
                self.error = f'连接 scrcpy 视频流失败: {last_err}'
                self._cleanup_partial()
                return False

            self.started = True
            self.reader_thread = threading.Thread(
                target=self._read_loop,
                name=f'scrcpy-read-{self.session_id}',
                daemon=True,
            )
            self.reader_thread.start()
            logger.info(
                'scrcpy mirror started session=%s device=%s port=%s scid=%s version=%s jar=%s',
                self.session_id, self.device_id, self.local_port, f'{scid:08x}', used_version, server_jar,
            )
            return True
        except Exception as exc:
            logger.exception('scrcpy start failed')
            self.error = str(exc)
            self._cleanup_partial()
            return False

    def _read_loop(self):
        assert self.sock is not None
        buf = getattr(self, '_pending_first', b'') or b''
        self._pending_first = b''
        try:
            if buf:
                try:
                    self.on_chunk(buf)
                except Exception as exc:
                    logger.debug('on_chunk failed: %s', exc)
                buf = b''
            while not self.stop_flag.is_set():
                try:
                    chunk = self.sock.recv(65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                if len(buf) >= 8192:
                    to_send = buf
                    buf = b''
                    try:
                        self.on_chunk(to_send)
                    except Exception as exc:
                        logger.debug('on_chunk failed: %s', exc)
            if buf:
                try:
                    self.on_chunk(buf)
                except Exception:
                    pass
        finally:
            logger.info('scrcpy read loop ended session=%s', self.session_id)

    def _cleanup_partial(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        if self.server_proc and self.server_proc.poll() is None:
            try:
                self.server_proc.terminate()
            except Exception:
                pass
            try:
                self.server_proc.wait(timeout=3)
            except Exception:
                try:
                    self.server_proc.kill()
                except Exception:
                    pass
        self.server_proc = None
        if self.local_port:
            try:
                _adb(self.adb, self.device_id, 'forward', '--remove', f'tcp:{self.local_port}', timeout=5)
            except Exception:
                pass

    def is_alive(self) -> bool:
        if not self.started or self.stop_flag.is_set():
            return False
        if self.reader_thread and not self.reader_thread.is_alive():
            return False
        if self.server_proc is not None and self.server_proc.poll() is not None:
            return False
        return True

    def stop(self):
        self.stop_flag.set()
        self._cleanup_partial()
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=3)
        self.started = False


def probe_scrcpy_available() -> Tuple[bool, str]:
    jar = resolve_scrcpy_server_jar()
    if not jar:
        return False, '未找到 scrcpy-server（请安装 scrcpy 或配置 SCRCPY_SERVER_PATH）'
    return True, str(jar)

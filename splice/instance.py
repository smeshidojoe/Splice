"""Один процесс на все выделенные файлы.

Проводник на статическом пункте меню запускает программу отдельно на каждый
выделенный файл. Первый процесс поднимает QLocalServer и копит файлы ~0.6 с;
остальные отдают ему свои файлы и выходят. Так «Merge with Splice» на десяти
файлах открывает одно окно с десятью строками, а не десять окон.

Тот же процесс держит именованный мьютекс — по нему установщик понимает, что
программу надо закрыть перед заменой exe (AppMutex в splice_setup.iss).
"""

from __future__ import annotations

import ctypes
import json
import os
import re

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .constants import INSTANCE_NAME

_MUTEX = None
GATHER_MS = 600


def natural_key(path: str):
    """clip2 раньше clip10."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", os.path.basename(path))]


def _hold_mutex() -> None:
    global _MUTEX
    try:
        _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, INSTANCE_NAME + "-Mutex")
    except Exception:
        pass


def _send(mode: str, files: list[str]) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write((json.dumps({"mode": mode, "files": files}) + "\n").encode("utf-8"))
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


class Gatherer(QObject):
    """ready(mode, files) — пачка файлов одного режима собрана."""

    ready = Signal(str, list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_conn)
        self.pending: dict[str, list[str]] = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(GATHER_MS)
        self.timer.timeout.connect(self._dispatch)

    def start(self, mode: str, files: list[str]) -> bool:
        """True — мы главный процесс; False — файлы отданы уже запущенному."""
        for _ in range(10):
            if _send(mode, files):
                return False
            if self.server.listen(INSTANCE_NAME):
                break
            QLocalServer.removeServer(INSTANCE_NAME)   # хвост упавшего процесса
            QThread.msleep(80)
        _hold_mutex()
        self.add(mode, files)
        return True

    def add(self, mode: str, files: list[str]) -> None:
        self.pending.setdefault(mode, []).extend(files)
        self.timer.start()

    def _on_conn(self) -> None:
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            buf = bytearray()

            def read(s=sock, b=buf):
                b.extend(bytes(s.readAll()))
                while b"\n" in b:
                    line, _, rest = bytes(b).partition(b"\n")
                    b[:] = rest
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self.add(msg["mode"], list(msg["files"]))
                    except (ValueError, KeyError, TypeError):
                        pass

            sock.readyRead.connect(read)
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                read()

    def _dispatch(self) -> None:
        pending, self.pending = self.pending, {}
        for mode, files in pending.items():
            unique = sorted({os.path.normcase(f): f for f in files}.values(), key=natural_key)
            self.ready.emit(mode, unique)

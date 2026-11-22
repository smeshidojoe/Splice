"""Приложение: трей, окна, FFmpeg, обновления.

Программа живёт в трее, как Clipr и Spotty: пункт меню проводника отдаёт
файлы уже запущенному процессу, и окно открывается сразу. Ручной запуск exe
без файлов открывает настройки, запуск с --tray (автозапуск) — молча.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMenu, QMessageBox, QProgressDialog, QSystemTrayIcon,
)

from . import i18n, tools
from .config import Config
from .constants import APP_NAME
from .i18n import tr
from .instance import Gatherer
from .updates import UpdateService


class SpliceApp:
    def __init__(self, argv, mode: str, files: list[str], quiet: bool = False) -> None:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        self.qt = QApplication(argv)
        self.qt.setApplicationName(APP_NAME)
        self.qt.setQuitOnLastWindowClosed(False)
        self.config = Config()
        i18n.set_language(self.config.language())
        from .ui import icons
        self.qt.setWindowIcon(icons.app_icon())
        self.windows = []
        self.updates = UpdateService()
        self.updates.state.connect(self._on_update_state)
        self._manual_check = None
        self.mode, self.files = mode, files
        self._quiet = quiet and not files      # автозапуск: только значок в трее
        self.settings = None
        self.gatherer = Gatherer()
        self.gatherer.ready.connect(self._open)

    def run(self) -> int:
        if not self.gatherer.start(self.mode, self.files):
            return 0                         # файлы отданы уже открытому окну
        self._build_tray()
        if self.config.update_due() and self.updates.supported():
            QTimer.singleShot(1500, self._auto_check)
        return self.qt.exec()

    # --- окна --------------------------------------------------------------- #
    def _open(self, mode: str, files: list[str]) -> None:
        if not files:
            if self._quiet:
                self._quiet = False
            else:
                self.open_settings()
            return
        if not self._ensure_ffmpeg():
            return
        if mode == "merge":
            self.open_merge(files)
        else:
            self.open_chopper(files)

    def _show(self, w) -> None:
        self.windows.append(w)
        w.destroyed.connect(lambda *_: self.windows.remove(w) if w in self.windows else None)
        w.show()
        w.raise_()
        w.activateWindow()

    def open_chopper(self, files: list[str]) -> None:
        from .ui.chopper import ChopperWindow
        self._show(ChopperWindow(self, files))

    def open_merge(self, files: list[str]) -> None:
        from .ui.merge import MergeWindow
        self._show(MergeWindow(self, files))

    def open_settings(self, pos=None) -> None:
        if self.settings is None:
            from .ui.settings import SettingsWindow
            self.settings = SettingsWindow(self)
            self.settings.destroyed.connect(lambda *_: setattr(self, "settings", None))
            if pos is not None:
                self.settings.move(pos)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def _pick(self, mode: str) -> None:
        """Из трея: явный выбор файлов — единственное место с диалогом."""
        from .instance import natural_key
        from .ui.merge import video_filter
        import os
        title = tr("tray.merge" if mode == "merge" else "tray.chop").rstrip("…")
        fs, _ = QFileDialog.getOpenFileNames(None, title, "", video_filter())
        if fs:
            self._open(mode, sorted((os.path.normpath(f) for f in fs), key=natural_key))

    # --- трей --------------------------------------------------------------- #
    def _build_tray(self) -> None:
        from .ui import icons
        from .ui.widgets import rounded_menu
        self.tray = QSystemTrayIcon(icons.app_icon())
        self.tray.setToolTip(APP_NAME)
        self.menu = QMenu()
        rounded_menu(self.menu)
        self.a_chop = QAction(self.menu)
        self.a_chop.triggered.connect(lambda: self._pick("chop"))
        self.a_merge = QAction(self.menu)
        self.a_merge.triggered.connect(lambda: self._pick("merge"))
        self.a_settings = QAction(self.menu)
        self.a_settings.triggered.connect(self.open_settings)
        self.a_update = QAction(self.menu)
        self.a_update.triggered.connect(self._update_from_tray)
        self.a_quit = QAction(self.menu)
        self.a_quit.triggered.connect(self.quit)
        for a in (self.a_chop, self.a_merge, None, self.a_settings, self.a_update, None,
                  self.a_quit):
            self.menu.addSeparator() if a is None else self.menu.addAction(a)
        self.retranslate()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(
            lambda r: r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick)
            and self.open_settings())
        self.tray.show()

    def retranslate(self) -> None:
        self.a_chop.setText(tr("tray.chop"))
        self.a_merge.setText(tr("tray.merge"))
        self.a_settings.setText(tr("tray.settings"))
        ready = self.updates.ready_version()
        self.a_update.setText(tr("tray.restart", version=ready) if ready else tr("tray.update"))
        self.a_quit.setText(tr("tray.quit"))

    def _update_from_tray(self) -> None:
        if self.updates.ready_version():
            self.restart_to_update(None)
        else:
            self.check_updates(None)

    def quit(self) -> None:
        if self.busy() and QMessageBox.question(
                None, APP_NAME, tr("chop.busy_close")) != QMessageBox.Yes:
            return
        for w in list(self.windows):
            w.close()
        if self.settings:
            self.settings.close()
        self.tray.hide()
        self.qt.quit()

    def busy(self) -> bool:
        return any(getattr(w, "_busy", lambda: False)() for w in self.windows)

    # --- FFmpeg ------------------------------------------------------------- #
    def _ensure_ffmpeg(self) -> bool:
        if tools.have_ffmpeg() and tools.ffprobe_path():
            return True
        if QMessageBox.question(None, tr("ffmpeg.missing_title"), tr("ffmpeg.missing_text")) \
                != QMessageBox.Yes:
            return False
        import threading
        dialog = QProgressDialog(tr("ffmpeg.downloading", percent=0), tr("chop.cancel"), 0, 100)
        dialog.setWindowTitle(APP_NAME)
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.show()
        state = {"f": 0.0, "done": False, "error": ""}

        def work():
            try:
                tools.download_ffmpeg(lambda f: state.__setitem__("f", f))
            except Exception as e:          # noqa: BLE001
                state["error"] = str(e)
            state["done"] = True

        threading.Thread(target=work, daemon=True).start()
        while not state["done"]:
            pct = int(state["f"] * 100)
            dialog.setValue(pct)
            dialog.setLabelText(tr("ffmpeg.downloading", percent=pct))
            self.qt.processEvents()
            time.sleep(0.05)
        dialog.close()
        if state["error"]:
            QMessageBox.critical(None, APP_NAME, tr("ffmpeg.failed", error=state["error"]))
            return False
        return True

    # --- обновления ---------------------------------------------------------- #
    def _auto_check(self) -> None:
        self.config["last_update_check"] = time.time()
        self.updates.check(silent=True)

    def check_updates(self, parent) -> None:
        self._manual_check = parent if parent is not None else self.tray
        self.config["last_update_check"] = time.time()
        self.updates.check(silent=False)

    def _on_update_state(self, state: str, version: str) -> None:
        parent, self._manual_check = self._manual_check, (
            self._manual_check if state == "checking" else None)
        if state == "ready" and hasattr(self, "a_update"):
            self.retranslate()
        if parent is None:
            return
        if parent is getattr(self, "tray", None):
            parent = None
            if state == "available" and self.updates.supported():
                self.updates.download()
                return
        texts = {"current": tr("update.current", version=version),
                 "error": tr("update.error")}
        if state in texts:
            QMessageBox.information(parent, APP_NAME, texts[state])

    def restart_to_update(self, parent) -> None:
        if self.busy():
            QMessageBox.information(parent, APP_NAME, tr("update.busy"))
            return
        if self.updates.start_helper():
            self.updates.exit_now()
        QMessageBox.warning(parent, APP_NAME, tr("update.install_failed"))

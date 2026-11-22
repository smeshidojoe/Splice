"""Общее для обоих окон: тёмный заголовок, полоса обновления, меню «ещё»."""

from __future__ import annotations

import ctypes
import os
import subprocess

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QMenu, QMessageBox, QWidget

from .. import crashlog, i18n
from ..constants import APP_NAME, APP_VERSION, DEVELOPER_URL, RELEASES_URL
from ..i18n import tr
from . import icons, theme
from .controls import ProgressLine, label
from .widgets import PressButton, rounded_menu

EXTRA_QSS = f"""
QWidget#window {{ background: {theme.WINDOW}; }}
QFrame#side {{
    background: {theme.SURFACE};
    border: 1px solid {theme.BORDER};
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 16px;
}}
QWidget#updateBar {{
    background: {theme.SURFACE_RAISED};
    border: 1px solid {theme.BORDER};
    border-radius: 12px;
}}
QLabel#fileName {{ font-size: 15px; font-weight: 600; letter-spacing: -0.2px; }}
QLabel#value {{ font-size: 13px; color: {theme.TEXT_DIM}; }}
QLabel#mark {{ font-size: 13px; font-weight: 600; color: {theme.OK};
               font-family: "Cascadia Mono", "Consolas", monospace; }}
QLabel#timecode {{ font-family: "Cascadia Mono", "Consolas", monospace; font-size: 15px; }}
QLabel#status {{ font-size: 12px; color: {theme.TEXT_DIM}; }}
QLabel#status[error="true"] {{ color: {theme.DANGER}; }}
QLabel#empty {{ font-size: 12px; color: {theme.TEXT_DIM}; }}
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{ border: none; padding: 0; margin: 0 0 4px 0; }}
QListWidget::item:selected {{ background: transparent; }}
QWidget#row {{ background: rgba(255, 255, 255, 0.04); border-radius: 10px; }}
QWidget#row[current="true"] {{ background: rgba(76, 141, 255, 0.22); }}
QLabel#rowNum {{ font-size: 12px; font-weight: 700; color: {theme.ACCENT}; }}
QLabel#rowTime {{ font-size: 12px; font-family: "Cascadia Mono", "Consolas", monospace; }}
QLabel#rowLen {{ font-size: 11px; color: {theme.TEXT_DIM}; }}
QVideoWidget {{ background: #000000; }}
QSlider::groove:horizontal {{ height: 4px; background: {theme.TRACK}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {theme.TEXT_DIM}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #FFFFFF; width: 12px; height: 12px;
                              margin: -4px 0; border-radius: 6px; }}
"""


def window_style() -> str:
    return theme.QSS + EXTRA_QSS


def dark_titlebar(widget: QWidget) -> None:
    """Тёмная системная строка заголовка (Windows 10 2004+ / 11)."""
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        for attr in (20, 19):            # DWMWA_USE_IMMERSIVE_DARK_MODE (новый и старый)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass


def show_in_folder(path: str) -> None:
    if os.name == "nt" and path:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])


def beep() -> None:
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        pass


def icon_button(name: str, tip: str = "", size: int = 18) -> PressButton:
    button = PressButton()
    button.setObjectName("icon")
    button.setIcon(icons.glyph(name, theme.TEXT, size))
    button.setIconSize(QSize(size, size))
    button.setToolTip(tip)
    button.setFocusPolicy(Qt.NoFocus)
    return button


def text_button(text: str, primary: bool = False, icon: str = "") -> PressButton:
    button = PressButton(text)
    if primary:
        button.setObjectName("primary")
    if icon:
        button.setIcon(icons.glyph(icon, "#FFFFFF" if primary else theme.TEXT, 16))
        button.setIconSize(QSize(16, 16))
    button.setFocusPolicy(Qt.NoFocus)
    return button


# --- полоса обновления --------------------------------------------------------- #

class UpdateBar(QWidget):
    """Тихая строка сверху окна: «доступна версия — скачать / перезапустить».

    Появляется только когда есть что сказать; ошибки проверки в фоне сюда не
    попадают — человек пришёл резать видео, а не читать про сеть.
    """

    def __init__(self, app, parent=None) -> None:
        super().__init__(parent)
        self.app = app
        self.setObjectName("updateBar")
        self.setAttribute(Qt.WA_StyledBackground)
        self.text = label("", "rowTitle")
        self.bar = ProgressLine()
        self.bar.setFixedWidth(120)
        self.action = text_button("", primary=True)
        self.action.clicked.connect(self._act)
        self.later = text_button(tr("update.later"))
        self.later.clicked.connect(self.hide)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 8, 8)
        lay.setSpacing(10)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.bar)
        lay.addWidget(self.later)
        lay.addWidget(self.action)
        self.hide()
        service = app.updates
        service.state.connect(self._on_state)
        service.progress.connect(self.bar.set_fraction)
        state, version = service.last_state()
        if state:
            self._on_state(state, version)

    def _on_state(self, state: str, version: str) -> None:
        self.bar.setVisible(state == "downloading")
        if state == "available":
            if not self.app.updates.supported():
                self.text.setText(tr("update.dev", version=version))
                self.action.hide()
            else:
                self.text.setText(tr("update.available", version=version))
                self.action.setText(tr("update.download"))
                self.action.show()
        elif state == "downloading":
            self.text.setText(tr("update.downloading", version=version))
            self.action.hide()
        elif state == "ready":
            self.text.setText(tr("update.ready", version=version))
            self.action.setText(tr("update.restart"))
            self.action.show()
        elif state == "failed":
            self.text.setText(tr("update.failed"))
            self.action.hide()
        else:
            return                      # checking / current / error — молчим
        self.show()

    def _act(self) -> None:
        if self.app.updates.ready_version():
            self.app.restart_to_update(self.window())
        else:
            self.app.updates.download()


# --- меню «ещё» --------------------------------------------------------------- #

def more_button(app, parent: QWidget) -> PressButton:
    button = icon_button("more", tr("more.tip"))
    menu = QMenu(parent)
    rounded_menu(menu)

    lang = menu.addMenu(tr("more.language"))
    rounded_menu(lang)
    group = QActionGroup(lang)
    for code, name in i18n.LANGUAGES.items():
        act = QAction(name, lang, checkable=True)
        act.setChecked(code == i18n.language())
        act.triggered.connect(lambda _=False, c=code: _set_language(app, parent, c))
        group.addAction(act)
        lang.addAction(act)

    menu.addSeparator()
    menu.addAction(tr("more.check"), lambda: app.check_updates(parent))
    auto = QAction(tr("more.auto"), menu, checkable=True)
    auto.setChecked(app.config["check_updates"])
    auto.toggled.connect(lambda on: app.config.__setitem__("check_updates", on))
    menu.addAction(auto)
    menu.addSeparator()
    menu.addAction(tr("more.shortcuts"), lambda: QMessageBox.information(
        parent, tr("more.shortcuts"), tr("shortcuts.text")))
    if crashlog.latest():
        menu.addAction(tr("more.crash"), lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(crashlog.CRASH_DIR)))
    menu.addAction(tr("more.about", version=APP_VERSION), lambda: _about(parent))

    button.clicked.connect(lambda: menu.exec(button.mapToGlobal(button.rect().bottomLeft())))
    return button


def _set_language(app, parent, code) -> None:
    if code == i18n.language():
        return
    app.config["language"] = code
    i18n.set_language(code)
    app.retranslate()
    QMessageBox.information(parent, APP_NAME, tr("more.restart_lang"))


def _about(parent) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(APP_NAME)
    box.setIconPixmap(icons.app_pixmap(64))
    box.setTextFormat(Qt.RichText)
    box.setText(f"<b>{APP_NAME} {APP_VERSION}</b><br>"
                f"{tr('chop.hint')}<br><br>"
                f"<a href='{RELEASES_URL}' style='color:{theme.ACCENT}'>{RELEASES_URL}</a><br>"
                f"<a href='{DEVELOPER_URL}' style='color:{theme.ACCENT}'>{DEVELOPER_URL}</a>")
    box.exec()

"""Настройки: меню проводника, автозапуск, язык, обновления. Открывается из
трея (двойной щелчок или «Настройки…») и при ручном запуске exe."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget,
)

from .. import autostart, i18n, shell
from ..constants import APP_NAME, APP_VERSION
from ..i18n import tr
from . import icons
from .common import UpdateBar, dark_titlebar, text_button, window_style
from .controls import Switch, label


def _row(title: str, note: str, control: QWidget) -> QHBoxLayout:
    text = QVBoxLayout()
    text.setSpacing(1)
    text.addWidget(label(title, "rowTitle"))
    if note:
        text.addWidget(label(note, "rowNote", wrap=True))
    row = QHBoxLayout()
    row.setSpacing(14)
    row.addLayout(text, 1)
    row.addWidget(control, 0, Qt.AlignVCenter)
    return row


class SettingsWindow(QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.setObjectName("window")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(window_style())
        self.setWindowIcon(icons.app_icon())
        self.setWindowTitle(tr("settings.title"))
        self.setFixedWidth(500)

        self.menu = Switch(shell.is_registered())
        self.menu.toggled.connect(self._menu)
        self.auto = Switch(autostart.is_enabled())
        self.auto.setEnabled(autostart.supported())
        self.auto.toggled.connect(self._autostart)
        self.updates = Switch(bool(app.config["check_updates"]))
        self.updates.toggled.connect(lambda on: app.config.__setitem__("check_updates", on))
        self.lang = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(i18n.language())))
        self.lang.currentIndexChanged.connect(self._language)
        check = text_button(tr("settings.check"))
        check.clicked.connect(lambda: app.check_updates(self))

        card = QFrame()
        card.setObjectName("side")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(16)
        cl.addLayout(_row(tr("settings.menu"), tr("settings.menu_note"), self.menu))
        cl.addLayout(_row(tr("settings.autostart"),
                          tr("settings.autostart_note") if autostart.supported()
                          else tr("settings.dev_only"), self.auto))
        cl.addLayout(_row(tr("settings.updates"), "", self.updates))
        cl.addLayout(_row(tr("settings.language"), "", self.lang))

        foot = QHBoxLayout()
        foot.addWidget(label(f"{APP_NAME} {APP_VERSION}", "status"))
        foot.addStretch()
        foot.addWidget(check)

        head = QHBoxLayout()
        logo = label("")
        logo.setPixmap(icons.app_pixmap(28))
        head.addWidget(logo)
        head.addWidget(label(APP_NAME, "fileName"))
        head.addStretch()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)
        root.addWidget(UpdateBar(app, self))
        root.addLayout(head)
        root.addWidget(card)
        root.addLayout(foot)

    def _menu(self, on: bool) -> None:
        try:
            shell.register() if on else shell.unregister()
        except OSError:
            self.menu.set_checked(not on)
            QMessageBox.warning(self, APP_NAME, tr("settings.failed"))

    def _autostart(self, on: bool) -> None:
        if not autostart.set_enabled(on):
            self.auto.set_checked(not on)
            QMessageBox.warning(self, APP_NAME, tr("settings.failed"))

    def _language(self) -> None:
        code = self.lang.currentData()
        if code == i18n.language():
            return
        self.app.config["language"] = code
        i18n.set_language(code)
        self.app.retranslate()
        # Пункты проводника — тоже на новом языке.
        if shell.is_registered():
            shell.register()
        # Окно собрано на старом языке — пересобираем.
        pos = self.pos()
        self.close()
        QTimer.singleShot(0, lambda: self.app.open_settings(pos))

    def showEvent(self, e) -> None:
        super().showEvent(e)
        QTimer.singleShot(0, lambda: dark_titlebar(self))

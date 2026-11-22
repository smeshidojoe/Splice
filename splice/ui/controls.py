"""Мелкие элементы: плавное число, переключатель, тонкая полоса прогресса
(перенесены из Clipr).

Правило движения одно на всё: анимируем только то, что иначе прыгнуло бы,
укладываемся в ~200 мс и каждую анимацию начинаем с того значения, что сейчас
на экране, — тогда её можно развернуть посреди пути.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from . import motion, theme


def label(text: str = "", name: str = "", wrap: bool = False, parent=None) -> QLabel:
    widget = QLabel(text, parent)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


class Tween(QVariantAnimation):
    """Одно число, плывущее к цели. Всегда стартует с того, что на экране,
    поэтому смена цели посреди пути разворачивает движение, а не прыгает."""

    def __init__(self, owner: QWidget, value: float = 0.0, duration: int = 180,
                 curve: QEasingCurve | None = None,
                 on_change: Callable[[], None] | None = None) -> None:
        super().__init__(owner)
        self.value = value
        self._owner = owner
        self._on_change = on_change or owner.update
        self.setDuration(duration)
        self.setEasingCurve(curve or motion.EASE_OUT)
        self.valueChanged.connect(self._step)

    def _step(self, value) -> None:
        self.value = float(value)
        self._on_change()

    def to(self, target: float, animate: bool = True) -> None:
        self.stop()
        if not animate or not self._owner.isVisible() or abs(target - self.value) < 1e-4:
            self.value = float(target)
            self._on_change()
            return
        self.setStartValue(self.value)
        self.setEndValue(float(target))
        self.start()



# --- переключатель ---------------------------------------------------------------- #

class Switch(QWidget):
    """Переключатель в духе iOS: бегунок доезжает до своей стороны и чуть
    расширяется под пальцем, пока кнопка зажата — предмет, а не картинка."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(40, 24)
        self._pos = Tween(self, 1.0 if checked else 0.0, motion.SWITCH_MS)
        self._press = Tween(self, 0.0, motion.PRESS_MS)
        self._hover = Tween(self, 0.0, motion.HOVER_MS, motion.EASE)

    def isChecked(self) -> bool:  # noqa: N802 (в тон Qt)
        return self._checked

    def set_checked(self, on: bool) -> None:
        """Выставить из настроек, не порождая toggled."""
        if on != self._checked:
            self._checked = on
            self._pos.to(1.0 if on else 0.0, not motion.reduced_motion())

    def _flip(self) -> None:
        self._checked = not self._checked
        self._pos.to(1.0 if self._checked else 0.0, not motion.reduced_motion())
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._press.to(1.0, not motion.reduced_motion())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return
        self._press.to(0.0, not motion.reduced_motion())
        if self.rect().contains(event.position().toPoint()):
            self._flip()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self._flip()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event) -> None:
        self._hover.to(1.0)

    def leaveEvent(self, event) -> None:
        self._hover.to(0.0)
        self._press.to(0.0)

    def focusInEvent(self, event) -> None:
        self.update()

    def focusOutEvent(self, event) -> None:
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        t = self._pos.value
        track = theme.mix(theme.TRACK, theme.ACCENT, t)
        if self._hover.value and self.isEnabled():
            track = theme.mix(track.name(), "#FFFFFF", 0.08 * self._hover.value)
        if not self.isEnabled():
            track.setAlphaF(0.45)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        radius = rect.height() / 2
        painter.drawRoundedRect(rect, radius, radius)
        if self.hasFocus():
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-0.5, -0.5, 0.5, 0.5), radius, radius)
            painter.setPen(Qt.NoPen)

        size = rect.height() - 4
        stretch = 5 * self._press.value
        left = rect.left() + 2
        right = rect.right() - 2 - size - stretch
        x = left + (right - left) * t
        painter.setBrush(QColor(0, 0, 0, 50))
        painter.drawRoundedRect(QRectF(x, rect.top() + 2.6, size + stretch, size),
                                size / 2, size / 2)
        painter.setBrush(QColor("#FFFFFF") if self.isEnabled() else QColor("#9A9AA4"))
        painter.drawRoundedRect(QRectF(x, rect.top() + 2, size + stretch, size),
                                size / 2, size / 2)


# --- полоса прогресса ------------------------------------------------------------ #


class ProgressLine(QWidget):
    """Тонкая полоса прогресса: значение догоняет новое линейно (как любой
    прогресс — ускорение здесь выдавало бы неправду о скорости)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._value = Tween(self, 0.0, 250, QEasingCurve(QEasingCurve.Linear))

    def set_fraction(self, fraction: float) -> None:
        self._value.to(fraction, animate=fraction >= self._value.value)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.TRACK))
        painter.drawRoundedRect(rect, radius, radius)
        if self._value.value > 0:
            painter.setBrush(QColor(theme.ACCENT))
            width = max(rect.height(), rect.width() * min(1.0, self._value.value))
            painter.drawRoundedRect(QRectF(rect.left(), rect.top(), width, rect.height()),
                                    radius, radius)

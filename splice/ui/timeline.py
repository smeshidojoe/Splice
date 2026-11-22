"""Таймлайн окна нарезки.

Что на нём есть: дорожка, добавленные фрагменты (акцентные плашки), черновой
диапазон In–Out (контур), указатель воспроизведения и тонкая линия под
курсором со временем.

Мышь:
  * нажать и вести по дорожке — перемотка, кадр обновляется сразу (1:1);
  * за край фрагмента или маркер In/Out — подвинуть его;
  * клик по фрагменту — выбрать его (и перемотать туда, где кликнули).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import motion, theme
from .controls import Tween

GRAB_PX = 7          # насколько близко к краю считается «взял край»
MIN_SEG_MS = 40      # фрагмент короче не бывает


def fmt(ms: int, short: bool = False) -> str:
    ms = max(0, int(ms))
    s, rest = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if short:
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
    return f"{h:02}:{m:02}:{s:02}.{rest:03}"


class Timeline(QWidget):
    seek = Signal(int)                 # перемотать сюда
    selected = Signal(int)             # выбран фрагмент (индекс, -1 — никакой)
    segments_changed = Signal()        # край фрагмента подвинули
    marks_changed = Signal()           # подвинули In или Out
    scrub_started = Signal()
    scrub_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.duration = 0
        self.position = 0
        self.segments: list[list[int]] = []
        self.current = -1
        self.in_ms: int | None = None
        self.out_ms: int | None = None
        self._hover_x: float | None = None
        self._drag: tuple | None = None          # ("seek",) | ("seg", i, 0/1) | ("mark", "in"/"out")
        self._flash = Tween(self, 0.0, 420, motion.EASE_OUT)
        self._flash_index = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

    # --- геометрия ---------------------------------------------------------- #
    def _track(self) -> QRectF:
        return QRectF(10, 22, self.width() - 20, 30)

    def _x(self, ms: float) -> float:
        t = self._track()
        return t.left() + t.width() * (ms / self.duration if self.duration else 0)

    def _ms(self, x: float) -> int:
        t = self._track()
        if not self.duration or t.width() <= 0:
            return 0
        f = (x - t.left()) / t.width()
        return int(round(max(0.0, min(1.0, f)) * self.duration))

    # --- снаружи ------------------------------------------------------------ #
    def set_position(self, ms: int) -> None:
        self.position = ms
        self.update()

    def flash(self, index: int) -> None:
        """Только что добавленный фрагмент вспыхивает — видно, куда он лёг."""
        self._flash_index = index
        self._flash.value = 1.0
        self._flash.to(0.0)

    def dragging(self) -> bool:
        return self._drag is not None

    # --- мышь --------------------------------------------------------------- #
    def _hit(self, x: float):
        """Что под курсором: край фрагмента, маркер или ничего."""
        best, best_d = None, GRAB_PX + 1
        for name in ("in", "out"):
            ms = self.in_ms if name == "in" else self.out_ms
            if ms is not None:
                d = abs(self._x(ms) - x)
                if d < best_d:
                    best, best_d = ("mark", name), d
        for i, (a, b) in enumerate(self.segments):
            for edge, ms in ((0, a), (1, b)):
                d = abs(self._x(ms) - x)
                # При равенстве выбранный фрагмент важнее соседа.
                if d < best_d or (d == best_d and i == self.current):
                    best, best_d = ("seg", i, edge), d
        return best

    def _segment_at(self, ms: int) -> int:
        for i, (a, b) in enumerate(self.segments):
            if a <= ms <= b:
                return i
        return -1

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.LeftButton or not self.duration:
            return
        x = e.position().x()
        hit = self._hit(x)
        if hit:
            self._drag = hit
            if hit[0] == "seg" and hit[1] != self.current:
                self.current = hit[1]
                self.selected.emit(self.current)
        else:
            self._drag = ("seek",)
            ms = self._ms(x)
            idx = self._segment_at(ms)
            if idx != self.current:
                self.current = idx
                self.selected.emit(idx)
            self.position = ms
            self.seek.emit(ms)
        self.scrub_started.emit()
        self.update()

    def mouseMoveEvent(self, e) -> None:
        x = e.position().x()
        self._hover_x = x
        if self._drag is None:
            self.setCursor(Qt.SizeHorCursor if self._hit(x) else Qt.PointingHandCursor)
            self.update()
            return
        ms = self._ms(x)
        kind = self._drag[0]
        if kind == "seek":
            self.position = ms
        elif kind == "seg":
            _, i, edge = self._drag
            a, b = self.segments[i]
            if edge == 0:
                self.segments[i][0] = min(ms, b - MIN_SEG_MS)
            else:
                self.segments[i][1] = max(ms, a + MIN_SEG_MS)
            ms = self.segments[i][edge]
            self.segments_changed.emit()
        else:
            if self._drag[1] == "in":
                self.in_ms = ms if self.out_ms is None else min(ms, self.out_ms - MIN_SEG_MS)
                ms = self.in_ms
            else:
                self.out_ms = ms if self.in_ms is None else max(ms, self.in_ms + MIN_SEG_MS)
                ms = self.out_ms
            self.marks_changed.emit()
        # Тянем край — видим кадр под краем, как в Clipr.
        self.position = ms
        self.seek.emit(ms)
        self.update()

    def mouseReleaseEvent(self, e) -> None:
        if self._drag is not None:
            self._drag = None
            self.scrub_finished.emit()
            self.update()

    def leaveEvent(self, e) -> None:
        self._hover_x = None
        self.update()

    # --- отрисовка ---------------------------------------------------------- #
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._track()

        # Дорожка.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.SEGMENT_BG))
        p.drawRoundedRect(t, 8, 8)

        # Деления времени: подписи над дорожкой.
        if self.duration:
            self._ticks(p, t)

        clip = QPainterPath()
        clip.addRoundedRect(t, 8, 8)
        p.save()
        p.setClipPath(clip)

        # Фрагменты.
        accent = QColor(theme.ACCENT)
        for i, (a, b) in enumerate(self.segments):
            r = QRectF(self._x(a), t.top(), max(3.0, self._x(b) - self._x(a)), t.height())
            fill = QColor(accent)
            fill.setAlphaF(0.85 if i == self.current else 0.45)
            if i == self._flash_index and self._flash.value > 0:
                fill = theme.mix(fill.name(), "#FFFFFF", 0.55 * self._flash.value)
                fill.setAlphaF(0.85)
            p.setBrush(fill)
            p.drawRoundedRect(r.adjusted(0.5, 2, -0.5, -2), 5, 5)
        p.restore()

        # Номера фрагментов поверх плашек, если влезают.
        p.setFont(self._font(10, QFont.DemiBold))
        for i, (a, b) in enumerate(self.segments):
            w = self._x(b) - self._x(a)
            if w > 22:
                p.setPen(QColor(255, 255, 255, 230 if i == self.current else 170))
                p.drawText(QRectF(self._x(a), t.top(), w, t.height()), Qt.AlignCenter, str(i + 1))

        # Черновой диапазон In–Out.
        if self.in_ms is not None or self.out_ms is not None:
            a = self.in_ms if self.in_ms is not None else 0
            b = self.out_ms if self.out_ms is not None else self.duration
            if self.in_ms is not None and self.out_ms is not None:
                r = QRectF(self._x(a), t.top() + 1, self._x(b) - self._x(a), t.height() - 2)
                fill = QColor(theme.OK)
                fill.setAlphaF(0.16)
                p.setBrush(fill)
                p.setPen(QPen(QColor(theme.OK), 1.2, Qt.DashLine))
                p.drawRoundedRect(r, 5, 5)
            for ms, is_in in ((self.in_ms, True), (self.out_ms, False)):
                if ms is not None:
                    self._marker(p, t, self._x(ms), is_in)

        # Линия под курсором и время.
        if self._hover_x is not None and self.duration and self._drag is None:
            x = max(t.left(), min(t.right(), self._hover_x))
            p.setPen(QPen(QColor(255, 255, 255, 70), 1))
            p.drawLine(QPointF(x, t.top()), QPointF(x, t.bottom()))
            self._bubble(p, x, fmt(self._ms(x)), dim=True)

        # Указатель воспроизведения.
        if self.duration:
            x = self._x(self.position)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawRoundedRect(QRectF(x - 2, t.top() - 4, 4, t.height() + 8), 2, 2)
            p.setBrush(QColor("#FFFFFF"))
            p.drawRoundedRect(QRectF(x - 1, t.top() - 4, 2, t.height() + 8), 1, 1)
            p.drawEllipse(QPointF(x, t.top() - 4), 4, 4)
            if self._drag is not None:
                self._bubble(p, x, fmt(self.position))
        p.end()

    def _marker(self, p: QPainter, t: QRectF, x: float, is_in: bool) -> None:
        colour = QColor(theme.OK)
        p.setPen(QPen(colour, 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x, t.top() - 2), QPointF(x, t.bottom() + 2))
        d = 6 if is_in else -6
        p.drawLine(QPointF(x, t.top() - 2), QPointF(x + d, t.top() - 2))
        p.drawLine(QPointF(x, t.bottom() + 2), QPointF(x + d, t.bottom() + 2))

    def _font(self, px: int, weight=QFont.Normal) -> QFont:
        f = QFont("Segoe UI Variable Text")
        f.setFamilies(["Segoe UI Variable Text", "Segoe UI"])
        f.setPixelSize(px)
        f.setWeight(weight)
        return f

    def _ticks(self, p: QPainter, t: QRectF) -> None:
        # Шаг подбираем так, чтобы подписи не слипались: не чаще ~90 px.
        steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200]
        px_per_s = t.width() / (self.duration / 1000)
        step = next((s for s in steps if s * px_per_s >= 90), steps[-1])
        p.setFont(self._font(10))
        p.setPen(QColor(theme.TEXT_DIM))
        s = 0
        while s * 1000 <= self.duration:
            x = self._x(s * 1000)
            p.drawLine(QPointF(x, t.top() - 4), QPointF(x, t.top() - 1))
            if x + 40 < t.right() or s == 0:
                p.drawText(QRectF(x + 3, 2, 60, 14), Qt.AlignLeft | Qt.AlignVCenter,
                           fmt(s * 1000, short=True))
            s += step

    def _bubble(self, p: QPainter, x: float, text: str, dim: bool = False) -> None:
        p.setFont(self._font(10, QFont.DemiBold))
        w = p.fontMetrics().horizontalAdvance(text) + 12
        r = QRectF(x - w / 2, 0, w, 17)
        r.moveLeft(max(0.0, min(self.width() - w, r.left())))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.SURFACE_RAISED) if dim else QColor("#FFFFFF"))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(QColor(theme.TEXT) if dim else QColor("#111114"))
        p.drawText(r, Qt.AlignCenter, text)

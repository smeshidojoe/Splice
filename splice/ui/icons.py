"""Иконки рисуются кодом — программа не тащит с собой картинок.

Знак программы — плёнка, разрезанная наискось: две половины кадра чуть
разъехались, между ними акцентный шов. Тот же рисунок идёт в exe
(tools_gen_assets.py), в заголовок окна и на баннер.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from . import theme


def _pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)

    body = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#22232A"))
    p.drawRoundedRect(body, s * 0.24, s * 0.24)

    # Кадр плёнки, разрезанный по диагонали: левая и правая половины.
    frame = QRectF(s * 0.20, s * 0.30, s * 0.60, s * 0.40)
    gap = s * 0.045
    cut_top, cut_bottom = s * 0.56, s * 0.44           # шов идёт наискось
    left = QPolygonF([frame.topLeft(), QPointF(cut_top - gap, frame.top()),
                      QPointF(cut_bottom - gap, frame.bottom()), frame.bottomLeft()])
    right = QPolygonF([QPointF(cut_top + gap, frame.top()), frame.topRight(),
                       frame.bottomRight(), QPointF(cut_bottom + gap, frame.bottom())])
    radius = s * 0.06
    p.setBrush(QColor("#F2F2F4"))
    for poly, dy in ((left, s * 0.025), (right, -s * 0.025)):
        clip = QPainterPath()
        clip.addRoundedRect(frame.translated(0, dy), radius, radius)
        p.save()
        p.setClipPath(clip)
        p.drawPolygon(poly.translated(0, dy))
        p.restore()

    # Перфорация — без неё это просто прямоугольник.
    p.setBrush(QColor("#22232A"))
    hole = s * 0.045
    for i in range(4):
        x = frame.left() + s * 0.06 + i * s * 0.13
        dy = s * 0.025 if x < s * 0.5 else -s * 0.025
        for y in (frame.top() + s * 0.04, frame.bottom() - s * 0.04 - hole):
            p.drawRoundedRect(QRectF(x, y + dy, hole * 1.3, hole), hole * 0.3, hole * 0.3)

    # Шов разреза — акцент.
    pen = QPen(QColor(theme.ACCENT), max(1.0, s * 0.05))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(cut_top + s * 0.04, frame.top() - s * 0.10),
               QPointF(cut_bottom - s * 0.04, frame.bottom() + s * 0.10))
    p.end()
    return pixmap


def app_pixmap(size: int) -> QPixmap:
    return _pixmap(size)


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_pixmap(size))
    return icon


# --- пиктограммы интерфейса ------------------------------------------------ #
# Одна сетка 24×24, одна толщина штриха, скруглённые концы.

_GRID = 24.0


def _pen(colour: QColor, width: float = 2.0) -> QPen:
    pen = QPen(colour, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _draw(p: QPainter, name: str, c: QColor) -> None:
    p.setPen(_pen(c))
    p.setBrush(Qt.NoBrush)
    if name == "play":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        path = QPainterPath()
        path.moveTo(8, 5.5)
        path.lineTo(18.5, 12)
        path.lineTo(8, 18.5)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "pause":
        p.setPen(_pen(c, 3.0))
        p.drawLine(QPointF(9, 6.5), QPointF(9, 17.5))
        p.drawLine(QPointF(15, 6.5), QPointF(15, 17.5))
    elif name in ("prev", "next"):
        flip = name == "next"
        x = (lambda v: 24 - v) if flip else (lambda v: v)
        p.drawLine(QPointF(x(7), 6.5), QPointF(x(7), 17.5))
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        path = QPainterPath()
        path.moveTo(x(17.5), 6.5)
        path.lineTo(x(10), 12)
        path.lineTo(x(17.5), 17.5)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "in":
        p.drawPolyline([QPointF(13, 5), QPointF(8, 5), QPointF(8, 19), QPointF(13, 19)])
        p.drawLine(QPointF(12, 12), QPointF(18, 12))
    elif name == "out":
        p.drawPolyline([QPointF(11, 5), QPointF(16, 5), QPointF(16, 19), QPointF(11, 19)])
        p.drawLine(QPointF(6, 12), QPointF(12, 12))
    elif name == "plus":
        p.drawLine(QPointF(12, 6), QPointF(12, 18))
        p.drawLine(QPointF(6, 12), QPointF(18, 12))
    elif name == "close":
        p.drawLine(QPointF(7.5, 7.5), QPointF(16.5, 16.5))
        p.drawLine(QPointF(16.5, 7.5), QPointF(7.5, 16.5))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(4, 7.5)
        path.quadTo(4, 5.5, 6, 5.5)
        path.lineTo(9.5, 5.5)
        path.lineTo(11.5, 7.5)
        path.lineTo(18, 7.5)
        path.quadTo(20, 7.5, 20, 9.5)
        path.lineTo(20, 16.5)
        path.quadTo(20, 18.5, 18, 18.5)
        path.lineTo(6, 18.5)
        path.quadTo(4, 18.5, 4, 16.5)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "more":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        for x in (6, 12, 18):
            p.drawEllipse(QPointF(x, 12), 1.7, 1.7)
    elif name in ("up", "down"):
        y = (lambda v: 24 - v) if name == "down" else (lambda v: v)
        p.drawPolyline([QPointF(7, y(14.5)), QPointF(12, y(9.5)), QPointF(17, y(14.5))])
    elif name == "scissors":
        p.drawEllipse(QPointF(7, 17), 2.8, 2.8)
        p.drawEllipse(QPointF(17, 17), 2.8, 2.8)
        p.drawLine(QPointF(9, 15), QPointF(17, 4.5))
        p.drawLine(QPointF(15, 15), QPointF(7, 4.5))
    elif name == "merge":
        p.drawPolyline([QPointF(5, 6), QPointF(9, 6), QPointF(13, 12), QPointF(19, 12)])
        p.drawPolyline([QPointF(5, 18), QPointF(9, 18), QPointF(13, 12)])
        p.drawPolyline([QPointF(16, 9), QPointF(19, 12), QPointF(16, 15)])


def glyph(name: str, colour: str | QColor = theme.TEXT, size: int = 18) -> QIcon:
    """Пиктограмма для кнопки. Рисуем сразу в двух плотностях: 1× и 2×."""
    icon = QIcon()
    c = QColor(colour)
    for scale in (1, 2):
        px = size * scale
        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(px / _GRID, px / _GRID)
        _draw(p, name, c)
        p.end()
        pixmap.setDevicePixelRatio(scale)
        icon.addPixmap(pixmap)
    return icon

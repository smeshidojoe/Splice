"""Окно нарезки: просмотр, точки In/Out, список фрагментов, экспорт.

Фрагментов сколько угодно. Без Merge Chopped каждый сохраняется отдельным
файлом рядом с исходником: имя_part1, имя_part2… С Merge Chopped фрагменты
режутся во временную папку и склеиваются в имя_chopped — тоже без
перекодирования.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox,
    QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from .. import ffmpeg
from ..i18n import tr
from . import icons, theme
from .common import (
    UpdateBar, beep, dark_titlebar, icon_button, more_button, show_in_folder,
    text_button, window_style,
)
from .controls import ProgressLine, Switch, label
from .timeline import Timeline, fmt


class SegmentRow(QWidget):
    """Строка списка: номер, начало → конец, длина, крестик."""

    def __init__(self, index: int, a: int, b: int, on_remove, pending: bool = False) -> None:
        super().__init__()
        self.setObjectName("row")
        self.setAttribute(Qt.WA_StyledBackground)
        num = label("•" if pending else str(index + 1), "rowNum")
        num.setFixedWidth(18)
        times = label(f"{fmt(a)}  →  {fmt(b)}", "rowTime")
        length = label(tr("chop.pending") if pending else f"{(b - a) / 1000:.2f} s", "rowLen")
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(times)
        text.addWidget(length)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 6, 7)
        lay.setSpacing(8)
        lay.addWidget(num)
        lay.addLayout(text, 1)
        if not pending:
            close = icon_button("close", tr("chop.remove_tip"), 14)
            close.clicked.connect(lambda: on_remove(index))
            lay.addWidget(close)

    def set_current(self, on: bool) -> None:
        self.setProperty("current", on)
        self.style().unpolish(self)
        self.style().polish(self)


class ChopperWindow(QWidget):
    def __init__(self, app, files: list[str]) -> None:
        super().__init__()
        self.app = app
        self.queue = list(files[1:])
        self.src = ""
        self.fps = 30.0
        self.worker: ffmpeg.Worker | None = None
        self.last_out = ""
        self._was_playing = False

        self.setObjectName("window")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(window_style())
        self.setWindowIcon(icons.app_icon())
        self.resize(1240, 760)
        self.setMinimumSize(900, 560)

        self._build()
        self._shortcuts()
        dark_titlebar(self)
        self.load(files[0])

    # --- сборка ------------------------------------------------------------- #
    def _build(self) -> None:
        # Плеер.
        self.video = QVideoWidget()
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video.setStyleSheet("background: #000;")
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.6)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.durationChanged.connect(self._on_duration)
        self.player.positionChanged.connect(self._on_position)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.errorOccurred.connect(
            lambda _e, msg: self._status(tr("chop.player_error", msg=msg), error=True))

        # Шапка.
        self.name = label("", "fileName")
        self.meta = label("", "value")
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self.name)
        head.addWidget(self.meta)
        head.addStretch()
        head.addWidget(more_button(self.app, self))

        # Таймлайн.
        self.timeline = Timeline()
        self.timeline.seek.connect(self._seek_to)
        self.timeline.selected.connect(self._select)
        self.timeline.segments_changed.connect(self._refresh_list)
        self.timeline.marks_changed.connect(self._refresh_marks)
        self.timeline.scrub_started.connect(self._scrub_start)
        self.timeline.scrub_finished.connect(self._scrub_end)

        # Транспорт.
        self.btn_prev = icon_button("prev", tr("chop.prev_tip"))
        self.btn_prev.clicked.connect(lambda: self.step(-1))
        self.btn_play = icon_button("play", tr("chop.play_tip"), 20)
        self.btn_play.clicked.connect(self.toggle)
        self.btn_next = icon_button("next", tr("chop.next_tip"))
        self.btn_next.clicked.connect(lambda: self.step(1))
        self.time = label("00:00:00.000", "timecode")
        self.total = label("/ 00:00:00.000", "value")

        vol = QSlider(Qt.Horizontal)
        vol.setRange(0, 100)
        vol.setValue(60)
        vol.setFixedWidth(84)
        vol.setFocusPolicy(Qt.NoFocus)
        vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))

        self.btn_in = text_button(tr("chop.in"), icon="in")
        self.btn_in.setToolTip(tr("chop.in_tip"))
        self.btn_in.clicked.connect(self.set_in)
        self.lbl_in = label("—", "mark")
        self.btn_out = text_button(tr("chop.out"), icon="out")
        self.btn_out.setToolTip(tr("chop.out_tip"))
        self.btn_out.clicked.connect(self.set_out)
        self.lbl_out = label("—", "mark")
        self.btn_add = text_button(tr("chop.add"), primary=True, icon="plus")
        self.btn_add.setToolTip(tr("chop.add_tip"))
        self.btn_add.clicked.connect(self.add_segment)

        transport = QHBoxLayout()
        transport.setSpacing(6)
        for w in (self.btn_prev, self.btn_play, self.btn_next):
            transport.addWidget(w)
        transport.addSpacing(10)
        transport.addWidget(self.time)
        transport.addWidget(self.total)
        transport.addSpacing(12)
        transport.addWidget(vol)
        transport.addStretch()
        transport.addWidget(self.btn_in)
        transport.addWidget(self.lbl_in)
        transport.addSpacing(6)
        transport.addWidget(self.btn_out)
        transport.addWidget(self.lbl_out)
        transport.addSpacing(6)
        transport.addWidget(self.btn_add)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addLayout(head)
        left.addWidget(self.video, 1)
        left.addWidget(self.timeline)
        left.addLayout(transport)

        # Правая панель.
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(320)

        self.count = label("", "sectionTitle")
        clear = text_button(tr("chop.clear"))
        clear.clicked.connect(self.clear_segments)
        self.btn_clear = clear
        top = QHBoxLayout()
        top.addWidget(self.count)
        top.addStretch()
        top.addWidget(clear)

        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.currentRowChanged.connect(self._list_row)
        self.list.itemDoubleClicked.connect(lambda _i: self._jump_current())
        self.empty = label(tr("chop.empty"), "empty", wrap=True)
        self.empty.setAlignment(Qt.AlignCenter)

        self.switch = Switch(bool(self.app.config["merge_chopped"]))
        self.switch.setFocusPolicy(Qt.NoFocus)
        self.switch.toggled.connect(self._merge_toggled)
        merge_text = QVBoxLayout()
        merge_text.setSpacing(1)
        merge_text.addWidget(label(tr("chop.merge"), "rowTitle"))
        merge_text.addWidget(label(tr("chop.merge_note"), "rowNote", wrap=True))
        merge_row = QHBoxLayout()
        merge_row.addLayout(merge_text, 1)
        merge_row.addWidget(self.switch, 0, Qt.AlignVCenter)

        self.folder = text_button("", icon="folder")
        self.folder.clicked.connect(self.choose_dir)
        self.out_dir = ""

        self.btn_export = text_button(tr("chop.export"), primary=True, icon="scissors")
        self.btn_export.setMinimumHeight(42)
        self.btn_export.clicked.connect(self.export)
        self.btn_cancel = text_button(tr("chop.cancel"))
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_cancel.hide()
        self.progress = ProgressLine()
        self.progress.hide()
        self.status = label("", "status", wrap=True)
        self.btn_show = text_button(tr("chop.show"), icon="folder")
        self.btn_show.clicked.connect(lambda: show_in_folder(self.last_out))
        self.btn_show.hide()
        self.btn_queue = text_button("")
        self.btn_queue.clicked.connect(self.load_next)
        hint = label(tr("chop.hint"), "hint", wrap=True)

        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 14, 14, 14)
        sl.setSpacing(10)
        sl.addLayout(top)
        sl.addWidget(self.list, 1)
        sl.addWidget(self.empty, 1)
        sl.addWidget(_hairline())
        sl.addLayout(merge_row)
        sl.addWidget(label(tr("chop.folder"), "sectionTitle"))
        sl.addWidget(self.folder)
        sl.addSpacing(4)
        sl.addWidget(self.btn_export)
        sl.addWidget(self.progress)
        sl.addWidget(self.status)
        sl.addWidget(self.btn_cancel)
        sl.addWidget(self.btn_show)
        sl.addWidget(self.btn_queue)
        sl.addWidget(hint)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addLayout(left, 1)
        body.addWidget(side)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)
        root.addWidget(UpdateBar(self.app, self))
        root.addLayout(body, 1)

    def _shortcuts(self) -> None:
        keys = [
            ("Space", self.toggle), ("I", self.set_in), ("O", self.set_out),
            ("Return", self.add_segment), ("Enter", self.add_segment),
            ("Delete", self.remove_current), ("Backspace", self.remove_current),
            ("Left", lambda: self.step(-1)), ("Right", lambda: self.step(1)),
            ("Shift+Left", lambda: self.seek_rel(-1000)),
            ("Shift+Right", lambda: self.seek_rel(1000)),
            ("Ctrl+Left", lambda: self.seek_rel(-10000)),
            ("Ctrl+Right", lambda: self.seek_rel(10000)),
            ("Home", lambda: self._seek_to(0)),
            ("End", lambda: self._seek_to(self.timeline.duration)),
            ("[", lambda: self._jump_mark(0)), ("]", lambda: self._jump_mark(1)),
            ("Ctrl+S", self.export), ("Escape", self.close),
        ]
        for key, fn in keys:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(fn)

    # --- файл --------------------------------------------------------------- #
    def load(self, path: str) -> None:
        path = os.path.normpath(path)
        self.src = path
        info = ffmpeg.probe(path)
        self.fps = info.get("fps") or 30.0
        tl = self.timeline
        tl.segments, tl.current, tl.in_ms, tl.out_ms = [], -1, None, None
        tl.duration = info.get("duration", 0)
        tl.position = 0
        self.out_dir = os.path.dirname(path)
        self._show_folder()
        self.name.setText(os.path.basename(path))
        self.setWindowTitle(tr("chop.title", name=os.path.basename(path)))
        self._update_meta(tl.duration)
        self._status("")
        self.btn_show.hide()
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.pause()                 # показать первый кадр
        self._refresh_queue()
        self._refresh_all()

    def _update_meta(self, duration: int) -> None:
        self.meta.setText(f"{fmt(duration, short=True)} · {self.fps:.3g} fps")
        self.total.setText("/ " + fmt(duration))

    def load_next(self) -> None:
        if self.queue and not self._busy():
            self.load(self.queue.pop(0))

    def _refresh_queue(self) -> None:
        self.btn_queue.setText(tr("chop.next_file", n=len(self.queue)))
        self.btn_queue.setVisible(bool(self.queue))

    # --- плеер -------------------------------------------------------------- #
    def _on_duration(self, d: int) -> None:
        if d > 0:
            self.timeline.duration = d
            self._update_meta(d)
            self.timeline.update()

    def _on_position(self, pos: int) -> None:
        if not self.timeline.dragging():
            self.timeline.set_position(pos)
        self.time.setText(fmt(pos))

    def _on_state(self, state) -> None:
        playing = state == QMediaPlayer.PlayingState
        self.btn_play.setIcon(icons.glyph("pause" if playing else "play", theme.TEXT, 20))

    def _pos(self) -> int:
        return self.timeline.position

    def _seek_to(self, ms: int) -> None:
        ms = max(0, min(self.timeline.duration, int(ms)))
        self.timeline.set_position(ms)
        self.time.setText(fmt(ms))
        self.player.setPosition(ms)

    def _scrub_start(self) -> None:
        self._was_playing = self.player.playbackState() == QMediaPlayer.PlayingState
        if self._was_playing:
            self.player.pause()

    def _scrub_end(self) -> None:
        self._sort_segments()
        if self._was_playing:
            self.player.play()

    def toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if self._pos() >= self.timeline.duration - 50:
                self._seek_to(0)
            self.player.play()

    def step(self, frames: int) -> None:
        self.player.pause()
        self.seek_rel(round(frames * 1000 / self.fps))

    def seek_rel(self, delta: int) -> None:
        self._seek_to(self._pos() + delta)

    # --- точки и фрагменты --------------------------------------------------- #
    def set_in(self) -> None:
        tl = self.timeline
        tl.in_ms = self._pos()
        if tl.out_ms is not None and tl.out_ms <= tl.in_ms:
            tl.out_ms = None
        self._refresh_marks()

    def set_out(self) -> None:
        tl = self.timeline
        tl.out_ms = self._pos()
        if tl.in_ms is None:
            # Out без In — фрагмент от начала или от конца предыдущего.
            tl.in_ms = max([b for _a, b in tl.segments if b < tl.out_ms] or [0])
        if tl.in_ms >= tl.out_ms:
            tl.in_ms = None
        self._refresh_marks()

    def _pending(self):
        tl = self.timeline
        if tl.in_ms is not None and tl.out_ms is not None and tl.out_ms > tl.in_ms:
            return tl.in_ms, tl.out_ms
        return None

    def add_segment(self) -> None:
        pending = self._pending()
        if not pending:
            self._status(tr("chop.need_range"), error=True)
            return
        tl = self.timeline
        seg = list(pending)
        tl.segments.append(seg)
        tl.in_ms = tl.out_ms = None
        self._sort_segments()
        idx = next(i for i, s in enumerate(tl.segments) if s is seg)
        tl.current = idx
        tl.flash(idx)
        self._status("")
        self._refresh_all()

    def _sort_segments(self) -> None:
        tl = self.timeline
        cur = tl.segments[tl.current] if 0 <= tl.current < len(tl.segments) else None
        tl.segments.sort(key=lambda s: (s[0], s[1]))
        tl.current = next((i for i, s in enumerate(tl.segments) if s is cur), -1)
        self._refresh_list()

    def remove_current(self) -> None:
        self.remove(self.timeline.current)

    def remove(self, index: int) -> None:
        tl = self.timeline
        if 0 <= index < len(tl.segments):
            del tl.segments[index]
            tl.current = min(index, len(tl.segments) - 1)
            self._refresh_all()
        elif self._pending() or tl.in_ms is not None or tl.out_ms is not None:
            tl.in_ms = tl.out_ms = None       # Del без фрагментов — сбросить черновик
            self._refresh_marks()

    def clear_segments(self) -> None:
        tl = self.timeline
        tl.segments.clear()
        tl.current = -1
        tl.in_ms = tl.out_ms = None
        self._refresh_all()

    def _select(self, index: int) -> None:
        self.timeline.current = index
        self._refresh_list()

    def _list_row(self, row: int) -> None:
        if row != self.timeline.current and row < len(self.timeline.segments):
            self.timeline.current = row
            self._refresh_list(keep_row=True)
            self._jump_current()

    def _jump_current(self) -> None:
        i = self.timeline.current
        if 0 <= i < len(self.timeline.segments):
            self._seek_to(self.timeline.segments[i][0])

    def _jump_mark(self, edge: int) -> None:
        tl = self.timeline
        if 0 <= tl.current < len(tl.segments):
            self._seek_to(tl.segments[tl.current][edge])
        else:
            ms = tl.in_ms if edge == 0 else tl.out_ms
            if ms is not None:
                self._seek_to(ms)

    # --- обновление вида ---------------------------------------------------- #
    def _refresh_all(self) -> None:
        self._refresh_marks()
        self._refresh_list()

    def _refresh_marks(self) -> None:
        tl = self.timeline
        self.lbl_in.setText(fmt(tl.in_ms) if tl.in_ms is not None else "—")
        self.lbl_out.setText(fmt(tl.out_ms) if tl.out_ms is not None else "—")
        self.btn_add.setEnabled(self._pending() is not None)
        tl.update()
        self._refresh_list()

    def _refresh_list(self, keep_row: bool = False) -> None:
        tl = self.timeline
        scroll = self.list.verticalScrollBar().value()
        self.list.blockSignals(True)
        self.list.clear()
        rows = [(i, a, b, False) for i, (a, b) in enumerate(tl.segments)]
        pending = self._pending()
        if pending:
            rows.append((len(rows), pending[0], pending[1], True))
        for i, a, b, is_pending in rows:
            row = SegmentRow(i, a, b, self.remove, pending=is_pending)
            row.set_current(i == tl.current and not is_pending)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, row.sizeHint().height()))
            if is_pending:
                item.setFlags(Qt.NoItemFlags)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        if 0 <= tl.current < len(tl.segments):
            self.list.setCurrentRow(tl.current)
        self.list.blockSignals(False)
        self.list.verticalScrollBar().setValue(scroll)
        if 0 <= tl.current < self.list.count() and not keep_row:
            self.list.scrollToItem(self.list.item(tl.current))

        has_rows = bool(rows)
        self.list.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        n = len(tl.segments)
        self.count.setText(f"{tr('chop.ranges')} · {n}" if n else tr("chop.ranges"))
        self.btn_clear.setVisible(bool(n or pending))
        self._refresh_export()
        tl.update()

    def _export_segments(self) -> list[tuple[int, int]]:
        segs = [(a, b) for a, b in self.timeline.segments if b > a]
        if not segs and self._pending():
            segs = [self._pending()]           # один диапазон можно и не добавлять
        return sorted(segs)

    def _refresh_export(self) -> None:
        n = len(self._export_segments())
        if self.switch.isChecked() and n > 1:
            text = tr("chop.export_merged")
        elif n > 1:
            text = tr("chop.export_n", n=n)
        else:
            text = tr("chop.export")
        self.btn_export.setText(text)
        self.btn_export.setEnabled(n > 0 and not self._busy())
        self.btn_export.updateGeometry()

    def _merge_toggled(self, on: bool) -> None:
        self.app.config["merge_chopped"] = on
        self._refresh_export()

    def _show_folder(self) -> None:
        metrics = self.folder.fontMetrics()
        self.folder.setText(metrics.elidedText(self.out_dir, Qt.ElideMiddle, 240))
        self.folder.setToolTip(self.out_dir)

    def choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("chop.folder_pick"), self.out_dir)
        if d:
            self.out_dir = os.path.normpath(d)
            self._show_folder()

    def _status(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    # --- экспорт ------------------------------------------------------------ #
    def _busy(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def export(self) -> None:
        if self._busy():
            return
        segs = self._export_segments()
        if not segs:
            self._status(tr("chop.nothing"), error=True)
            return
        merge = self.switch.isChecked() and len(segs) > 1
        self.player.pause()
        self.btn_show.hide()
        self._set_busy(True)
        texts = {"cut": lambda i, n: tr("chop.cut", i=i, n=n),
                 "merge": lambda: tr("chop.merging")}
        src, out_dir = self.src, self.out_dir
        self.worker = ffmpeg.Worker(
            lambda job: ffmpeg.chop(job, src, out_dir, segs, merge, texts), self)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.start()

    def cancel(self) -> None:
        if self._busy():
            self.worker.cancel()

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.btn_cancel.setVisible(busy)
        self.btn_queue.setEnabled(not busy)
        if busy:
            self.progress.set_fraction(0.0)
        self._refresh_export()

    def _on_progress(self, fraction: float, text: str) -> None:
        self.progress.set_fraction(fraction)
        if text:
            self._status(text)

    def _finish(self) -> None:
        if self.worker:
            self.worker.wait(2000)
        self._set_busy(False)

    def _on_done(self, outs: list) -> None:
        self._finish()
        tl = self.timeline
        tl.segments.clear()
        tl.current = -1
        tl.in_ms = tl.out_ms = None
        self._refresh_all()
        self.last_out = outs[0] if outs else ""
        self._status(tr("chop.saved", names=", ".join(os.path.basename(o) for o in outs)))
        self.btn_show.show()
        beep()

    def _on_failed(self, msg: str) -> None:
        self._finish()
        self._status(tr("chop.failed"), error=True)
        QMessageBox.critical(self, tr("chop.failed"), msg)

    def _on_cancelled(self) -> None:
        self._finish()
        self._status(tr("chop.cancelled"))

    # --- окно --------------------------------------------------------------- #
    def showEvent(self, e) -> None:
        super().showEvent(e)
        QTimer.singleShot(0, lambda: dark_titlebar(self))

    def closeEvent(self, e) -> None:
        if self._busy():
            if QMessageBox.question(self, self.windowTitle(), tr("chop.busy_close")) \
                    != QMessageBox.Yes:
                e.ignore()
                return
            self.worker.cancel()
            self.worker.wait(5000)
        self.player.stop()
        super().closeEvent(e)


def _hairline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {theme.HAIRLINE};")
    return line

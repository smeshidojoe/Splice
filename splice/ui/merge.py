"""Merge with Splice: выделенные в проводнике файлы склеиваются в один без
перекодирования. Порядок — естественная сортировка имён, его можно поменять
перетаскиванием или кнопками."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QListWidget, QListWidgetItem,
    QMessageBox, QVBoxLayout, QWidget,
)

from .. import ffmpeg
from ..constants import VIDEO_EXTS
from ..i18n import tr
from . import icons
from .common import (
    UpdateBar, beep, dark_titlebar, icon_button, more_button, show_in_folder,
    text_button, window_style,
)
from .controls import ProgressLine, label


def video_filter() -> str:
    return "%s (%s);;%s (*.*)" % (tr("chop.videos"), " ".join("*" + e for e in VIDEO_EXTS),
                                  tr("chop.all_files"))


class MergeWindow(QWidget):
    def __init__(self, app, files: list[str]) -> None:
        super().__init__()
        self.app = app
        self.worker: ffmpeg.Worker | None = None
        self.out_touched = False
        self.setObjectName("window")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(window_style())
        self.setWindowIcon(icons.app_icon())
        self.setWindowTitle(tr("merge.title"))
        self.resize(680, 560)

        self.list = QListWidget()
        self.list.setObjectName("mergeList")
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setStyleSheet(
            "QListWidget::item { background: rgba(255,255,255,0.05); border-radius: 9px;"
            " padding: 9px 10px; margin-bottom: 4px; }"
            "QListWidget::item:selected { background: rgba(76,141,255,0.25); }")
        self.list.model().rowsMoved.connect(lambda *_: self._changed())

        tools = QHBoxLayout()
        for name, tip, fn in (("up", "merge.up_tip", lambda: self._move(-1)),
                              ("down", "merge.down_tip", lambda: self._move(1)),
                              ("close", "merge.remove_tip", self._remove),
                              ("scissors", "merge.chop_tip", self._chop)):
            b = icon_button(name, tr(tip))
            b.clicked.connect(fn)
            tools.addWidget(b)
        tools.addStretch()
        add = text_button(tr("merge.add"), icon="plus")
        add.clicked.connect(self._add_dialog)
        tools.addWidget(add)

        self.out = text_button("", icon="folder")
        self.out.clicked.connect(self._pick_out)
        self.out_path = ""
        self.warn = label("", "rowNote", wrap=True)
        self.warn.setProperty("warn", True)
        self.btn = text_button(tr("merge.go"), primary=True, icon="merge")
        self.btn.setMinimumHeight(42)
        self.btn.clicked.connect(self.merge)
        self.btn_cancel = text_button(tr("chop.cancel"))
        self.btn_cancel.clicked.connect(lambda: self.worker and self.worker.cancel())
        self.btn_cancel.hide()
        self.progress = ProgressLine()
        self.progress.hide()
        self.status = label("", "status", wrap=True)
        self.btn_show = text_button(tr("chop.show"), icon="folder")
        self.btn_show.hide()
        self.last_out = ""
        self.btn_show.clicked.connect(lambda: show_in_folder(self.last_out))

        card = QFrame()
        card.setObjectName("side")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 14, 14, 14)
        cl.setSpacing(10)
        cl.addWidget(label(tr("merge.order"), "sectionTitle"))
        cl.addWidget(self.list, 1)
        cl.addLayout(tools)
        cl.addWidget(label(tr("merge.output"), "sectionTitle"))
        cl.addWidget(self.out)
        cl.addWidget(self.warn)
        cl.addWidget(self.btn)
        cl.addWidget(self.progress)
        cl.addWidget(self.status)
        cl.addWidget(self.btn_cancel)
        cl.addWidget(self.btn_show)

        head = QHBoxLayout()
        head.addWidget(label(tr("merge.title"), "fileName"))
        head.addStretch()
        head.addWidget(more_button(app, self))

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)
        root.addWidget(UpdateBar(app, self))
        root.addLayout(head)
        root.addWidget(card, 1)
        self.add_files(files)

    # --- список ------------------------------------------------------------ #
    def files(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def add_files(self, files: list[str]) -> None:
        have = set(self.files())
        for f in files:
            if f not in have:
                it = QListWidgetItem(os.path.basename(f))
                it.setData(Qt.UserRole, f)
                it.setToolTip(f)
                self.list.addItem(it)
        self._changed()

    def _add_dialog(self) -> None:
        from ..instance import natural_key
        fs, _ = QFileDialog.getOpenFileNames(self, tr("merge.add"), "", video_filter())
        if fs:
            self.add_files(sorted((os.path.normpath(f) for f in fs), key=natural_key))

    def _move(self, d: int) -> None:
        r = self.list.currentRow()
        n = r + d
        if r < 0 or not 0 <= n < self.list.count():
            return
        self.list.insertItem(n, self.list.takeItem(r))
        self.list.setCurrentRow(n)
        self._changed()

    def _remove(self) -> None:
        r = self.list.currentRow()
        if r >= 0:
            self.list.takeItem(r)
            self._changed()

    def _chop(self) -> None:
        it = self.list.currentItem()
        if it:
            self.app.open_chopper([it.data(Qt.UserRole)])

    def _changed(self) -> None:
        fs = self.files()
        if fs and not self.out_touched:
            name, ext = os.path.splitext(os.path.basename(fs[0]))
            self.out_path = ffmpeg.unique_path(os.path.dirname(fs[0]), name + "_merged", ext)
        self._show_out()
        self.btn.setEnabled(len(fs) >= 2 and not self._busy())
        # Проверка дорожек — ffprobe на каждый файл; не в момент перетаскивания.
        QTimer.singleShot(150, self._check)

    def _check(self) -> None:
        odd = ffmpeg.compatibility(self.files()) if len(self.files()) > 1 else []
        self.warn.setText(tr("merge.mismatch", names=", ".join(os.path.basename(o) for o in odd))
                          if odd else "")
        self.warn.setVisible(bool(odd))

    def _show_out(self) -> None:
        m = self.out.fontMetrics()
        self.out.setText(m.elidedText(self.out_path, Qt.ElideMiddle, 520) if self.out_path else "…")
        self.out.setToolTip(self.out_path)

    def _pick_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr("merge.output_pick"), self.out_path,
                                              video_filter())
        if path:
            self.out_path = os.path.normpath(path)
            self.out_touched = True
            self._show_out()

    # --- склейка ----------------------------------------------------------- #
    def _busy(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def merge(self) -> None:
        fs = self.files()
        if len(fs) < 2:
            self.status.setText(tr("merge.need_two"))
            return
        out = self.out_path
        if any(os.path.normcase(out) == os.path.normcase(f) for f in fs):
            self.status.setText(tr("merge.self"))
            return
        if os.path.exists(out) and QMessageBox.question(
                self, tr("merge.title"), tr("merge.exists", path=out)) != QMessageBox.Yes:
            return
        self._set_busy(True)
        texts = {"merge": lambda: tr("chop.merging")}
        self.worker = ffmpeg.Worker(lambda job: ffmpeg.merge(job, fs, out, texts), self)
        self.worker.progress.connect(lambda f, t: (self.progress.set_fraction(f),
                                                   t and self.status.setText(t)))
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.cancelled.connect(lambda: (self._finish(),
                                               self.status.setText(tr("chop.cancelled"))))
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.btn.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.btn_cancel.setVisible(busy)
        self.btn_show.hide()
        if busy:
            self.progress.set_fraction(0.0)

    def _finish(self) -> None:
        if self.worker:
            self.worker.wait(2000)
        self._set_busy(False)
        self.btn.setEnabled(len(self.files()) >= 2)

    def _done(self, outs: list) -> None:
        self._finish()
        self.last_out = outs[0]
        self.status.setText(tr("chop.saved", names=os.path.basename(outs[0])))
        self.btn_show.show()
        self.out_touched = False
        beep()

    def _failed(self, msg: str) -> None:
        self._finish()
        self.status.setText(tr("chop.failed"))
        QMessageBox.critical(self, tr("chop.failed"), msg + "\n\n" + tr("merge.failed_hint"))

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
        super().closeEvent(e)

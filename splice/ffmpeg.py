"""Работа с FFmpeg: сведения о файле, нарезка и склейка без перекодирования.

Всё — потоковое копирование (`-c copy`): ни одного кадра не пересчитываем,
поэтому быстро и без потерь. Цена — точность начала: без перекодирования
фрагмент может начаться только с ключевого кадра, и ffmpeg берёт ближайший
слева от точки In.

Склейка — concat demuxer. Ему нужны одинаковые кодеки и параметры у всех
кусков; кусков одного файла это касается всегда, разных файлов — проверяем
заранее (`compatibility`), иначе ffmpeg молча собрал бы битый файл.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading

from PySide6.QtCore import QThread, Signal

from . import tools

CREATE_NO_WINDOW = 0x08000000


class Cancelled(Exception):
    pass


class FFmpegError(RuntimeError):
    pass


# --- сведения о файле ------------------------------------------------------- #

def probe(path: str) -> dict:
    """{"duration": мс, "fps": кадров/с, "streams": [...]} или пустой словарь."""
    exe = tools.ffprobe_path()
    if not exe:
        return {}
    try:
        result = tools.run_hidden([exe, "-v", "error", "-print_format", "json",
                                   "-show_format", "-show_streams", path], timeout=20)
        data = json.loads(result.stdout or "{}")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}
    info = {"duration": 0, "fps": 0.0, "streams": data.get("streams", [])}
    try:
        info["duration"] = int(float(data.get("format", {}).get("duration", 0)) * 1000)
    except (TypeError, ValueError):
        pass
    for stream in info["streams"]:
        if stream.get("codec_type") == "video":
            info["fps"] = _rate(stream.get("avg_frame_rate")) or _rate(stream.get("r_frame_rate"))
            break
    return info


def _rate(text) -> float:
    try:
        num, _, den = str(text).partition("/")
        value = float(num) / float(den or 1)
        return value if 0 < value < 1000 else 0.0
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _signature(stream: dict) -> tuple:
    if stream.get("codec_type") == "video":
        return ("v", stream.get("codec_name"), stream.get("width"), stream.get("height"),
                stream.get("pix_fmt"))
    return ("a", stream.get("codec_name"), stream.get("sample_rate"), stream.get("channels"))


def compatibility(paths: list[str]) -> list[str]:
    """Файлы, чьи дорожки не совпадают с первым. Пустой список — склеятся."""
    first = None
    odd = []
    for path in paths:
        streams = [s for s in probe(path).get("streams", [])
                   if s.get("codec_type") in ("video", "audio")]
        sig = tuple(_signature(s) for s in streams)
        if first is None:
            first = sig
        elif sig != first:
            odd.append(path)
    return odd


# --- запуск ffmpeg с прогрессом -------------------------------------------- #

class Job:
    """Один экспорт. progress(доля 0..1, текст); cancel() — из любого потока."""

    def __init__(self, progress):
        self._progress = progress
        self._cancelled = threading.Event()
        self._proc = None

    def cancel(self):
        self._cancelled.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass

    def report(self, fraction, text=""):
        self._progress(max(0.0, min(1.0, fraction)), text)

    def run(self, args, duration_ms=0, on_fraction=None):
        """Запускает ffmpeg; on_fraction(0..1) по ходу, если известна длина."""
        if self._cancelled.is_set():
            raise Cancelled()
        exe = tools.ffmpeg_path()
        if not exe:
            raise FFmpegError("FFmpeg not found")
        cmd = [exe, "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats",
               *args]
        # stderr — в файл: читать два канала из одного потока значит рано или
        # поздно повиснуть на переполненном буфере.
        with tempfile.TemporaryFile() as err:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err,
                                          creationflags=CREATE_NO_WINDOW)
            for raw in self._proc.stdout:
                line = raw.decode("ascii", "ignore").strip()
                if on_fraction and duration_ms and line.startswith("out_time_us="):
                    try:
                        on_fraction(int(line[12:]) / 1000 / duration_ms)
                    except ValueError:
                        pass          # «N/A» в начале
            code = self._proc.wait()
            self._proc = None
            if self._cancelled.is_set():
                raise Cancelled()
            if code != 0:
                err.seek(0)
                tail = err.read().decode("utf-8", "ignore").strip().splitlines()[-12:]
                raise FFmpegError("\n".join(tail) or "ffmpeg exit code %d" % code)


def _sec(ms: int) -> str:
    return "%.3f" % (ms / 1000)


def _faststart(out: str) -> list[str]:
    return ["-movflags", "+faststart"] \
        if os.path.splitext(out)[1].lower() in (".mp4", ".mov", ".m4v") else []


def cut(job: Job, src: str, out: str, a_ms: int, b_ms: int, on_fraction=None):
    job.run(["-ss", _sec(a_ms), "-i", src, "-t", _sec(b_ms - a_ms),
             "-map", "0:v?", "-map", "0:a?", "-c", "copy",
             "-avoid_negative_ts", "make_zero", *_faststart(out), out],
            b_ms - a_ms, on_fraction)


def concat(job: Job, files: list[str], out: str, duration_ms=0, on_fraction=None):
    fd, listing = tempfile.mkstemp(suffix=".txt", prefix="splice_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for path in files:
                escaped = path.replace("\\", "/").replace("'", "'\\''")
                f.write("file '%s'\n" % escaped)
        job.run(["-f", "concat", "-safe", "0", "-i", listing,
                 "-map", "0:v?", "-map", "0:a?", "-c", "copy", *_faststart(out), out],
                duration_ms, on_fraction)
    finally:
        _remove(listing)


# --- имена файлов ------------------------------------------------------------ #

def unique_path(folder: str, stem: str, ext: str) -> str:
    path = os.path.join(folder, stem + ext)
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, "%s_%d%s" % (stem, n, ext))
        n += 1
    return path


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


# --- задания ---------------------------------------------------------------- #

def chop(job: Job, src: str, out_dir: str, segments: list[tuple[int, int]],
         merge: bool, texts: dict) -> list[str]:
    """Режет src по фрагментам; merge — ещё и склеивает их в один файл.

    texts — функции, отдающие подписи на текущем языке: модулю ffmpeg про
    переводы знать незачем.
    """
    name, ext = os.path.splitext(os.path.basename(src))
    total = sum(b - a for a, b in segments) or 1
    done = 0
    weight = 0.85 if merge else 1.0           # склейке — хвост полосы
    tmp = tempfile.mkdtemp(prefix="splice_") if merge else ""
    outs = []
    try:
        n = 1
        for i, (a, b) in enumerate(segments, 1):
            if merge:
                out = os.path.join(tmp, "part%d%s" % (i, ext))
            else:
                # part1, part2… не затирая нарезанное раньше.
                while os.path.exists(os.path.join(out_dir, "%s_part%d%s" % (name, n, ext))):
                    n += 1
                out = os.path.join(out_dir, "%s_part%d%s" % (name, n, ext))
                n += 1
            text = texts["cut"](i, len(segments))
            base, span = done, b - a
            job.report(weight * base / total, text)
            try:
                cut(job, src, out, a, b,
                    lambda f, base=base, span=span, text=text:
                        job.report(weight * (base + span * min(f, 1.0)) / total, text))
            except BaseException:
                _remove(out)                  # не оставляем огрызок
                raise
            outs.append(out)
            done += span
        if not merge:
            job.report(1.0, "")
            return outs
        final = unique_path(out_dir, name + "_chopped", ext)
        text = texts["merge"]()
        job.report(weight, text)
        try:
            concat(job, outs, final, total,
                   lambda f: job.report(weight + (1 - weight) * min(f, 1.0), text))
        except BaseException:
            _remove(final)
            raise
        job.report(1.0, "")
        return [final]
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def merge(job: Job, files: list[str], out: str, texts: dict) -> list[str]:
    total = sum(probe(f).get("duration", 0) for f in files)
    text = texts["merge"]()
    job.report(0.0, text)
    try:
        concat(job, files, out, total, lambda f: job.report(min(f, 1.0), text))
    except BaseException:
        _remove(out)
        raise
    job.report(1.0, "")
    return [out]


class Worker(QThread):
    """Гонит задание в фоне. fn(job) -> список готовых файлов."""

    progress = Signal(float, str)
    done = Signal(list)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self.job = Job(self.progress.emit)

    def cancel(self):
        self.job.cancel()

    def run(self):
        try:
            self.done.emit(self._fn(self.job))
        except Cancelled:
            self.cancelled.emit()
        except Exception as error:      # noqa: BLE001 — показываем человеку
            self.failed.emit(str(error))

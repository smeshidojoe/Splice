"""Единственный источник правды по имени, версии и путям приложения.

APP_VERSION отсюда читают Splice.spec (регуляркой, для ресурса версии exe) и
updater (для сравнения с тегом релиза на GitHub). Поднять версию = поправить
одну строку здесь.
"""

import os
import sys

APP_NAME = "Splice"
APP_VERSION = "0.1.0"

GITHUB_REPO = "smeshidojoe/Splice"
DEVELOPER_URL = "https://github.com/smeshidojoe"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"

APP_ID = "SmeshidoJoe.Splice"
# Проводник запускает программу отдельно на каждый выделенный файл. Первый
# процесс слушает этот канал, остальные отдают ему свои файлы и выходят.
# Это же имя — AppMutex установщика (splice/instance.py держит мьютекс).
INSTANCE_NAME = "Splice-Single-Instance"

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".m4v",
              ".ts", ".mts", ".m2ts", ".wmv", ".3gp")

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_dir():
    """%APPDATA%/Splice — настройки, журнал падений, скачанный FFmpeg."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def install_dir():
    """Папка установки (где лежит exe). В разработке — корень проекта."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

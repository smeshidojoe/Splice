"""Настройки: %APPDATA%/Splice/settings.json.

Немного: язык, галочка Merge Chopped, когда последний раз ходили за
обновлением. Битый или чужой файл не роняет программу — берём умолчания.
"""

import json
import os
import time

from .constants import app_dir

PATH = os.path.join(app_dir(), "settings.json")

DEFAULTS = {
    "language": "",            # "" — по языку системы
    "merge_chopped": False,
    "check_updates": True,
    "last_update_check": 0.0,
}

UPDATE_INTERVAL = 6 * 3600     # не чаще раза в шесть часов: программу запускают часто


def _system_language():
    try:
        import ctypes
        lang = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return "ru" if lang in (0x19, 0x22, 0x23) else "en"   # ru, uk, be
    except Exception:
        return "en"


class Config:
    def __init__(self):
        self.data = dict(DEFAULTS)
        try:
            with open(PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for key, value in loaded.items():
                    if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
                        self.data[key] = value
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def language(self):
        return self.data["language"] or _system_language()

    def update_due(self):
        return (self.data["check_updates"]
                and time.time() - self.data["last_update_check"] > UPDATE_INTERVAL)

    def save(self):
        try:
            os.makedirs(os.path.dirname(PATH), exist_ok=True)
            tmp = PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, PATH)
        except OSError:
            pass

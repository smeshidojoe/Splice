"""Пункты в контекстном меню проводника.

HKCU\\Software\\Classes\\SystemFileAssociations\\<.ext>\\shell\\<verb> — без прав
администратора и не трогая чужую ассоциацию файла (плеер по умолчанию
остаётся прежним). Пишет их сам exe (`--register`), установщик лишь вызывает
его после установки и `--unregister` при удалении: список расширений и
подписи живут в одном месте.

На Windows 11 пункты лежат в «Показать дополнительные параметры» (Shift+F10).
"""

from __future__ import annotations

import os
import sys

from .constants import VIDEO_EXTS
from .i18n import tr

VERBS = (("Splice.Chop", "shell.chop", "chop", "scissors"),
         ("Splice.Merge", "shell.merge", "merge", "merge"))


def _command(mode: str) -> tuple[str, str]:
    """(команда, иконка). В разработке — pythonw + main.py, без окна консоли."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return f'"{exe}" --mode {mode} "%1"', exe
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return f'"{exe}" "{main}" --mode {mode} "%1"', exe


def _base(ext: str, verb: str) -> str:
    return rf"Software\Classes\SystemFileAssociations\{ext}\shell\{verb}"


def register() -> None:
    import winreg
    for ext in VIDEO_EXTS:
        for verb, key, mode, _icon in VERBS:
            command, icon = _command(mode)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _base(ext, verb)) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, tr(key))
                winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, tr(key))
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
                # Player — без потолка в 15 файлов, который у Document.
                winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _base(ext, verb) + r"\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, command)
    _notify()


def unregister() -> None:
    import winreg
    for ext in VIDEO_EXTS:
        for verb, *_ in VERBS:
            for key in (_base(ext, verb) + r"\command", _base(ext, verb)):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
                except OSError:
                    pass
    _notify()


def _notify() -> None:
    """Проводник перечитывает ассоциации без перезапуска."""
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass


def is_registered() -> bool:
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, _base(VIDEO_EXTS[0], VERBS[0][0])).Close()
        return True
    except OSError:
        return False

"""Запуск: обновление, регистрация меню, перехват падений — до окон.

Живёт в пакете, чтобы `python main.py` и собранный exe шли одним путём.
"""

import argparse
import ctypes
import os
import sys

from .constants import APP_ID


def _args(argv):
    ap = argparse.ArgumentParser(prog="Splice")
    ap.add_argument("--mode", choices=["chop", "merge"], default="chop")
    ap.add_argument("--register", action="store_true", help="add Explorer menu items")
    ap.add_argument("--unregister", action="store_true", help="remove Explorer menu items")
    ap.add_argument("--tray", action="store_true", help="start quietly in the tray")
    ap.add_argument("--apply-update", default=None)
    ap.add_argument("files", nargs="*")
    return ap.parse_known_args(argv)[0]


def main() -> int:
    args = _args(sys.argv[1:])

    # Новый exe запущен с --apply-update <старый exe> — подменить и выйти.
    if args.apply_update is not None:
        from . import updater
        updater.apply_self_update(args.apply_update)
        return 0

    if args.register or args.unregister:
        from . import i18n, shell
        from .config import Config
        i18n.set_language(Config().language())
        shell.register() if args.register else shell.unregister()
        return 0

    from . import crashlog, updater
    try:
        updater.cleanup_applied()
    except Exception:
        pass
    crashlog.install()
    crashlog.cleanup()

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

    from .app import SpliceApp
    files = [os.path.abspath(f) for f in args.files if os.path.isfile(f)]
    return SpliceApp(sys.argv[:1], args.mode, files, quiet=args.tray).run()

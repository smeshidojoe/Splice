"""Строки интерфейса на двух языках (как в Spotty и Clipr).

`tr("ключ", имя=значение)` — строка на текущем языке с подстановкой {имя}.
Пропущенный перевод подменяется английским; неизвестный ключ возвращается как
есть — так забытая строка видна сразу, а не прячется.
"""

LANGUAGES = {"en": "English", "ru": "Русский"}
DEFAULT = "en"

_language = DEFAULT

STRINGS = {
    # --- меню проводника ------------------------------------------------------ #
    "shell.chop":        {"en": "Chop with Splice", "ru": "Нарезать в Splice"},
    "shell.merge":       {"en": "Merge with Splice", "ru": "Склеить в Splice"},

    # --- окно нарезки --------------------------------------------------------- #
    "chop.title":        {"en": "Splice — {name}", "ru": "Splice — {name}"},
    "chop.open":         {"en": "Choose a Video", "ru": "Выберите видео"},
    "chop.videos":       {"en": "Video", "ru": "Видео"},
    "chop.all_files":    {"en": "All files", "ru": "Все файлы"},
    "chop.in":           {"en": "In", "ru": "Начало"},
    "chop.out":          {"en": "Out", "ru": "Конец"},
    "chop.in_tip":       {"en": "Set start here (I)", "ru": "Начало здесь (I)"},
    "chop.out_tip":      {"en": "Set end here (O)", "ru": "Конец здесь (O)"},
    "chop.add":          {"en": "Add Range", "ru": "Добавить"},
    "chop.add_tip":      {"en": "Add the In–Out range to the list (Enter)",
                          "ru": "Добавить диапазон в список (Enter)"},
    "chop.play_tip":     {"en": "Play / Pause (Space)", "ru": "Воспроизвести / пауза (Пробел)"},
    "chop.prev_tip":     {"en": "Previous frame (←)", "ru": "Кадр назад (←)"},
    "chop.next_tip":     {"en": "Next frame (→)", "ru": "Кадр вперёд (→)"},
    "chop.ranges":       {"en": "RANGES", "ru": "ФРАГМЕНТЫ"},
    "chop.empty":        {"en": "Mark In (I) and Out (O),\nthen press Enter.\n\n"
                                "Add as many ranges as you need —\neach becomes its own file.",
                          "ru": "Поставьте начало (I) и конец (O)\nи нажмите Enter.\n\n"
                                "Фрагментов может быть сколько угодно —\nкаждый станет "
                                "отдельным файлом."},
    "chop.pending":      {"en": "Not added yet", "ru": "Ещё не добавлен"},
    "chop.remove_tip":   {"en": "Remove (Del)", "ru": "Убрать (Del)"},
    "chop.clear":        {"en": "Clear", "ru": "Очистить"},
    "chop.merge":        {"en": "Merge Chopped", "ru": "Merge Chopped"},
    "chop.merge_note":   {"en": "Glue all ranges into one file", "ru": "Склеить все фрагменты в один файл"},
    "chop.folder":       {"en": "Save to", "ru": "Сохранить в"},
    "chop.folder_pick":  {"en": "Choose a Folder", "ru": "Выберите папку"},
    "chop.export":       {"en": "Save", "ru": "Сохранить"},
    "chop.export_n":     {"en": "Save {n} Files", "ru": "Сохранить {n} шт."},
    "chop.export_merged": {"en": "Save Merged", "ru": "Сохранить склейку"},
    "chop.cancel":       {"en": "Cancel", "ru": "Отмена"},
    "chop.next_file":    {"en": "Next File ({n} left)", "ru": "Следующий файл (ещё {n})"},
    "chop.show":         {"en": "Show in Folder", "ru": "Показать в папке"},
    "chop.need_range":   {"en": "Set In and Out first — Out must come after In.",
                          "ru": "Сначала поставьте начало и конец — конец позже начала."},
    "chop.nothing":      {"en": "No ranges yet: mark In and Out.",
                          "ru": "Фрагментов нет: поставьте начало и конец."},
    "chop.cut":          {"en": "Cutting {i} of {n}…", "ru": "Режу {i} из {n}…"},
    "chop.merging":      {"en": "Merging…", "ru": "Склеиваю…"},
    "chop.saved":        {"en": "Saved: {names}", "ru": "Сохранено: {names}"},
    "chop.cancelled":    {"en": "Cancelled.", "ru": "Отменено."},
    "chop.failed":       {"en": "FFmpeg couldn't do it", "ru": "FFmpeg не справился"},
    "chop.hint":         {"en": "No re-encoding: a range starts at the nearest keyframe "
                                "before In.",
                          "ru": "Без перекодирования фрагмент начинается с ближайшего "
                                "ключевого кадра перед точкой начала."},
    "chop.busy_close":   {"en": "Saving is still running. Stop it and close?",
                          "ru": "Сохранение ещё идёт. Прервать и закрыть?"},
    "chop.player_error": {"en": "Preview unavailable: {msg}", "ru": "Просмотр недоступен: {msg}"},

    # --- склейка ------------------------------------------------------------- #
    "merge.title":       {"en": "Merge with Splice", "ru": "Склейка — Splice"},
    "merge.order":       {"en": "ORDER — drag to rearrange", "ru": "ПОРЯДОК — перетаскивайте"},
    "merge.add":         {"en": "Add Files…", "ru": "Добавить файлы…"},
    "merge.up_tip":      {"en": "Move up", "ru": "Выше"},
    "merge.down_tip":    {"en": "Move down", "ru": "Ниже"},
    "merge.remove_tip":  {"en": "Remove", "ru": "Убрать"},
    "merge.chop_tip":    {"en": "Open in the chopper", "ru": "Открыть в нарезке"},
    "merge.output":      {"en": "Output file", "ru": "Итоговый файл"},
    "merge.output_pick": {"en": "Save Merged File As", "ru": "Сохранить склейку как"},
    "merge.go":          {"en": "Merge without Re-encoding", "ru": "Склеить без перекодирования"},
    "merge.need_two":    {"en": "Add at least two files.", "ru": "Нужно минимум два файла."},
    "merge.mismatch":    {"en": "These files differ in codec, resolution or audio from the "
                                "first one and may not merge cleanly: {names}",
                          "ru": "У этих файлов другой кодек, разрешение или звук, чем у "
                                "первого, — склейка может не получиться: {names}"},
    "merge.exists":      {"en": "The file already exists. Replace it?\n\n{path}",
                          "ru": "Файл уже есть. Заменить?\n\n{path}"},
    "merge.self":        {"en": "The output can't be one of the input files.",
                          "ru": "Итоговый файл не может быть одним из исходных."},
    "merge.failed_hint": {"en": "Files with different codecs, resolution or frame rate can't "
                                "be merged without re-encoding.",
                          "ru": "Файлы с разными кодеками, разрешением или частотой кадров "
                                "без перекодирования не склеить."},

    # --- меню «ещё» ---------------------------------------------------------- #
    "more.tip":          {"en": "More", "ru": "Ещё"},
    "more.language":     {"en": "Language", "ru": "Язык"},
    "more.check":        {"en": "Check for Updates", "ru": "Проверить обновления"},
    "more.auto":         {"en": "Check Automatically", "ru": "Проверять автоматически"},
    "more.shortcuts":    {"en": "Keyboard Shortcuts", "ru": "Горячие клавиши"},
    "more.about":        {"en": "About Splice {version}", "ru": "О Splice {version}"},
    "more.crash":        {"en": "Open Crash Reports", "ru": "Открыть журнал падений"},
    "more.restart_lang": {"en": "The language changes the next time a window opens.",
                          "ru": "Язык сменится, когда откроется следующее окно."},
    "shortcuts.text":    {"en": "Space — play / pause\nI / O — set In / Out\n"
                                "Enter — add range\nDel — remove selected range\n"
                                "← / → — one frame\nShift + ← / → — one second\n"
                                "Ctrl + ← / → — ten seconds\nHome / End — start / end\n"
                                "[ / ] — jump to In / Out\nCtrl + S — save\nEsc — close",
                          "ru": "Пробел — воспроизведение / пауза\nI / O — начало / конец\n"
                                "Enter — добавить фрагмент\nDel — убрать выбранный\n"
                                "← / → — на кадр\nShift + ← / → — на секунду\n"
                                "Ctrl + ← / → — на десять секунд\nHome / End — в начало / "
                                "конец\n[ / ] — к началу / концу фрагмента\n"
                                "Ctrl + S — сохранить\nEsc — закрыть"},

    # --- обновления ---------------------------------------------------------- #
    "update.available":  {"en": "Splice {version} is available", "ru": "Доступна Splice {version}"},
    "update.downloading": {"en": "Downloading {version}…", "ru": "Скачиваю {version}…"},
    "update.ready":      {"en": "Splice {version} is downloaded", "ru": "Splice {version} скачана"},
    "update.current":    {"en": "You're up to date ({version}).",
                          "ru": "Установлена последняя версия ({version})."},
    "update.error":      {"en": "Couldn't check for updates — no connection to GitHub.",
                          "ru": "Не удалось проверить обновления — нет связи с GitHub."},
    "update.failed":     {"en": "Couldn't download the update.",
                          "ru": "Не удалось скачать обновление."},
    "update.install_failed": {"en": "Couldn't install the update — download it again.",
                              "ru": "Не удалось установить обновление — скачайте его заново."},
    "update.dev":        {"en": "{version} is available — installs only in the built app.",
                          "ru": "Доступна {version} — ставится только в собранной версии."},
    "update.busy":       {"en": "Wait until saving finishes, then restart.",
                          "ru": "Дождитесь конца сохранения — потом перезапуск."},
    "update.download":   {"en": "Download", "ru": "Скачать"},
    "update.restart":    {"en": "Restart", "ru": "Перезапустить"},
    "update.later":      {"en": "Later", "ru": "Позже"},

    # --- FFmpeg -------------------------------------------------------------- #
    "ffmpeg.missing_title": {"en": "FFmpeg Not Found", "ru": "FFmpeg не найден"},
    "ffmpeg.missing_text": {
        "en": "Splice cuts and merges video with FFmpeg.\n\n"
              "Download it now (about 80 MB, into the app folder in AppData)?",
        "ru": "Splice режет и склеивает видео с помощью FFmpeg.\n\n"
              "Скачать его сейчас (около 80 МБ, в папку программы в AppData)?"},
    "ffmpeg.downloading": {"en": "Downloading FFmpeg… {percent}%",
                           "ru": "Скачиваю FFmpeg… {percent}%"},
    "ffmpeg.failed":     {"en": "Couldn't download FFmpeg:\n{error}",
                          "ru": "Не удалось скачать FFmpeg:\n{error}"},
    # --- трей и настройки ---------------------------------------------------- #
    "tray.settings":     {"en": "Settings…", "ru": "Настройки…"},
    "tray.chop":         {"en": "Chop a Video…", "ru": "Нарезать видео…"},
    "tray.merge":        {"en": "Merge Videos…", "ru": "Склеить видео…"},
    "tray.update":       {"en": "Check for Updates", "ru": "Проверить обновления"},
    "tray.restart":      {"en": "Restart to Update ({version})",
                          "ru": "Перезапустить для обновления ({version})"},
    "tray.quit":         {"en": "Quit Splice", "ru": "Выйти из Splice"},
    "tray.hint":         {"en": "Splice is in the tray. Right-click a video in Explorer "
                                "to chop or merge it.",
                          "ru": "Splice в трее. Нажмите правой кнопкой на видео в проводнике, "
                                "чтобы нарезать или склеить его."},
    "settings.title":    {"en": "Splice Settings", "ru": "Настройки Splice"},
    "settings.menu":     {"en": "Explorer menu", "ru": "Меню проводника"},
    "settings.menu_note": {"en": "“Chop with Splice” and “Merge with Splice” on video files",
                           "ru": "«Нарезать в Splice» и «Склеить в Splice» у видеофайлов"},
    "settings.autostart": {"en": "Start with Windows", "ru": "Запускать вместе с Windows"},
    "settings.autostart_note": {"en": "Stays in the tray, opens instantly from Explorer",
                                "ru": "Сидит в трее, из проводника открывается мгновенно"},
    "settings.dev_only": {"en": "Only in the installed app", "ru": "Только в установленной версии"},
    "settings.updates":  {"en": "Check for updates automatically",
                          "ru": "Проверять обновления автоматически"},
    "settings.language": {"en": "Language", "ru": "Язык"},
    "settings.check":    {"en": "Check Now", "ru": "Проверить сейчас"},
    "settings.failed":   {"en": "Couldn't change the registry.", "ru": "Не удалось изменить реестр."},
}


def set_language(code):
    """Неизвестный код (например, из старых настроек) — английский."""
    global _language
    _language = code if code in LANGUAGES else DEFAULT


def language():
    return _language


def tr(key, **kwargs):
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_language) or entry.get("en") or key
    return text.format(**kwargs) if kwargs else text

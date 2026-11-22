<div align="center">

<img src="assets/app.png" width="112" alt="">

# Splice

**English** · [Русский](README.ru.md)

Cut a video into pieces — or cut and glue it back — straight from the Explorer
menu. No re-encoding: fast and lossless.

</div>

## Download

1. Open the [Releases](https://github.com/SmeshidoJoe/Splice/releases/latest) page.
2. Download `Splice-Setup-….exe` and run it. No administrator rights needed.
3. On first launch Splice offers to download FFmpeg (about 80 MB). Say yes.

Works on Windows 10 and 11.

## How to use

**Chop.** Right-click a video → **Chop with Splice** (on Windows 11: *Show more
options*). Mark **In** (`I`) and **Out** (`O`), press `Enter` to add the range.
Add as many ranges as you like, then **Save** — each range becomes
`name_part1`, `name_part2`… next to the source. Drag a range's edges on the
timeline to adjust it.

**Merge Chopped.** Turn it on and all ranges are cut and glued into one
`name_chopped` file — still without re-encoding.

**Merge.** Select several videos → **Merge with Splice**. Reorder them by
dragging and press **Merge**. Files must share codec, resolution and audio
format; Splice warns when they don't.

Without re-encoding a cut can only start on a keyframe, so a range starts at
the nearest keyframe before In.

| Key | Action |
| --- | --- |
| `Space` | play / pause |
| `I` / `O` | set In / Out |
| `Enter` | add range |
| `Del` | remove selected range |
| `←` `→` | one frame (`Shift` — 1 s, `Ctrl` — 10 s) |
| `[` `]` | jump to In / Out |
| `Ctrl + S` | save |

## Build

```
pip install -r requirements.txt pyinstaller
python tools_gen_assets.py
pyinstaller --clean --noconfirm Splice.spec
iscc splice_setup.iss
```

From source: `python main.py file.mp4`, `python main.py --register` adds the
Explorer menu items for the source checkout (`--unregister` removes them).

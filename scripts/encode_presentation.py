"""Encode captured UI frames and verify the presentation deliverables."""
import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/presentation"
FRAMES = ROOT / "storage/presentation/frames"
gif = OUT / "11_시연.gif"
subprocess.run([
    imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
    "-framerate", "10", "-i", str(FRAMES / "%03d.png"), "-frames:v", "120",
    "-filter_complex",
    "[0:v]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
    "-loop", "0", str(gif),
], check=True)
rows = []
pngs = sorted(OUT.glob("*.png"))
assert len(pngs) == 10
for p in [*pngs, gif]:
    with Image.open(p) as im:
        assert im.size == (1920, 1080), (p.name, im.size)
        duration = 0
        if p == gif:
            assert im.is_animated
            for i in range(im.n_frames):
                im.seek(i)
                duration += im.info.get("duration", 0)
            assert 10000 <= duration <= 15000, duration
        rows.append({
            "file": p.name, "width": im.width, "height": im.height,
            "bytes": p.stat().st_size, "duration_ms": duration or None,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        })
(OUT / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Verified {len(pngs)} PNGs at 1920x1080; GIF {duration / 1000:.2f}s, {gif.stat().st_size:,} bytes.")

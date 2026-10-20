"""Encode captured UI frames and verify the presentation deliverables."""
import hashlib
import json
import subprocess
import html
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/presentation"
FRAMES = ROOT / "storage/presentation-final/frames"
gif = OUT / "13_시연.gif"
subprocess.run([
    imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
    "-framerate", "10", "-i", str(FRAMES / "%03d.png"), "-frames:v", "120",
    "-filter_complex",
    "[0:v]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
    "-loop", "0", str(gif),
], check=True)
rows = []
pngs = sorted(OUT.glob("*.png"))
assert len(pngs) == 12
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
cards = "".join(
    f'<a class="card" href="{html.escape(row["file"])}"><img loading="lazy" src="{html.escape(row["file"])}" '
    f'alt="{html.escape(Path(row["file"]).stem)}"><h2>{html.escape(Path(row["file"]).stem.replace("_", " · "))}</h2>'
    f'<p>1920 × 1080{" · 12초" if row["duration_ms"] else " · PNG"}</p></a>'
    for row in rows
)
(OUT / "index.html").write_text(
    '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>PRISM · 최종 발표 결과</title><style>'
    'body{margin:0;background:#0b1722;color:#e7f3f8;font:17px "Malgun Gothic",sans-serif;padding:40px}'
    'header,main{max-width:1600px;margin:auto}h1{font-size:36px}header p{color:#9ab8c8;line-height:1.7}'
    'main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin-top:32px}'
    'a{color:#75d4df}.card{display:block;background:#102431;border:1px solid #294351;border-radius:14px;overflow:hidden;text-decoration:none}'
    '.card img{width:100%;aspect-ratio:16/9;object-fit:contain;display:block}.card h2{font-size:21px;margin:20px}.card p{margin:20px;color:#93adbb}'
    '@media(max-width:800px){main{grid-template-columns:1fr}body{padding:20px}}</style>'
    '<header><h1>PRISM · 최종 발표 결과</h1><p>물류 창고 · 입출고 구역 / PNG 12장 + 12초 GIF / 누락 없음</p>'
    '<p><a href="README.md">캡처 기준·출처</a> · <a href="../placement-correction/index.html">원본·±3° 보정 비교</a> · '
    '<a href="_old/index.html">이전 발표 자료</a></p>'
    '<p>GIF는 완료된 메시 생성 결과와 실제 배치 UI를 연결한 편집본이며 추론 대기 시간을 생략했습니다.</p></header><main>'
    + cards + '</main></html>', encoding="utf-8"
)

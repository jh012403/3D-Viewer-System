"""Edit actual browser footage into four offline fallback presentations."""
import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'storage/twin_recordings'
OUT = ROOT / 'docs/twin-videos'
OUT.mkdir(exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

def run(args):
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', *args], check=True)

def clip(source, destination, start=0, duration=None, speed=1, caption=False):
    args = ['-ss', str(start)]
    if duration is not None:
        args += ['-t', str(duration)]
    args += ['-i', str(source)]
    filters = f'setpts=(PTS-STARTPTS)/{speed},scale=1800:1100:force_original_aspect_ratio=decrease,pad=1800:1100:(ow-iw)/2:(oh-ih)/2,fps=30'
    if caption:
        args += ['-i', str(RAW/'generation-caption.png'), '-filter_complex', f'[0:v]{filters}[base];[base][1:v]overlay=0:0', '-shortest']
    else:
        args += ['-vf', filters]
    run([*args, '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(destination)])

def concat(parts, target, name):
    listing = RAW/f'{name}.txt'
    listing.write_text(''.join("file '"+p.as_posix()+"'\n" for p in parts), encoding='utf-8')
    run(['-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(target)])

source = RAW/'real-mesh-validation.webm'
_, seconds = imageio_ffmpeg.count_frames_and_secs(str(source))
timing = json.loads((ROOT/'docs/twin-real-mesh-run.json').read_text(encoding='utf-8'))
selection = timing['selection_video_seconds']
caption = Image.new('RGB', (1800, 54), '#0b1c29')
ImageDraw.Draw(caption).text((26, 10), '실제 사진 → SAM3 선택 → FastVLM 이해 → TRELLIS 생성 · 대기 구간 편집 · 동일 생성 기록을 4개 시연에 사용', font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 21), fill='#b6f1f7')
caption.save(RAW/'generation-caption.png')
parts=[]
# Retain actual upload, selection, processing and successful result frames.
for i,(start,length,speed) in enumerate([(0,5,1),(max(0,selection-3),9,1),(min(seconds-18,selection+12),12,3),(max(0,seconds-16),6,1)]):
    target=RAW/f'gen-{i}.mp4';clip(source,target,start,length,speed,True);parts.append(target)
clip(RAW/'mesh-download.webm',RAW/'mesh-download.mp4',caption=True)
parts.append(RAW/'mesh-download.mp4')
concat(parts,RAW/'generation-edited.mp4','generation-concat')

rows=[]
for scene in ['twin-logistics','twin-laboratory','twin-workbench','twin-factory']:
    clips=[]
    for phase in ['intro','outro','report']:
        target=RAW/f'{scene}-{phase}.mp4';clip(RAW/f'{scene}-{phase}.webm',target);clips.append(target)
    video=OUT/f'{scene}.mp4'
    concat([clips[0],RAW/'generation-edited.mp4',clips[1],clips[2]],video,scene+'-concat')
    frames,duration=imageio_ffmpeg.count_frames_and_secs(str(video))
    rows.append({'scene':scene,'video':video.name,'seconds':duration,'frames':frames,'bytes':video.stat().st_size,'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'generation_job':timing['job'],'editing':'One actual generation reused in four videos; waiting intervals cut/accelerated.'})
    print(scene,round(duration,2),'seconds',flush=True)
(OUT/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

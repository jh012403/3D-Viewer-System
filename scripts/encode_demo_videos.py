"""Encode real browser recordings as offline H.264 fallback videos."""
import hashlib,json,subprocess
from pathlib import Path
import imageio_ffmpeg
root=Path(__file__).resolve().parents[1];out=root/'docs/demo-videos';out.mkdir(exist_ok=True)
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();rows=[]
for scene in ['sunroom','ceramics','d4f646fcc79650d6','hall']:
    source=root/'storage/demo_recordings'/f'{scene}.webm';target=out/f'{scene}.mp4'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(source),'-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-r','30','-movflags','+faststart','-an',str(target)],check=True)
    frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(target))
    rows.append({'scene':scene,'video':target.relative_to(root).as_posix(),'seconds':seconds,'frames':frames,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    print(scene,seconds,'seconds',target.stat().st_size,'bytes',flush=True)
(out/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

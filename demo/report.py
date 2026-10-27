"""Read actual OBS statistics and media metadata; never infer smoothness from FPS alone."""
import argparse
import json
from pathlib import Path
import imageio_ffmpeg

def summarize(path):
    path=Path(path);r=json.loads(path.read_text(encoding='utf-8'))
    result={'status':r['status'],'mode':r['mode'],'scenario_seconds':r.get('scenario_seconds'),
            'hardware_webgl':r.get('hardware_webgl'),'monitor':r.get('monitor'),
            'rotation_degrees':r.get('rotation_degrees'),'before':r.get('before'),'after':r.get('after'),
            'failure':r.get('failure'),'recording_error':r.get('recording_error')}
    if r.get('mp4'):
        frames=imageio_ffmpeg.read_frames(r['mp4']);meta=next(frames);frames.close()
        result['video']={'path':r['mp4'],**meta}
        source=imageio_ffmpeg.read_frames(r['mkv']);source_meta=next(source);source.close()
        result['mkv_duration_seconds']=source_meta.get('duration')
        result['remux_duration_difference_seconds']=abs(meta.get('duration',0)-source_meta.get('duration',0))
    delta=r.get('obs_delta',{})
    for prefix in ('render','output'):
        lost=delta.get(prefix+'_skipped_frames');total=delta.get(prefix+'_total_frames')
        if lost is not None:
            result[prefix+'_lag']={'skipped':lost,'frames':total,'percent':round(100*lost/total,4) if total and total>0 else None}
    samples=r.get('obs_samples',[]);slow=[]
    for a,b in zip(samples,samples[1:]):
        skipped=b.get('render_skipped_frames',0)-a.get('render_skipped_frames',0)
        if skipped>0:slow.append({'from_seconds':a['seconds'],'to_seconds':b['seconds'],'step':b['step'],'render_skipped_frames':skipped,'average_frame_render_ms':b.get('average_frame_render_time')})
    result['render_lag_intervals']=slow
    result['interpretation']='OBS render lag measures frames missed by composition; output lag measures encoder/output loss. Coincidence with inference is evidence of contention, not proof of a unique cause. A 60fps container alone does not prove smooth motion.'
    (path.parent/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_json');summarize(p.parse_args().run_json)

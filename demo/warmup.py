"""Real sequential model jobs. No fixture replacement and no old-cache writes."""
import json
import time
import uuid
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]

def request(method, url, **kw):
    r = requests.request(method, url, timeout=600, **kw)
    r.raise_for_status()
    return r.json()

def fresh_background(path, folder):
    # Trailing JPEG bytes preserve the photograph while assigning a new cache key.
    # Never regenerate or rename an existing curated scene cache.
    if path.suffix.lower() not in ('.jpg', '.jpeg'):
        raise ValueError('Use a JPEG background for isolated live-generation runs.')
    out = folder / 'warehouse-live.jpg'
    out.write_bytes(path.read_bytes() + b'\nPRISM-DEMO-' + uuid.uuid4().hex.encode())
    return out

def poll(url, success, timeout=2400):
    started = time.monotonic()
    last = None
    while time.monotonic() - started < timeout:
        job = request('GET', url)
        marker = (job.get('status'), job.get('stage'), job.get('message'))
        if marker != last:
            print(marker, flush=True)
            last = marker
        if job.get('status') == 'failed':
            raise RuntimeError(job.get('error') or job.get('message'))
        if job.get('status') == success:
            return job
        time.sleep(3)
    raise TimeoutError(url)

def run(config, folder):
    folder.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    photo = fresh_background(ROOT / config['background_image'], folder)
    with photo.open('rb') as f:
        job = request('POST', config['base_url']+'/scene-api/build', files={'file': (photo.name, f, 'image/jpeg')})
    scene = poll(config['base_url']+'/scene-api/jobs/'+job['id'], 'ready')
    scene_seconds = time.monotonic()-start
    with (ROOT/config['object_image']).open('rb') as f:
        uploaded = request('POST', config['base_url']+'/api/upload', data={'type':'image_to_3d'}, files={'file':('object.jpg',f,'image/jpeg')})
    jid=uploaded['job_id']
    base=config['base_url']+'/api/jobs/'+jid
    mask=request('POST',base+'/segmentation-text-prompt',json={'prompt':config['object_prompt'],'confidence_threshold':.5,'merge_mode':'best'})
    request('POST',config['base_url']+'/api/jobs',json={'job_id':jid,'type':'image_to_3d','options':{'sam2_candidate_id':mask['selected_candidate_id']}})
    mesh=poll(base,'completed')
    result={'scene':scene,'mesh_job':jid,'mesh_status':mesh['status'],'scene_seconds':scene_seconds,'total_seconds':time.monotonic()-start,'note':'Actual one-pass inference. Per-job subprocess/model loading remains; warmup does not keep all models resident.'}
    (folder/'warmup.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    config=json.loads((Path(__file__).with_name('config.json')).read_text(encoding='utf-8'))
    run(config,ROOT/'storage/obs-demo/warmup')

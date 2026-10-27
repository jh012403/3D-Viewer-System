"""Copy real offline outputs into an isolated, reproducible demo package."""
import hashlib
import json
import shutil
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'demo_assets'
JOB='job_000006'

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def copy_tree(source,target):
    target.mkdir(parents=True,exist_ok=True)
    for path in source.rglob('*'):
        if not path.is_file():continue
        if path.name in ('object_raw.glb','fastvlm_input.png'):continue
        out=target/path.relative_to(source);out.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,out)

def prepare():
    scene=ROOT/'storage/scene_cache/twin-logistics'
    copy_tree(scene,ASSETS/'public/scene-cache/twin-logistics')
    for relative in (f'storage/outputs/{JOB}',f'storage/previews/{JOB}',f'storage/uploads/{JOB}',f'storage/temp/{JOB}/sam2_candidates/candidates'):
        copy_tree(ROOT/relative,ASSETS/'public'/relative)
    response_dir=ASSETS/'responses';response_dir.mkdir(parents=True,exist_ok=True)
    for name,url in [('job',f'http://127.0.0.1:8000/api/jobs/{JOB}'),('result',f'http://127.0.0.1:8000/api/jobs/{JOB}/result'),('exports',f'http://127.0.0.1:8000/api/jobs/{JOB}/exports'),('policies','http://127.0.0.1:8001/scene-api/policies')]:
        response=requests.get(url,timeout=30);response.raise_for_status();write(response_dir/(name+'.json'),response.json())
    seg=json.loads((ROOT/f'storage/temp/{JOB}/sam2_candidates/sam3_text_prompt_response.json').read_text(encoding='utf-8'))
    write(response_dir/'seg.json',seg)
    response=requests.post(f'http://127.0.0.1:8001/scene-api/generated-assets/{JOB}',timeout=60)
    response.raise_for_status();asset=response.json()
    source=ROOT/'storage/scene_assets'/Path(asset['url']).name
    destination=ASSETS/'public/scene-api/asset-files/prepared-box.glb'
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    asset.update(id='prepared-box',url='/scene-api/asset-files/prepared-box.glb',name='반입 상자')
    write(response_dir/'import.json',asset)
    graph=json.loads((scene/'graph.json').read_text(encoding='utf-8'))
    graph['demo_provenance']='Prepared photo-guided warehouse graph; runtime inference is bypassed only in DEMO_MODE=1.'
    write(ASSETS/'public/scene-cache/twin-logistics/graph.json',graph)
    write(ASSETS/'graph-initial.json',graph)
    write(ASSETS/'asset-list-initial.json',graph['nodes'])
    write(ASSETS/'provenance.json',{
        'mode':'prepared-results demonstration, not live inference',
        'background':'storage/scene_cache/twin-logistics/source.jpg',
        'background_models':['apple/ml-sharp','Depth Anything V2 metric'],
        'graph':'Existing photo-guided curated graph copied without modifying original cache',
        'object_source':f'storage/uploads/{JOB}/input_image.jpg',
        'object_models':['SAM3 text mask','FastVLM metadata','TRELLIS.2 GLB'],
        'source_job':JOB,
        'fixed_inputs':'One warehouse scene; one fixed cardboard-box intake photo. Different demo clicks/prompts return the same prepared mask.',
        'timing':'Scene replay 8 seconds, segmentation replay 4 seconds, mesh replay 8 seconds; these are presentation delays, not measured inference times.'})
    manifest=[]
    for path in ASSETS.rglob('*'):
        if path.is_file() and path.name!='manifest.json':
            manifest.append({'path':path.relative_to(ASSETS).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    write(ASSETS/'manifest.json',manifest)
    print('Prepared',len(manifest),'files',sum(x['bytes'] for x in manifest),'bytes')

if __name__=='__main__':prepare()

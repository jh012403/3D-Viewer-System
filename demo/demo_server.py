"""Opt-in prepared API. Production pipeline modules are never imported or changed."""
import asyncio
import copy
import json
import os
import time
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

if os.environ.get('DEMO_MODE')!='1':
    raise RuntimeError('Prepared API is disabled. Set DEMO_MODE=1 explicitly; use normal services otherwise.')
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'demo_assets'
app=FastAPI(title='PRISM prepared demo API')
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5174','http://localhost:5174'],allow_methods=['*'],allow_headers=['*'])
# The existing UI hides the entire generated-assets picker when initially empty.
# Expose the genuinely prepared GLB from startup, just as the normal library does.
jobs={'demo_prepared_box':{'started':time.monotonic()-9}};scene_jobs={}

def fixture(name):return json.loads((ASSETS/'responses'/f'{name}.json').read_text(encoding='utf-8'))
def ensure(jid):
    if jid not in jobs:raise HTTPException(404,'Unknown demo job')
def job_record(jid):
    ensure(jid);record=fixture('job');record['job_id']=jid
    started=jobs[jid].get('started')
    elapsed=time.monotonic()-started if started is not None else 0
    if elapsed<8:
        record.update(status='running',result=None,stage=['image_preprocess_running','asset_metadata_running','object_mesh_running','material_package_running'][max(0,min(3,int(elapsed/2)))])
    if started is None:record['status']='queued'
    return record

@app.middleware('http')
async def provenance_header(request,call_next):
    response=await call_next(request);response.headers['X-PRISM-Demo-Mode']='prepared-results'
    return response

@app.get('/scene-api/health')
def health():return {'status':'ok','demo_mode':True,'cache_count':1}

@app.get('/scene-api/scenes')
def scenes():
    scene=json.loads((ASSETS/'public/scene-cache/twin-logistics/scene.json').read_text(encoding='utf-8'))
    return [{**scene,'url':'/scene-cache/twin-logistics/scene.json'}]

@app.post('/scene-api/build')
async def build(request:Request):
    # Accept the real upload contract, intentionally ignore content in fixed demo.
    await request.body();jid='demo-scene-'+uuid.uuid4().hex[:10];scene_jobs[jid]=time.monotonic()
    return {'id':jid}

@app.get('/scene-api/jobs/{jid}')
def scene_status(jid:str):
    if jid not in scene_jobs:raise HTTPException(404,'Unknown scene job')
    elapsed=time.monotonic()-scene_jobs[jid]
    labels=['현장 3D 복원','실측 스케일 정렬','자산 인식','자산 등록','관계 분석']
    stage=min(4,int(elapsed/1.6))
    return {'status':'ready' if elapsed>=8 else 'running','stage':stage,'message':labels[stage],'url':'/scene-cache/twin-logistics/scene.json'}

@app.post('/api/upload')
async def upload(request:Request):
    await request.body();jid='demo_'+uuid.uuid4().hex[:10];jobs[jid]={}
    return {'job_id':jid,'type':'image_to_3d','input_file':fixture('job')['input_file'],'filename':'box-three-quarter.jpg'}

@app.api_route('/api/jobs/{jid}/segmentation-candidates',methods=['GET'])
@app.api_route('/api/jobs/{jid}/segmentation-text-prompt',methods=['POST'])
@app.api_route('/api/jobs/{jid}/segmentation-prompt',methods=['POST'])
@app.api_route('/api/jobs/{jid}/segmentation-candidates/{candidate_id}/enhance',methods=['POST'])
async def segmentation(jid:str,candidate_id:str=''):
    ensure(jid);await asyncio.sleep(4)
    response=fixture('seg');response['job_id']=jid
    return response

@app.post('/api/jobs')
async def create_job(request:Request):
    data=await request.json();jid=data['job_id'];ensure(jid);jobs[jid]['started']=time.monotonic()
    return job_record(jid)

@app.get('/api/jobs/{jid}')
def status(jid:str):return job_record(jid)

@app.get('/api/jobs/{jid}/result')
def result(jid:str):
    record=job_record(jid)
    if record['status']!='completed':raise HTTPException(409,'Prepared result not ready')
    response=fixture('result');response.update(job_id=jid,job=record)
    return response

@app.get('/api/jobs/{jid}/exports')
def exports(jid:str):
    ensure(jid);data=fixture('exports');data['job_id']=jid;return data

@app.get('/api/demo-assets/trellis')
def examples():return {'source':'prepared-demo','count':0,'items':[]}

@app.get('/scene-api/generated-assets')
def generated():
    source=fixture('import')
    return [{'job_id':jid,'name':source['name'],'category':source['category'],'specification':source['specification']} for jid in reversed(jobs) if job_record(jid)['status']=='completed']

@app.post('/scene-api/generated-assets/{jid}')
def import_asset(jid:str):
    if job_record(jid)['status']!='completed':raise HTTPException(409,'Not ready')
    response=fixture('import');response['source_job']=jid;return response

@app.get('/scene-api/policies')
def policies():return fixture('policies')

@app.get('/demo-api/provenance')
def provenance():return json.loads((ASSETS/'provenance.json').read_text(encoding='utf-8'))

@app.get('/demo-api/artifacts/{name}')
def artifact(name:str):
    allowed={'graph-initial.json','graph-updated.json','asset-list-initial.json','asset-list-updated.json','composite-result.png'}
    if name not in allowed or not (ASSETS/name).is_file():raise HTTPException(404,'Prepared artifact not available')
    return FileResponse(ASSETS/name)

# All result URLs retain their production shape and resolve to copied files.
app.mount('/storage',StaticFiles(directory=ASSETS/'public/storage'),name='storage')
app.mount('/scene-cache',StaticFiles(directory=ASSETS/'public/scene-cache'),name='scene-cache')
app.mount('/scene-api/asset-files',StaticFiles(directory=ASSETS/'public/scene-api/asset-files'),name='asset-files')

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8020)

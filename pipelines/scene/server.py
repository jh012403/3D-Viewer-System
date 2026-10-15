"""Loopback scene service, independent of the existing mesh service."""
from pathlib import Path
import json, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from PIL import Image
from .build import CACHE, ROOT, build

CACHE.mkdir(parents=True,exist_ok=True)
uploads=ROOT/"storage/scene_uploads"; uploads.mkdir(parents=True,exist_ok=True)
app=FastAPI(title="Scene workspace")
app.mount("/scene-cache",StaticFiles(directory=CACHE),name="scene-cache")
jobs={}; executor=ThreadPoolExecutor(max_workers=1)
@app.get("/scene-api/health")
def health():
    return {"status":"ok","cache_count":len(list(CACHE.glob("*/scene.json")))}
@app.get("/scene-api/scenes")
def scenes():
    return [dict(json.loads(p.read_text(encoding="utf-8")),url=f"/scene-cache/{p.parent.name}/scene.json") for p in CACHE.glob("*/scene.json")]
@app.post("/scene-api/build")
async def create(file:UploadFile):
    data=await file.read(25*1024*1024+1)
    if len(data)>25*1024*1024: raise HTTPException(413,"Image exceeds 25 MB")
    if sum(j["status"] in ("queued","running") for j in jobs.values())>=3:
        raise HTTPException(429,"Scene queue is full")
    jid=uuid.uuid4().hex; path=uploads/f"{jid}.jpg"
    import io
    try:
        image=Image.open(io.BytesIO(data))
        if image.width*image.height>30_000_000: raise ValueError("Image exceeds 30 MP")
        # Preserve uploaded bytes and EXIF for SHARP focal length estimation.
        image.verify()
    except Exception as exc: raise HTTPException(400,"Invalid or oversized photograph") from exc
    path.write_bytes(data); jobs[jid]={"status":"queued","message":"Queued"}
    title=Path(file.filename or "Uploaded photograph").stem[:80]
    def run():
        jobs[jid]["status"]="running"
        try:
            out=build(path,progress=lambda msg:jobs[jid].update(message=msg))
            manifest=json.loads((out/"scene.json").read_text(encoding="utf-8"))
            manifest["title"]=title
            (out/"scene.json").write_text(json.dumps(manifest,ensure_ascii=False),encoding="utf-8")
            jobs[jid].update(message="Qwen names and SAM3 masks")
            from .graph import run as graph_run
            graph_run([{"id":out.name,"image":str(out/"source.jpg"),"out":str(out),"depth_domain":"hypersim"}])
            jobs[jid].update(status="ready",message="Scene and graph ready",url=f"/scene-cache/{out.name}/scene.json")
        except Exception as exc:
            jobs[jid].update(status="failed",message=str(exc))
    executor.submit(run)
    return {"id":jid}
@app.get("/scene-api/jobs/{jid}")
def job(jid:str):
    if jid not in jobs: raise HTTPException(404,"Unknown job")
    return jobs[jid]

# GLB assets are copied and normalized into NEW storage only.
asset_dir=ROOT/"storage/scene_assets"; asset_dir.mkdir(parents=True,exist_ok=True)
app.mount("/scene-api/asset-files",StaticFiles(directory=asset_dir),name="scene-assets")

def generated_asset(job_id):
    import re,struct
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',job_id):raise HTTPException(400,'Invalid job id')
    directory=(ROOT/'storage/outputs'/job_id).resolve()
    if not directory.is_relative_to((ROOT/'storage/outputs').resolve()):raise HTTPException(400,'Invalid output path')
    path=directory/'object_mesh.glb'
    if not path.is_file():raise HTTPException(404,'Generated GLB is not ready')
    with path.open('rb') as stream:header=stream.read(12)
    if len(header)!=12 or header[:4]!=b'glTF' or struct.unpack('<I',header[8:12])[0]!=path.stat().st_size:
        raise HTTPException(409,'GLB is still being written')
    meta={}
    try:meta=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    return path,{'job_id':job_id,'name':meta.get('asset_name') or meta.get('specific_type') or '생성 물체 '+job_id[:8],
        'category':meta.get('normalized_category_id') or meta.get('object_category') or 'unknown'}

@app.get('/scene-api/generated-assets')
def generated_assets():
    result=[]
    for path in sorted((ROOT/'storage/outputs').glob('*/object_mesh.glb'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:result.append(generated_asset(path.parent.name)[1])
        except HTTPException:continue
    return result

@app.post('/scene-api/generated-assets/{job_id}')
async def import_generated_asset(job_id:str):
    import io
    path,meta=generated_asset(job_id)
    if path.stat().st_size>100*1024*1024:raise HTTPException(413,'GLB exceeds 100 MB')
    result=await add_asset(UploadFile(file=io.BytesIO(path.read_bytes()),filename=meta['name']+'.glb'),meta['category'])
    return {**result,'source_job':job_id}

@app.get("/scene-api/policies")
def policies():
    from pipelines.image_to_3d.semantic_metadata import POLICIES
    return [p.to_json() for p in POLICIES.values()]
@app.post("/scene-api/assets")
async def add_asset(file:UploadFile, category:str="auto"):
    import io, trimesh
    from pipelines.image_to_3d.mesh_cleanup import _normalize_scene_transform
    from pipelines.image_to_3d.semantic_metadata import normalize_category
    if category=='auto':category=normalize_category(Path(file.filename or '').stem)['normalized_category_id']
    data=await file.read(100*1024*1024+1)
    if len(data)>100*1024*1024:raise HTTPException(413,"GLB exceeds 100 MB")
    if data[:4]!=b"glTF":raise HTTPException(400,"Only binary GLB is supported")
    try:
        scene=trimesh.load(io.BytesIO(data),file_type="glb",force="scene")
        normalization=_normalize_scene_transform(scene,category)
        aid=uuid.uuid4().hex
        # Preserve original glTF UVs, materials and extensions byte-for-byte.
        # The viewer applies the existing policy's transform to a parent group.
        (asset_dir/f"{aid}.glb").write_bytes(data)
    except Exception as exc:raise HTTPException(400,f"Cannot prepare GLB: {exc}") from exc
    return {"id":aid,"url":f"/scene-api/asset-files/{aid}.glb","name":Path(file.filename or "object.glb").stem,
        "category":category,"normalization":normalization,"normalization_applied":False}


@app.post("/scene-api/graphs/{scene_id}")
def generate_graph(scene_id:str):
    import re
    if not re.fullmatch(r"[a-zA-Z0-9_-]+",scene_id):raise HTTPException(400,"Invalid scene id")
    out=CACHE/scene_id
    if not (out/"scene.json").exists():raise HTTPException(404,"Unknown scene")
    if any(j["status"] in ("queued","running") for j in jobs.values()):raise HTTPException(409,"GPU worker is busy")
    jid=uuid.uuid4().hex;jobs[jid]={"status":"queued","message":"Graph queued"}
    def run_graph():
        jobs[jid].update(status="running",message="Qwen names and SAM3 masks")
        try:
            from .graph import run
            run([{"id":scene_id,"image":str(out/"source.jpg"),"out":str(out),"depth_domain":"hypersim"}])
            jobs[jid].update(status="ready",message="Graph ready")
        except Exception as exc:jobs[jid].update(status="failed",message=str(exc))
    executor.submit(run_graph)
    return {"id":jid}


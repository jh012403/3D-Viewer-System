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
    def run():
        jobs[jid]["status"]="running"
        try:
            out=build(path,progress=lambda msg:jobs[jid].update(message=msg))
            jobs[jid].update(status="ready",url=f"/scene-cache/{out.name}/scene.json")
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
@app.get("/scene-api/policies")
def policies():
    from pipelines.image_to_3d.semantic_metadata import POLICIES
    return [p.to_json() for p in POLICIES.values()]
@app.post("/scene-api/assets")
async def add_asset(file:UploadFile, category:str="small_prop"):
    import io, trimesh
    from pipelines.image_to_3d.mesh_cleanup import _normalize_scene_transform
    data=await file.read(100*1024*1024+1)
    if len(data)>100*1024*1024:raise HTTPException(413,"GLB exceeds 100 MB")
    if data[:4]!=b"glTF":raise HTTPException(400,"Only binary GLB is supported")
    try:
        scene=trimesh.load(io.BytesIO(data),file_type="glb",force="scene")
        # Bake scene node transforms before reusing the existing normalization.
        scene=trimesh.Scene(scene.to_geometry())
        normalization=_normalize_scene_transform(scene,category)
        aid=uuid.uuid4().hex
        scene.export(asset_dir/f"{aid}.glb")
    except Exception as exc:raise HTTPException(400,f"Cannot prepare GLB: {exc}") from exc
    return {"id":aid,"url":f"/scene-api/asset-files/{aid}.glb","name":Path(file.filename or "object.glb").stem,
        "category":category,"normalization":normalization}


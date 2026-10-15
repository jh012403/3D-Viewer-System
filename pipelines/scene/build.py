"""Independent SHARP + metric DAV2 scene cache builder; never mutates source assets."""
from __future__ import annotations
import argparse, gc, hashlib, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "storage" / "scene_cache"

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")

def align_scale(points, opacities, depth, focal):
    """Robust foreground z-buffer ratio. Positive scale only; no camera translation."""
    h, w = depth.shape
    xyz = points.reshape(-1, 3)
    good = np.isfinite(xyz).all(1) & (xyz[:, 2] > .1) & (opacities.reshape(-1) > .5)
    xyz = xyz[good]
    u = np.rint(focal * xyz[:, 0] / xyz[:, 2] + w / 2).astype(int)
    v = np.rint(focal * xyz[:, 1] / xyz[:, 2] + h / 2).astype(int)
    valid = (u >= 0) & (u < w) & (v >= 0) & (v < h)
    zbuf = np.full(h * w, np.inf, dtype=np.float32)
    np.minimum.at(zbuf, v[valid] * w + u[valid], xyz[valid, 2])
    zbuf = zbuf.reshape(h, w)
    valid = np.isfinite(zbuf) & np.isfinite(depth) & (depth > .1) & (depth < 19.5)
    # Avoid silhouette boundaries where two monocular models disagree most.
    import cv2
    edges = cv2.morphologyEx(depth.astype(np.float32), cv2.MORPH_GRADIENT, np.ones((5,5), np.uint8))
    valid &= edges < np.maximum(.1, depth * .05)
    ratios = depth[valid] / zbuf[valid]
    if len(ratios) < 500:
        raise ValueError("Insufficient reliable pixels for metric scale alignment")
    scale = float(np.median(ratios))
    if not .05 < scale < 20:
        raise ValueError("Metric scale outside supported range")
    residual = np.abs(zbuf[valid] * scale - depth[valid]) / depth[valid]
    return scale, {"method":"foreground-zbuffer-median-ratio", "samples":int(len(ratios)),
        "scale":scale, "median_relative_residual":float(np.median(residual)),
        "p90_relative_residual":float(np.percentile(residual,90)), "metric_ground_truth":False}

def surface(depth, focal, stride=5):
    h,w=depth.shape
    ys=np.arange(0,h,stride); xs=np.arange(0,w,stride)
    xx,yy=np.meshgrid(xs,ys); z=depth[yy,xx]
    p=np.stack(((xx-w/2)*z/focal, -(yy-h/2)*z/focal, -z),-1).reshape(-1,3)
    n=len(xs); ids=np.arange(len(p)).reshape(len(ys),n)
    a=ids[:-1,:-1].ravel(); b=ids[:-1,1:].ravel()
    c=ids[1:,:-1].ravel(); d=ids[1:,1:].ravel()
    faces=np.concatenate((np.stack((a,c,b),1),np.stack((b,c,d),1)))
    zs=-p[faces,2]
    ok=np.isfinite(zs).all(1)&(zs.min(1)>.1)&((zs.max(1)-zs.min(1))<np.maximum(.08,zs.mean(1)*.035))
    return {"positions":p.astype(np.float32).ravel().tolist(),"indices":faces[ok].ravel().tolist(),
        "coordinate_system":"three-camera-x-right-y-up-z-back", "units":"meters"}

def build(image_path, output=None, progress=print):
    import cv2, torch
    from PIL import Image
    from sharp.models import PredictorParams, create_predictor
    from sharp.utils.io import load_rgb
    from sharp.utils.gaussians import unproject_gaussians, save_ply
    image_path=Path(image_path)
    key=hashlib.sha256(image_path.read_bytes()+b"scene-v1-hypersim-vitl").hexdigest()[:16]
    out=Path(output) if output else CACHE/key
    if (out/"scene.json").exists():
        return out
    out.mkdir(parents=True,exist_ok=True)
    progress("Loading source photograph")
    image,_,focal=load_rgb(image_path)
    h,w=image.shape[:2]
    # Cap cache image resolution, preserving calibrated intrinsics and aspect.
    ratio=min(1,1280/max(h,w))
    if ratio<1:
        image=cv2.resize(image,(round(w*ratio),round(h*ratio)))
        focal*=ratio
    h,w=image.shape[:2]
    Image.fromarray(image).save(out/"source.jpg",quality=95)
    device="cuda" if torch.cuda.is_available() else "cpu"
    progress("SHARP Gaussian prediction")
    predictor=create_predictor(PredictorParams())
    predictor.load_state_dict(torch.load(ROOT/".runtime/weights/sharp_2572gikvuh.pt",map_location="cpu",weights_only=True))
    predictor.eval().to(device)
    # Official predict_image math (Apple ml-sharp); independent of optional gsplat CUDA renderer.
    with torch.inference_mode():
        inp=torch.from_numpy(image.copy()).float().to(device).permute(2,0,1)[None]/255
        inp=torch.nn.functional.interpolate(inp,size=(1536,1536),mode="bilinear",align_corners=True)
        ndc=predictor(inp,torch.tensor([focal/w],device=device,dtype=torch.float32))
        k=torch.tensor([[focal,0,w/2,0],[0,focal,h/2,0],[0,0,1,0],[0,0,0,1]],device=device,dtype=torch.float32)
        k[0]*=1536/w; k[1]*=1536/h
        gaussians=unproject_gaussians(ndc,torch.eye(4,device=device),k,(1536,1536)).to("cpu")
    del predictor,ndc,inp
    gc.collect()
    if device=="cuda": torch.cuda.empty_cache()
    progress("Depth Anything V2 metric indoor depth")
    sys.path.insert(0,str(ROOT/".runtime/Depth-Anything-V2/metric_depth"))
    from depth_anything_v2.dpt import DepthAnythingV2
    depth_model=DepthAnythingV2(encoder="vitl",features=256,out_channels=[256,512,1024,1024],max_depth=20)
    depth_model.load_state_dict(torch.load(ROOT/".runtime/weights/depth_anything_v2_metric_hypersim_vitl.pth",map_location="cpu",weights_only=True))
    depth_model.eval().to(device)
    with torch.inference_mode():
        depth=depth_model.infer_image(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
    del depth_model
    gc.collect()
    if device=="cuda": torch.cuda.empty_cache()
    np.save(out/"depth.npy",depth)
    progress("Metric alignment and surface cache")
    scale,diagnostics=align_scale(gaussians.mean_vectors.numpy(),gaussians.opacities.numpy(),depth,focal)
    gaussians=gaussians._replace(mean_vectors=gaussians.mean_vectors*scale,singular_values=gaussians.singular_values*scale)
    save_ply(gaussians,focal,(h,w),out/"background.ply")
    write_json(out/"surface.json",surface(depth,focal))
    write_json(out/"graph.json",{"nodes":[],"edges":[],"status":"not_generated"})
    manifest={"version":1,"id":out.name,"title":image_path.stem,"source":"source.jpg","splat":"background.ply",
        "surface":"surface.json","graph":"graph.json","camera":{"width":w,"height":h,"fx":focal,"fy":focal,"cx":w/2,"cy":h/2,
        "position":[0,0,0],"target":[0,0,-float(np.median(depth))],"up":[0,1,0]},
        "alignment":diagnostics,"orbit_degrees":2,"presentation":{"vertical_degrees":.5,"preview_zoom":1.06},"coordinate_system":"three-camera-x-right-y-up-z-back",
        "splat_coordinate_system":"opencv-x-right-y-down-z-forward",
        "models":{"background":"apple/ml-sharp","depth":"Depth-Anything-V2-Metric-Hypersim-Large"},
        "limitations":["Monocular inferred geometry; hidden surfaces unknown","Camera up assumed from image; support planes require verification"]}
    write_json(out/"scene.json",manifest)
    progress("Ready")
    return out

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("image"); parser.add_argument("--output")
    args=parser.parse_args()
    print(build(args.image,args.output))

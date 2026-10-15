"""Qwen names/attributes -> SAM3 text masks -> metric visible-surface boxes.
Spatial predicates are computed by the same JS geometry module used by the viewer.
"""
from __future__ import annotations
import argparse,gc,json,os,shutil,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
from .build import ROOT,write_json
PROMPT='''List the visible, distinct object categories in this photograph, including support surfaces (table, floor, shelf) when visible. Return ONLY a JSON object {"objects":[{"name":"short singular English category","attributes":["color or material"]}]}. Use concrete nouns useful as segmentation text prompts. No spatial relations, positions, bounding boxes, counts or inferred hidden objects. Do not enumerate object parts separately. At most 20 categories.'''

def name_batch(entries):
    import torch
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
    pending=[e for e in entries if not (Path(e["out"])/"names.json").exists()]
    if not pending:return
    model_path=ROOT/".runtime/weights/Qwen3-VL-4B-Instruct"
    processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
    model=Qwen3VLForConditionalGeneration.from_pretrained(model_path,dtype=torch.bfloat16,device_map="cuda",attn_implementation="sdpa",local_files_only=True)
    for entry in pending:
        out=Path(entry["out"]);out.mkdir(parents=True,exist_ok=True)
        image=Image.open(entry["image"]).convert("RGB");image.thumbnail((1000,1000))
        messages=[{"role":"user","content":[{"type":"image","image":image},{"type":"text","text":PROMPT}]}]
        inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors="pt").to("cuda")
        with torch.inference_mode():
            generated=model.generate(**inputs,max_new_tokens=900,do_sample=False)
        raw=processor.decode(generated[0,inputs["input_ids"].shape[-1]:],skip_special_tokens=True)
        (out/"names-raw.txt").write_text(raw,encoding="utf-8")
        start,end=raw.find("{"),raw.rfind("}")+1
        data=json.loads(raw[start:end])
        objects=[];seen=set()
        for obj in data["objects"]:
            name=str(obj.get("name","")).strip().lower()
            if name and name not in seen:
                seen.add(name);objects.append({"name":name,"attributes":[str(x) for x in obj.get("attributes",[])][:5]})
        write_json(out/"names.json",{"objects":objects[:20],"model":"Qwen/Qwen3-VL-4B-Instruct","spatial_relations_requested":False})
        print(entry["id"],"names:",", ".join(x["name"] for x in objects),flush=True)
    del model,processor,inputs,generated;gc.collect();torch.cuda.empty_cache()

def prepare_depth(entry):
    import cv2,torch
    from sharp.utils.io import load_rgb
    out=Path(entry["out"]);out.mkdir(parents=True,exist_ok=True)
    if (out/"depth.npy").exists() and (out/"scene.json").exists():
        return json.loads((out/"scene.json").read_text(encoding="utf-8"))["camera"]
    if (out/"depth.npy").exists() and (out/"camera.json").exists():
        return json.loads((out/"camera.json").read_text(encoding="utf-8"))
    image,_,focal=load_rgb(Path(entry["image"]))
    h,w=image.shape[:2];factor=min(1,1280/max(h,w))
    if factor<1:image=cv2.resize(image,(round(w*factor),round(h*factor)));focal*=factor
    h,w=image.shape[:2];Image.fromarray(image).save(out/"source.jpg",quality=95)
    sys.path.insert(0,str(ROOT/".runtime/Depth-Anything-V2/metric_depth"))
    from depth_anything_v2.dpt import DepthAnythingV2
    dataset=entry.get("depth_domain","hypersim");max_depth=80 if dataset=="vkitti" else 20
    model=DepthAnythingV2(encoder="vitl",features=256,out_channels=[256,512,1024,1024],max_depth=max_depth)
    model.load_state_dict(torch.load(ROOT/f".runtime/weights/depth_anything_v2_metric_{dataset}_vitl.pth",map_location="cpu",weights_only=True))
    model.eval().cuda()
    with torch.inference_mode():depth=model.infer_image(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
    np.save(out/"depth.npy",depth)
    del model;gc.collect();torch.cuda.empty_cache()
    camera={"width":w,"height":h,"fx":float(focal),"fy":float(focal),"cx":w/2,"cy":h/2}
    write_json(out/"camera.json",camera)
    return camera

def mask_box(mask,depth,camera):
    import cv2
    mask=cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8))>0
    yy,xx=np.where(mask&np.isfinite(depth)&(depth>.1))
    if len(xx)<50:return None
    z=depth[yy,xx];valid=(z>=np.percentile(z,2))&(z<=np.percentile(z,98))
    xx,yy,z=xx[valid],yy[valid],z[valid]
    points=np.stack(((xx-camera["cx"])*z/camera["fx"],-(yy-camera["cy"])*z/camera["fy"],-z),1)
    return {"min":np.percentile(points,2,axis=0).tolist(),"max":np.percentile(points,98,axis=0).tolist()}

def compute_relations(nodes):
    node=shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
    script=ROOT/"frontend/scripts/compute-relations.mjs"
    result=subprocess.run([node,str(script)],input=json.dumps(nodes),text=True,capture_output=True,check=True)
    return json.loads(result.stdout)

def segment_batch(entries,progress=print):
    import torch
    # No torch.compile or optional perflib kernels needed for image grounding.
    os.environ["USE_PERFLIB"]="0"
    from sam3.model_builder import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor
    model=build_sam3_image_model(checkpoint_path=str(ROOT/".runtime/weights/sam3/sam3.pt"),load_from_HF=False,compile=False)
    processor=Sam3Processor(model,confidence_threshold=.5)
    for entry in entries:
        out=Path(entry["out"])
        if (out/"graph.json").exists():
            old=json.loads((out/"graph.json").read_text(encoding="utf-8"))
            if old.get("status")=="generated":continue
        camera=entry["camera"];depth=np.load(out/"depth.npy")
        objects=json.loads((out/"names.json").read_text(encoding="utf-8"))["objects"]
        image=Image.open(out/"source.jpg").convert("RGB")
        nodes=[];accepted=[]
        (out/"masks").mkdir(exist_ok=True)
        with torch.inference_mode(),torch.autocast("cuda",dtype=torch.bfloat16):
            state=processor.set_image(image)
            for obj in objects:
                processor.reset_all_prompts(state)
                result=processor.set_text_prompt(obj["name"],state)
                masks=result["masks"].squeeze(1).cpu().numpy()
                scores=result["scores"].float().flatten().cpu().numpy()
                for index in np.argsort(scores)[::-1]:
                    mask=masks[index].astype(bool)
                    if mask.sum()<100:continue
                    duplicate=any(np.logical_and(mask,prev).sum()/max(1,np.logical_or(mask,prev).sum())>.75 for prev in accepted)
                    if duplicate:continue
                    box=mask_box(mask,depth,camera)
                    if box is None:continue
                    nid=f"obj-{len(nodes):03d}"
                    yy,xx=np.where(mask)
                    Image.fromarray(mask.astype(np.uint8)*255).save(out/"masks"/f"{nid}.png")
                    nodes.append({"id":nid,"name":obj["name"],"category_attributes":obj["attributes"],"score":float(scores[index]),
                        "mask":f"masks/{nid}.png","bbox2d":[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)],
                        "box":box,"source":"sam3-metric-depth","box_extent":"visible-surface-robust-aabb"})
                    accepted.append(mask)
                print(entry["id"],obj["name"],"nodes",len(nodes),flush=True)
        from .cleanup import clean_nodes
        write_json(out/'nodes-raw.json',nodes)
        nodes,cleanup=clean_nodes(nodes,out)
        progress('Relationship analysis')
        edges=compute_relations(nodes)
        graph={"version":1,"status":"generated","nodes":nodes,"edges":edges,"camera":camera,
            "relation_policy":"directed-support-no-under-v4",
            "cleanup":cleanup,
            "models":{"names":"Qwen/Qwen3-VL-4B-Instruct","masks":"facebook/sam3","depth":entry.get("depth_domain","hypersim")},
            "coordinate_system":"three-camera-x-right-y-up-z-back","units":"meters",
            "limitations":["Boxes bound visible surfaces, not hidden volume","Gravity assumed from photo vertical","Metric depth is estimated"]}
        write_json(out/"graph.json",graph)
        del state;gc.collect();torch.cuda.empty_cache()
        print(entry["id"],"graph ready",len(nodes),len(edges),flush=True)

def run(entries,progress=print):
    for entry in entries:entry["out"]=str(ROOT/entry["out"]);entry["image"]=str(ROOT/entry["image"])
    entries=[e for e in entries if not (Path(e["out"])/"graph.json").exists() or json.loads((Path(e["out"])/"graph.json").read_text(encoding="utf-8")).get("status")!="generated"]
    if not entries:return
    progress('Object recognition')
    name_batch(entries)
    for entry in entries:
        print(entry["id"],"metric depth",flush=True)
        entry["camera"]=prepare_depth(entry)
    segment_batch(entries,progress)

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("manifest");args=parser.parse_args()
    run(json.loads(Path(args.manifest).read_text(encoding="utf-8"))["images"])

"""Reproducible selected-instance audit; not full node precision or 3D GT."""
import json
from pathlib import Path
from pipelines.scene.build import ROOT,write_json

def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return inter/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)
def score():
    refs=json.loads((ROOT/"docs/scene-reference-audit.json").read_text(encoding="utf-8"))
    manifest=json.loads((ROOT/"docs/scene-evaluation-set.json").read_text(encoding="utf-8"))
    entries={x["id"]:x for x in manifest["images"]};rows=[]
    for ref in refs["images"]:
        path=ROOT/entries[ref["id"]]["out"]/"graph.json"
        if not path.exists():rows.append({"id":ref["id"],"status":"not_generated"});continue
        graph=json.loads(path.read_text(encoding="utf-8"));nodes=graph["nodes"];w,h=graph["camera"]["width"],graph["camera"]["height"]
        candidates=[]
        for target in ref["objects"]:
            aliases=[target["name"],*target["aliases"]]
            for node in nodes:
                name=node["name"].lower()
                if not any(name==x or name.endswith(" "+x) or x.endswith(" "+name) for x in aliases):continue
                b=node["bbox2d"];overlap=iou(target["bbox_normalized"],[b[0]/w,b[1]/h,b[2]/w,b[3]/h])
                if overlap>=.3:candidates.append((overlap,target["id"],node["id"]))
        matches={};used=set()
        for overlap,tid,nid in sorted(candidates,reverse=True):
            if tid not in matches and nid not in used:matches[tid]={"node":nid,"iou":overlap};used.add(nid)
        relation_checks=[]
        for a,p,b in ref["relations"]:
            endpoints=a in matches and b in matches
            found=endpoints and any(e["source"]==matches[a]["node"] and e["target"]==matches[b]["node"] and e["relation"]==p for e in graph["edges"])
            relation_checks.append({"reference":[a,p,b],"endpoints_matched":endpoints,"recovered":bool(found)})
        rows.append({"id":ref["id"],"status":"audited","generated_nodes":len(nodes),"matched":len(matches),"reference_nodes":len(ref["objects"]),"matches":matches,"relations":relation_checks,"recovered_relations":sum(x["recovered"] for x in relation_checks),"reference_relations":len(relation_checks)})
    write_json(ROOT/"docs/scene-evaluation-results.json",{"method":refs["method"],"rows":rows})
    lines=["# Scene reference audit","",refs["method"],"","| Photograph | Nodes generated | Reference matches | Relations recovered |","|---|---:|---:|---:|"]
    for r in rows:
        if r["status"]!="audited":lines.append(f'| {r["id"]} | pending | pending | pending |');continue
        lines.append(f'| {r["id"]} | {r["generated_nodes"]} | {r["matched"]}/{r["reference_nodes"]} | {r["recovered_relations"]}/{r["reference_relations"]} |')
    done=[r for r in rows if r["status"]=="audited"]
    matched=sum(r["matched"] for r in done);total=sum(r["reference_nodes"] for r in done)
    rel=sum(r["recovered_relations"] for r in done);rel_total=sum(r["reference_relations"] for r in done)
    lines+=["",f"Selected object correspondence: {matched}/{total}. Selected relation recovery: {rel}/{rel_total}.",
        "", "Previous user-reported values: object correspondence 14/36 (38.9%), relation accuracy 9/10 (90%). Different photos, annotations and possibly definitions: no valid improvement claim.",
        "", "Unmatched and extra predicted nodes are retained in raw graph JSON. Full node precision/recall, complete relation precision, and metric 3D accuracy remain unmeasured. Reference audit is provisional until independently reviewed."]
    (ROOT/"docs/scene-evaluation.md").write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines))
if __name__=="__main__":score()

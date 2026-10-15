"""Rebuild derived graphs, preserving the original predictions for audit."""
import json
from .build import ROOT,write_json
from .graph import compute_relations

def run():
    paths=sorted(set((ROOT/'storage/scene_cache').glob('*/graph.json'))|set((ROOT/'storage/scene_evaluation').glob('*/graph.json')))
    rows=[]
    for path in paths:
        graph=json.loads(path.read_text(encoding='utf-8'))
        if graph.get('status')!='generated':continue
        backup=path.with_name('graph-unpruned-v1.json')
        if not backup.exists():write_json(backup,graph)
        original=json.loads(backup.read_text(encoding='utf-8'))
        graph['edges']=compute_relations(graph['nodes'])
        graph['relation_policy']='nearest-support-neighbors-v2'
        write_json(path,graph)
        rows.append(dict(scene=path.parent.name,nodes=len(graph['nodes']),before=len(original['edges']),after=len(graph['edges']),edges_per_node=round(len(graph['edges'])/len(graph['nodes']),3)))
    write_json(ROOT/'docs/scene-pruning-results.json',rows)
    print(json.dumps(rows,indent=2))
if __name__=='__main__':run()

"""Rebuild derived graphs, preserving the original predictions for audit."""
import json
from .build import ROOT,write_json
from .graph import compute_relations

def run(cleanup=False):
    paths=sorted(set((ROOT/'storage/scene_cache').glob('*/graph.json'))|set((ROOT/'storage/scene_evaluation').glob('*/graph.json')))
    rows=[]
    for path in paths:
        graph=json.loads(path.read_text(encoding='utf-8'))
        if graph.get('status')!='generated':continue
        checkpoint=path.with_name('graph-before-v3.json')
        if not checkpoint.exists():write_json(checkpoint,graph)
        backup=path.with_name('graph-unpruned-v1.json')
        if not backup.exists():write_json(backup,graph)
        original=json.loads(backup.read_text(encoding='utf-8'))
        if cleanup:
            from .cleanup import clean_nodes
            graph['nodes'],graph['cleanup']=clean_nodes(original['nodes'],path.parent)
            from .floor import augment_floor
            graph['nodes'],graph['floor_estimation']=augment_floor(graph['nodes'],path.parent,graph['camera'])
        graph['edges']=compute_relations(graph['nodes'])
        graph['relation_policy']='directed-support-neighbors-v3'
        write_json(path,graph)
        rows.append(dict(scene=path.parent.name,nodes=len(graph['nodes']),before=len(original['edges']),after=len(graph['edges']),edges_per_node=round(len(graph['edges'])/len(graph['nodes']),3)))
    write_json(ROOT/('docs/scene-cleanup-results.json' if cleanup else 'docs/scene-pruning-results.json'),rows)
    print(json.dumps(rows,indent=2))
if __name__=='__main__':
    import sys
    run('--cleanup' in sys.argv)

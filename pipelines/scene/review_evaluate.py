"""Compute precision and recall only from explicitly confirmed review labels."""
import argparse,json
from .build import ROOT

def metrics(tp,fp,fn):
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'over_detection_rate':fp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}

def evaluate(pack,review):
    if review.get('confirmed') is not True or not review.get('reviewer','').strip():raise ValueError('Explicit human confirmation and reviewer are required')
    if review.get('pack_id')!=pack['pack_id']:raise ValueError('Review snapshot mismatch')
    expected={p['id']:p for p in pack['photos']}
    if len(review['photos'])!=len(expected) or {p['id'] for p in review['photos']}!=set(expected):raise ValueError('All five photos must be reviewed')
    result=[]
    for r in review['photos']:
        p=expected[r['id']]
        if r['graph_sha256']!=p['graph_sha256'] or not r.get('missing_checked'):raise ValueError('Snapshot or missing-object review is incomplete')
        if set(r['nodes'])!={n['id'] for n in p['nodes']} or set(r['edges'])!={str(i) for i in range(len(p['edges']))}:raise ValueError('Prediction IDs do not match')
        node_values=[v['decision'] for v in r['nodes'].values()];edge_values=[v['decision'] for v in r['edges'].values()]
        if not set(node_values)<={'tp','fp','duplicate'} or not set(edge_values)<={'tp','fp'}:raise ValueError('Unreviewed predictions remain')
        for i,e in enumerate(p['edges']):
            if r['edges'][str(i)]['decision']=='tp' and any(r['nodes'][nid]['decision']!='tp' for nid in (e['source'],e['target'])):
                raise ValueError('A correct relation must connect two correct unique nodes')
        for field in ('missing_nodes','missing_edges'):
            if not isinstance(r.get(field),list) or any(not isinstance(x,str) or not x.strip() for x in r[field]):raise ValueError('Missing items must be nonempty strings')
        result.append({'id':r['id'],'nodes':metrics(node_values.count('tp'),sum(x!='tp' for x in node_values),len(r['missing_nodes'])),
                       'relations':metrics(edge_values.count('tp'),edge_values.count('fp'),len(r['missing_edges']))})
    total={field:metrics(*(sum(r[field][key] for r in result) for key in ('tp','fp','fn'))) for field in ('nodes','relations')}
    return {'pack_id':pack['pack_id'],'reviewer':review['reviewer'],'photos':result,'micro_average':total,'scope':'five-photo user-reviewed snapshot; relation recall uses reviewer-specified missing relations'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('review');args=parser.parse_args()
    pack=json.loads((ROOT/'docs/scene-review/review-pack.json').read_text(encoding='utf-8'))
    with open(args.review,encoding='utf-8-sig') as stream:review=json.load(stream)
    result=evaluate(pack,review)
    (ROOT/'docs/scene-human-evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

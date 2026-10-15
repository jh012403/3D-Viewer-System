"""Auditable confidence, reflection and duplicate filtering before graph creation."""
from copy import deepcopy
from pathlib import Path
import numpy as np
from PIL import Image

POLICY='mask-box-cleanup-v3'
MAX_NODES=24
NAMES={'table':'테이블','chair':'의자','cabinet':'수납장','window':'창문','door':'문','floor':'바닥','ceiling':'천장','wall':'벽','bottle':'병','light fixture':'조명','person':'사람','car':'자동차','bus':'버스','tree':'나무','plant':'식물','vase':'꽃병','bowl':'그릇','plate':'접시','jug':'물병','glass bottle':'유리병','paper bag':'종이봉투','bag':'봉투'}

def overlap3d(a,b):
    lo=np.maximum(a['min'],b['min']);hi=np.minimum(a['max'],b['max'])
    inter=float(np.prod(np.maximum(0,hi-lo)))
    va=float(np.prod(np.maximum(1e-6,np.subtract(a['max'],a['min']))))
    vb=float(np.prod(np.maximum(1e-6,np.subtract(b['max'],b['min']))))
    return inter/max(va+vb-inter,1e-9),inter/max(min(va,vb),1e-9)

def clean_nodes(nodes,directory):
    directory=Path(directory);image=np.asarray(Image.open(directory/'source.jpg').convert('RGB'))
    height,width=image.shape[:2];total=height*width
    masks={n['id']:np.asarray(Image.open(directory/n['mask']))>0 for n in nodes if n.get('mask')}
    kept=[];removed=[];merged=[]
    def reject(n,reason,**extra):removed.append({'id':n['id'],'name':n['name'],'reason':reason,**extra})
    for original in sorted(nodes,key=lambda n:(-n.get('score',0),n['id'])):
        n=deepcopy(original);mask=masks.get(n['id'])
        if mask is None:reject(n,'missing-mask');continue
        area=int(mask.sum());n['mask_pixels']=area
        if 'bbox2d' not in n:
            yy,xx=np.where(mask);n['bbox2d']=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
        if n.get('score',0)<.60:reject(n,'confidence-below-0.60');continue
        if area<max(150,total*.0002):reject(n,'mask-too-small');continue
        duplicate=None
        for other in kept:
            if n['name'].lower()!=other['name'].lower():continue
            iou,containment=overlap3d(n['box'],other['box'])
            miou=np.logical_and(mask,masks[other['id']]).sum()/max(1,np.logical_or(mask,masks[other['id']]).sum())
            if iou>.45 or containment>.8 or miou>.65:duplicate=other;break
        if duplicate is not None:
            duplicate.setdefault('merged_ids',[]).append(n['id'])
            # Keep the higher-confidence geometry, not an inflated union of noisy boxes.
            merged.append({'id':n['id'],'into':duplicate['id'],'reason':'same-category-overlap'})
            continue
        kept.append(n)
    reflective=[n for n in kept if n['name'].lower() in ('mirror','window') or
        ('glass' in ' '.join(n.get('category_attributes',n.get('attributes',[]))).lower() and n['name'].lower() in ('table','door'))]
    horizontal=[n for n in kept if any(w in n['name'].lower() for w in ('shelf','table')) and any(w in str(n).lower() for w in ('glass','reflective','glossy'))]
    filtered=[]
    for n in kept:
        mask=masks[n['id']];reflection=None
        for surface in horizontal:
            plane=(surface['box']['min'][1]+surface['box']['max'][1])/2
            if n['box']['max'][1]>plane+.025:continue
            for other in kept:
                if other['id']==n['id'] or other['name']!=n['name']:continue
                a=n['bbox2d'];b=other['bbox2d']
                alignment=max(0,min(a[2],b[2])-max(a[0],b[0]))/max(1,min(a[2]-a[0],b[2]-b[0]))
                # Perspective truncates reflected silhouettes; require both image
                # alignment at the surface and compressed, below-plane depth.
                compressed=n['box']['max'][1]-n['box']['min'][1]<.55*(other['box']['max'][1]-other['box']['min'][1])
                symmetric=abs((n['box']['min'][1]+n['box']['max'][1]+other['box']['min'][1]+other['box']['max'][1])/2-2*plane)<.06
                if alignment>.45 and b[1]<a[1] and abs(a[1]-b[3])<height*.14 and other['box']['max'][1]>plane+.04 and (compressed or symmetric):
                    reflection=surface;reject(n,'reflection-below-horizontal-surface',surface=surface['id'],counterpart=other['id']);break
            if reflection:break
        if reflection:continue
        for surface in reflective:
            if surface['id']==n['id'] or surface['name']==n['name']:continue
            ratio=np.logical_and(mask,masks[surface['id']]).sum()/max(1,mask.sum())
            behind=np.mean(n['box']['min'][2:3]+n['box']['max'][2:3])<np.mean(surface['box']['min'][2:3]+surface['box']['max'][2:3])-.05
            if ratio>.8 and (surface['name'].lower()=='mirror' or behind):reflection=surface;break
        if reflection:reject(n,'inside-reflective-region',surface=reflection['id']);continue
        filtered.append(n)
    filtered.sort(key=lambda n:(-(n['score']*np.sqrt(n['mask_pixels']/total)),n['id']))
    for n in filtered[MAX_NODES:]:reject(n,'confidence-area-budget-24')
    result=filtered[:MAX_NODES]
    for n in result:
        n['category_attributes']=n.pop('attributes',n.get('category_attributes',[]))
        x=(n['bbox2d'][0]+n['bbox2d'][2])/2/width
        position='왼쪽' if x<.4 else ('오른쪽' if x>.6 else '가운데')
        n['instance_attributes']=[position];n['attribute_method']='original-image-horizontal-position'
        n['label']=f"{position} {NAMES.get(n['name'].lower(),n['name'])} #{n['id'].split('-')[-1]}"
    result.sort(key=lambda n:n['id'])
    return result,{'policy':POLICY,'input_nodes':len(nodes),'output_nodes':len(result),'removed':removed,'merged':merged,'max_nodes':MAX_NODES}

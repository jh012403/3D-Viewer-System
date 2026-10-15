"""Editorial demo caches. Photo-guided choices, not accuracy evaluation."""
import json
from copy import deepcopy
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageOps
from .build import ROOT,write_json

PROFILES={
 'sunroom':{
  'nodes':{'obj-000':'유리 테이블','obj-002':'앞쪽 라탄 의자','obj-004':'창가 라탄 의자','obj-003':'검은 의자','obj-006':'수납장','obj-019':'파란 병','obj-013':'바닥','obj-008':'창문'},
  'edges':[('002','on','013'),('004','on','013'),('003','on','013'),('000','on','013'),('006','on','013'),('019','on','006'),('002','next to','000'),('004','next to','002'),('003','next to','000'),('006','left of','004')],
  'summary':'창가에 라탄 의자 두 개가 놓여 있고, 검은 의자와 유리 테이블이 마주 보고 있습니다. 수납장 위에는 파란 병이 놓여 있습니다.',
  'slots':[('테이블 왼쪽',.34,.88,'obj-000',.18),('테이블 가운데',.60,.90,'obj-000',.18)],
 },
 'ceramics':{
  'nodes':{'obj-015':'윗단 유리 선반','obj-016':'가운데 유리 선반','obj-017':'아랫단 유리 선반','obj-011':'파란 주전자','obj-009':'무늬 접시','obj-005':'왼쪽 장식 접시','obj-006':'오른쪽 장식 접시','obj-000':'가운데 도자기 그릇','obj-001':'오른쪽 도자기 그릇'},
  'edges':[('011','on','015'),('009','on','015'),('005','on','016'),('006','on','016'),('000','on','017'),('001','on','017'),('009','left of','011'),('005','left of','006'),('000','left of','001')],
  'summary':'유리 선반 위에 도자기들이 층층이 전시되어 있습니다. 맨 위에는 무늬 접시와 파란 주전자가 있고, 가운데 장식 접시 아래로 도자기 그릇들이 이어집니다.',
  'slots':[('가운데 선반 여백',.28,.57,'obj-016',.12),('아랫단 선반 여백',.38,.79,'obj-017',.12)],
 },
 'd4f646fcc79650d6':{
  'nodes':{'trunk':'트렁크 바닥','obj-000':'왼쪽 장바구니','obj-001':'가운데 왼쪽 장바구니','obj-002':'가운데 오른쪽 장바구니','obj-003':'오른쪽 장바구니','obj-014':'왼쪽 후미등','obj-015':'오른쪽 후미등','seats':'뒷좌석'},
  'manual':{'trunk':('trunk floor',[132,305,638,366]),'seats':('seat',[172,80,605,278])},
  'edges':[('obj-000','on','trunk'),('obj-001','on','trunk'),('obj-002','on','trunk'),('obj-003','on','trunk'),('000','next to','001'),('001','next to','002'),('002','next to','003'),('014','left of','000'),('003','left of','015'),('seats','behind','obj-000')],
  'summary':'열린 트렁크 오른쪽에 장바구니 네 개가 나란히 놓여 있습니다. 뒤에는 뒷좌석이 보이고, 양옆의 후미등이 트렁크를 둘러싸고 있습니다.',
  'slots':[('트렁크 왼쪽',.30,.64,'trunk',.30),('장바구니 옆',.40,.65,'trunk',.25)],
 },
 'hall':{
  'nodes':{'obj-000':'왼쪽 대리석 기둥','obj-004':'오른쪽 대리석 기둥','obj-024':'왼쪽 조각상','obj-023':'오른쪽 조각상','obj-008':'왼쪽 샹들리에','obj-007':'오른쪽 샹들리에','obj-009':'계단','landing':'위층 바닥','lower-floor':'아래층 바닥','ceiling':'장식 천장'},
  'manual':{'landing':('floor',[380,460,1100,489]),'lower-floor':('floor',[970,684,1210,790]),'ceiling':('ceiling',[180,0,1150,60])},
  'edges':[('obj-000','on','landing'),('obj-004','on','landing'),('obj-008','attached to','ceiling'),('obj-007','attached to','ceiling'),('024','next to','000'),('023','next to','004'),('009','in front of','000'),('009','in front of','004'),('000','left of','004'),('024','left of','023')],
  'summary':'대리석 기둥과 두 조각상이 위층 공간을 장식하고 있습니다. 천장에는 샹들리에 두 개가 매달려 있고, 앞쪽의 계단이 아래층으로 이어집니다.',
  'slots':[('아래층 안쪽',.82,.85,'lower-floor',.65),('아래층 오른쪽',.89,.88,'lower-floor',.60)],
 }
}

def run():
    summaries=[]
    for scene,profile in PROFILES.items():
        out=ROOT/'storage/scene_cache'/scene
        original=json.loads((out/'graph-unpruned-v1.json').read_text(encoding='utf-8'))
        camera=original['camera'];depth=np.load(out/'depth.npy');image=Image.open(out/'source.jpg').convert('RGB');w,h=image.size
        def point(u,v):
            x=int(np.clip(u*w,1,w-2));y=int(np.clip(v*h,1,h-2));z=float(np.median(depth[y-1:y+2,x-1:x+2]))
            return [(x-camera['cx'])*z/camera['fx'],-(y-camera['cy'])*z/camera['fy'],-z]
        source={n['id']:n for n in original['nodes']};nodes=[]
        for nid,label in profile['nodes'].items():
            if nid in source:n=deepcopy(source[nid])
            else:
                category,rect=profile['manual'][nid];lo=point(rect[0]/w,rect[1]/h);hi=point(rect[2]/w,rect[3]/h)
                n={'id':nid,'name':category,'bbox2d':rect,'box':{'min':np.minimum(lo,hi).tolist(),'max':np.maximum(lo,hi).tolist()},'source':'editorial-demo'}
            n['label']=label;n['attribute_method']='photo-guided-editorial';n.pop('instance_attributes',None)
            rect=n['bbox2d'];thumb=ImageOps.fit(image.crop(rect),(160,120));(out/'thumbs').mkdir(exist_ok=True);thumb.save(out/'thumbs'/f'{nid}.jpg',quality=92);n['thumbnail']=f'thumbs/{nid}.jpg'
            if n.get('mask'):
                mask=np.asarray(Image.open(out/n['mask']))
                contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    contour=max(contours,key=cv2.contourArea).reshape(-1,2);contour=contour[::max(1,len(contour)//150)]
                    n['outline']=[point(x/w,y/h) for x,y in contour]
            nodes.append(n)
        def node_id(x):return 'obj-'+x if x.isdigit() else x
        edges=[{'source':node_id(a),'target':node_id(b),'relation':r,'method':'editorial-demo'} for a,r,b in profile['edges']]
        slots=[]
        for index,(label,u,v,support,height) in enumerate(profile['slots']):
            pos=point(u,v);slots.append({'id':f'spot-{index}','label':label,'position':pos,'normal':[0,1,0],'support':support,'height_m':height,'radius_px':85})
        graph={'version':2,'status':'generated','curated':True,'provenance':'Photo-guided manual demo curation; not an evaluated automatic result','nodes':nodes,'edges':edges,'camera':camera,'summary':profile['summary'],'recommended_placements':slots}
        write_json(out/'graph.json',graph)
        # Track small curated JSON so the authored demo survives ignored caches.
        tracked=ROOT/'assets/scene-demo'/scene;tracked.mkdir(parents=True,exist_ok=True)
        write_json(tracked/'graph.json',graph)
        manifest=json.loads((out/'scene.json').read_text(encoding='utf-8'));manifest['curated']=True;manifest['orbit_degrees']=5
        manifest['presentation']={'vertical_degrees':.5,'preview_zoom':1.13,'orbit_radius_m':.12}
        write_json(out/'scene.json',manifest)
        summaries.append({'scene':scene,'title':manifest['title'],'nodes':len(nodes),'edges':len(edges),'placements':slots})
    write_json(ROOT/'docs/demo-curation.json',summaries)
    print(json.dumps(summaries,ensure_ascii=True,indent=2))

if __name__=='__main__':run()

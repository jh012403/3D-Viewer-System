"""Photo-guided industrial demo authoring, independent of historical caches."""
import json
import numpy as np
from PIL import Image,ImageOps,ImageDraw
from .build import ROOT,write_json

# Pixel rectangles in the licensed 1280px source photographs. These are authored
# visible assets, not claims of automatic detector accuracy or measured geometry.
PROFILES={
'twin-logistics':dict(title='물류 창고 · 입출고 구역',nodes=[
 ('floor','바닥','floor',[330,680,1220,840],'구조물','B'),
 ('rack','보관 랙','rack',[480,5,1230,485],'구조물','A'),
 ('pallet','이송 팔레트','pallet',[225,260,520,435],'적재물','B'),
 ('cartons','출고 상자 묶음','carton',[255,175,465,375],'적재물','B'),
 ('jack','핸드 팔레트 트럭','pallet truck',[402,342,564,464],'설비','B'),
 ('containers','보관 용기 묶음','container',[658,154,1057,370],'적재물','A'),
 ('upper','상단 보관 상자','carton',[677,0,1085,162],'적재물','A')],
 edges=[('rack','on','floor'),('pallet','on','floor'),('cartons','on','pallet'),('jack','on','floor'),('containers','on','rack'),('upper','on','rack'),('pallet','next to','rack'),('jack','next to','pallet')],
 slots=[('입출고 대기 위치',.66,.84,'floor',.55),('통로 우측 대기 위치',.83,.78,'floor',.5)],
 summary='Zone A에는 보관 랙과 용기·상자가 정리되어 있고, Zone B에는 출고 팔레트와 핸드 팔레트 트럭이 있습니다. 전면 여유 공간에서 신규 자산 반입을 검토합니다.'),
'twin-laboratory':dict(title='분석 실험실 · 시료 작업대',nodes=[
 ('bench','실험 작업대','table',[300,705,1275,850],'구조물','B'),
 ('microscope','광학 현미경','microscope',[329,0,837,521],'설비','A'),
 ('beaker','중앙 비커','glass beaker',[791,595,963,850],'공구','B'),
 ('flask','오른쪽 삼각 플라스크','glass flask',[979,411,1104,707],'공구','B'),
 ('small','오른쪽 비커','glass beaker',[995,698,1152,850],'공구','B'),
 ('dish','배양 접시','glass petri dish',[563,727,746,830],'공구','B'),
 ('tweezers','핀셋','tweezers',[296,752,583,846],'공구','B'),
 ('tubes','시험관 보관대','test tube rack',[1082,265,1278,597],'설비','A')],
 edges=[('microscope','on','bench'),('beaker','on','bench'),('flask','on','bench'),('small','on','bench'),('dish','on','bench'),('tweezers','on','bench'),('tubes','on','bench'),('beaker','next to','small'),('dish','next to','tweezers')],
 slots=[('작업대 우측 여유 공간',.96,.76,'bench',.16),('작업대 앞쪽 여유 공간',.18,.94,'bench',.16)],
 summary='현미경과 시험관 보관대를 Zone A로, 비커·플라스크·배양 접시가 놓인 시료 작업 영역을 Zone B로 구분했습니다. 신규 공구를 작업대 여유 공간에 배치할 수 있습니다.'),
'twin-workbench':dict(title='정밀 작업대 · 조립 셀',nodes=[
 ('bench','목재 작업대','table',[15,697,740,850],'구조물','B'),
 ('instrument','정밀 측정 장치','instrument',[0,581,254,702],'설비','A'),
 ('scope','작업용 광학 장치','microscope',[270,137,486,433],'설비','A'),
 ('stand','고정 지그','clamp',[394,472,530,757],'공구','B'),
 ('tray','부품 트레이','tray',[256,608,365,655],'공구','B'),
 ('pad','작업 받침','work pad',[310,632,592,727],'공구','B'),
 ('mount','광학 장치 지지대','mount',[0,299,286,581],'구조물','A')],
 edges=[('instrument','on','bench'),('stand','on','bench'),('tray','on','bench'),('pad','on','bench'),('mount','on','bench'),('scope','attached to','mount'),('tray','next to','instrument'),('stand','next to','pad')],
 slots=[('전면 작업대 왼쪽',.16,.91,'bench',.20),('전면 작업대 중앙',.48,.94,'bench',.18)],
 summary='Zone A의 광학 장치와 정밀 측정 장치 옆에 부품 트레이가 있습니다. Zone B의 고정 지그와 작업 받침 앞쪽은 신규 공구 반입을 검토할 수 있는 영역입니다.'),
'twin-factory':dict(title='산업 현장 · 차량 반입 홀',nodes=[
 ('floor','반입 홀 바닥','floor',[100,779,1278,852],'구조물','B'),
 ('truck','화물 차량','truck',[1020,558,1279,692],'설비','B'),
 ('guard1','전면 안전 가드','guard rail',[525,698,809,790],'구조물','A'),
 ('guard2','안쪽 안전 가드','guard rail',[862,679,925,714],'구조물','A'),
 ('column','전면 구조 기둥','column',[350,26,480,778],'구조물','A'),
 ('door','반입 셔터','door',[0,8,329,814],'구조물','A'),
 ('duct','환기 덕트','duct',[355,0,791,351],'설비','A'),
 ('catwalk','상부 점검 통로','platform',[800,313,1278,502],'구조물','A')],
 edges=[('truck','on','floor'),('guard1','on','floor'),('guard2','on','floor'),('column','on','floor'),('door','next to','column'),('guard1','next to','column'),('guard2','next to','truck'),('duct','attached to','column'),('catwalk','attached to','column')],
 slots=[('전면 반입 대기 위치',.62,.91,'floor',.85),('차량 앞쪽 대기 위치',.83,.86,'floor',.70)],
 summary='Zone A는 셔터·기둥·안전 가드가 있는 시설 구역이며, Zone B는 화물 차량과 신규 자산의 반입 구역입니다. 안전 가드 앞쪽 여유 공간에 자산을 배치해 동선을 검토합니다.')
}

def run():
 rows=[]
 for order,(scene,p) in enumerate(PROFILES.items()):
  out=ROOT/'storage/scene_cache'/scene
  m=json.loads((out/'scene.json').read_text(encoding='utf-8'));c=m['camera'];depth=np.load(out/'depth.npy');im=Image.open(out/'source.jpg');w,h=im.size
  def point(x,y):
   x=int(np.clip(x,2,w-3));y=int(np.clip(y,2,h-3));z=float(np.median(depth[y-2:y+3,x-2:x+3]));return np.array([(x-c['cx'])*z/c['fx'],-(y-c['cy'])*z/c['fy'],-z])
  nodes=[]
  for nid,label,name,rect,category,zone in p['nodes']:
   x1,y1,x2,y2=rect;y2=min(y2,h-1)
   pts=np.array([point(x,y) for x in np.linspace(x1,x2,12) for y in np.linspace(y1,y2,12)])
   lo=np.quantile(pts,.08,axis=0);hi=np.quantile(pts,.92,axis=0);hi=np.maximum(hi,lo+.025)
   (out/'thumbs').mkdir(exist_ok=True);ImageOps.fit(im.crop((x1,y1,x2,y2)),(160,120)).save(out/'thumbs'/f'{nid}.jpg')
   node=dict(id=nid,label=label,name=name,box={'min':lo.tolist(),'max':hi.tolist()},bbox2d=[x1,y1,x2,y2],source='editorial-photo-depth',category=category,zone='Zone '+zone,thumbnail=f'thumbs/{nid}.jpg',outline=[point(x,y).tolist() for x,y in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]])
   if 'glass' in name:
    mask=Image.new('L',im.size);ImageDraw.Draw(mask).rectangle((x1,y1,x2,y2),fill=255);(out/'masks').mkdir(exist_ok=True);mask.save(out/'masks'/f'{nid}.png');node['mask']=f'masks/{nid}.png'
   nodes.append(node)
  slots=[dict(id=f'spot-{i}',label=label,position=point(u*w,v*h).tolist(),normal=[0,1,0],support=support,height_m=height,radius_px=85) for i,(label,u,v,support,height) in enumerate(p['slots'])]
  zones=[]
  for key,color in [('A','#51c9db'),('B','#f0bb64')]:
   members=[n for n in nodes if n['zone']=='Zone '+key and n['name'] not in ('floor','table')];bounds=np.array([v for n in members for v in [n['box']['min'],n['box']['max']]])
   floor_y=slots[0]['position'][1];lo=bounds.min(0);hi=bounds.max(0)
   if key=='B':
    lo=np.minimum(lo,np.array([s['position'] for s in slots]).min(0)-.4);hi=np.maximum(hi,np.array([s['position'] for s in slots]).max(0)+.4)
   zones.append(dict(id='Zone '+key,name='시설·보관' if key=='A' else '작업·반입',color=color,bounds={'min':[float(lo[0]),floor_y,float(lo[2])],'max':[float(hi[0]),floor_y,float(hi[2])]}))
  graph=dict(version=3,status='generated',curated=True,digital_twin=True,provenance='Photo-guided authored assets and relationships; monocular estimated dimensions, not surveyed measurements',nodes=nodes,edges=[dict(source=a,relation=r,target=b,method='editorial-demo') for a,r,b in p['edges']],camera=c,zones=zones,summary=p['summary'],recommended_placements=slots)
  write_json(out/'graph.json',graph)
  m.update(title=p['title'],curated=True,digital_twin=True,sort_order=order,orbit_degrees=5,presentation={'vertical_degrees':.5,'preview_zoom':1.13,'orbit_radius_m':.12,'object_tint':'#ffffff'})
  write_json(out/'scene.json',m)
  tracked=ROOT/'assets/twin-demo'/scene;tracked.mkdir(parents=True,exist_ok=True);write_json(tracked/'graph.json',graph);write_json(tracked/'scene.json',m)
  rows.append(dict(scene=scene,title=p['title'],nodes=len(nodes),edges=len(graph['edges']),placements=slots))
 write_json(ROOT/'docs/twin-curation.json',rows)
 print(json.dumps(rows,ensure_ascii=True))
if __name__=='__main__':run()

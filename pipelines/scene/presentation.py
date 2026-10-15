"""Apply reviewed presentation metadata to the new demo caches only."""
import json
from .build import CACHE,write_json
PROFILES={
    'sunroom':('햇살 드는 유리 테이블 방',.5,.2,1.08),
    'ceramics':('도자기와 꽃 정물',3.0,.7,1.07),
    'hall':('조각상이 있는 전시 홀',1.5,.4,1.08),
    'd4f646fcc79650d6':('장바구니를 실은 자동차',1.5,.4,1.08),
}
for scene,(title,horizontal,vertical,zoom) in PROFILES.items():
    path=CACHE/scene/'scene.json'
    if not path.exists():continue
    data=json.loads(path.read_text(encoding='utf-8'))
    data['title']=title;data['orbit_degrees']=horizontal
    data['presentation']={'vertical_degrees':vertical,'preview_zoom':zoom,'initial_view':'original-camera-with-edge-crop','export_view':'uncropped-original-camera'}
    write_json(path,data)

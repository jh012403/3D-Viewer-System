"""New industrial demonstration caches; never modifies the original demo set."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipelines.scene.build import build
SCENES={'twin-logistics':4481259,'twin-laboratory':2280571,'twin-workbench':3912981,'twin-factory':209251}
if __name__=='__main__':
    rows=[]
    for scene,photo in SCENES.items():
        source=ROOT/'storage/twin_sources'/f'{photo}.jpg'
        print('BUILD',scene,flush=True)
        out=build(source,ROOT/'storage/scene_cache'/scene,progress=lambda x:print(x,flush=True))
        rows.append({'scene':scene,'provider':'Pexels','photo_id':photo,'source_page':f'https://www.pexels.com/photo/{photo}/','download':f'https://images.pexels.com/photos/{photo}/pexels-photo-{photo}.jpeg?w=1280','license_page':'https://www.pexels.com/license/','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'local':str(source.relative_to(ROOT))})
        (ROOT/'docs/twin-photo-sources.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')

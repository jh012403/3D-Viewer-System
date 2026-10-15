"""Record local cache integrity without committing large assets."""
import hashlib
import json
from .build import ROOT, CACHE

rows=[]
for directory in sorted(CACHE.iterdir()):
    if not (directory/'scene.json').exists():
        continue
    files={}
    for path in sorted(directory.rglob('*')):
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        files[path.relative_to(directory).as_posix()]={
            'bytes':path.stat().st_size,
            'sha256':digest,
        }
    rows.append({'id':directory.name,'files':files})
(ROOT/'docs/scene-cache-manifest.json').write_text(json.dumps({
    'source':'Replacement photos from official Depth-Anything-V2 examples; see scene-evaluation-set.json',
    'caches':rows,
},indent=2),encoding='utf-8')

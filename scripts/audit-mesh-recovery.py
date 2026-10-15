import json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
models={}
for name in ['FastVLM-0.5B','TRELLIS.2-4B','dinov3-vitl16','RMBG-2.0','TRELLIS-image-large']:
    directory=root/'.runtime/weights'/name
    files=[p for p in directory.rglob('*') if p.is_file() and '.cache' not in p.parts]
    models[name]={'files':len(files),'bytes':sum(p.stat().st_size for p in files),'weight_files':[str(p.relative_to(directory)) for p in files if p.suffix in ('.safetensors','.bin')]}
fastvlm=json.loads((root/'storage/fastvlm-chair-result.json').read_text(encoding='utf-16'))
report={'models':models,'trellis_repo_commit':subprocess.check_output([r'C:\Program Files\Git\cmd\git.exe','-C',str(root/'.runtime/TRELLIS.2'),'rev-parse','HEAD'],text=True).strip(),
 'fastvlm':fastvlm,'trellis_inference_verified':False,'end_to_end_verified':False,
 'blocker':'WSL install returned restart required; no Linux runtime available before restart',
 'bridge_verified':'Generated asset resolver and normalization tested with isolated synthetic GLB; browser placement uses Khronos fixture, not TRELLIS output'}
(root/'docs/mesh-recovery-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'models':models,'fastvlm_parse_status':fastvlm.get('vlm_parse_status'),'fastvlm_category':fastvlm.get('object_category')},indent=2))

"""WSL-only: reuse already-downloaded weights through local HF cache symlinks."""
from pathlib import Path
root=Path('/mnt/c/Users/user/Desktop/project/3D-Viewer-System/.runtime/weights')
models={'TRELLIS.2-4B':'microsoft/TRELLIS.2-4B','TRELLIS-image-large':'microsoft/TRELLIS-image-large','dinov3-vitl16':'facebook/dinov3-vitl16-pretrain-lvd1689m','dinov3-vitb16':'facebook/dinov3-vitb16-pretrain-lvd1689m','RMBG-2.0':'briaai/RMBG-2.0'}
for name,repo in models.items():
 source=root/name;metadata=next((source/'.cache/huggingface/download').rglob('*.metadata'));commit=metadata.read_text().splitlines()[0]
 target=Path('/opt/prism/hf/hub')/('models--'+repo.replace('/','--'));snapshot=target/'snapshots'/commit;snapshot.mkdir(parents=True,exist_ok=True);(target/'refs').mkdir(exist_ok=True);(target/'refs/main').write_text(commit)
 for file in source.rglob('*'):
  if not file.is_file() or '.cache' in file.parts:continue
  link=snapshot/file.relative_to(source);link.parent.mkdir(parents=True,exist_ok=True)
  if not link.exists():link.symlink_to(file)
 print(repo,commit)

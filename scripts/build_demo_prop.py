"""Small authored presentation prop; this is not a mesh-generation result."""
from pathlib import Path
import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

root=Path(__file__).resolve().parents[1];scene=trimesh.Scene()
def add(mesh,color,name,roughness=.65):
    mesh.visual=trimesh.visual.TextureVisuals(material=PBRMaterial(baseColorFactor=color,roughnessFactor=roughness,metallicFactor=0))
    scene.add_geometry(mesh,node_name=name)
profile=np.array([[0,0],[.055,0],[.064,.008],[.074,.105],[.073,.115],[.063,.115],[.061,.105],[.051,.015],[0,.015]])
pot=trimesh.creation.revolve(profile,sections=64)
# revolve is Z-up; the scene viewer is Y-up.
rotation=trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]);pot.apply_transform(rotation)
add(pot,[210,206,181,255],'ceramic-pot',.45)
soil=trimesh.creation.cylinder(radius=.062,height=.006,sections=48);soil.apply_transform(rotation);soil.apply_translation([0,.106,0]);add(soil,[53,39,25,255],'soil')
for i in range(9):
    angle=i*2.399;length=.13+(i%3)*.025
    tip=np.array([np.cos(angle)*.08,.15+length*.7,np.sin(angle)*.08]);base=np.array([0,.105,0])
    direction=tip-base;stem=trimesh.creation.cylinder(radius=.002,height=np.linalg.norm(direction),sections=8)
    stem.apply_transform(trimesh.geometry.align_vectors([0,0,1],direction));stem.apply_translation((base+tip)/2);add(stem,[65,88,39,255],f'stem-{i}')
    leaf=trimesh.creation.uv_sphere(count=[12,16]);leaf.apply_scale([.025,.007,.075])
    axis=np.array([np.cos(angle)*.65,.8,np.sin(angle)*.65]);leaf.apply_transform(trimesh.geometry.align_vectors([0,0,1],axis));leaf.apply_translation(tip)
    add(leaf,[48+i*3,83+i*4,40+i*2,255],f'leaf-{i}',.7)
out=root/'frontend/public/demo';out.mkdir(parents=True,exist_ok=True);scene.export(out/'planter.glb')
print(out/'planter.glb')

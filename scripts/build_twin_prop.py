"""Authored equipment-case rehearsal fixture, never presented as generated AI output."""
from pathlib import Path
import trimesh
from trimesh.visual.material import PBRMaterial
s=trimesh.Scene()
def box(size,pos,color,name):
 m=trimesh.creation.box(size);m.apply_translation(pos);m.visual=trimesh.visual.TextureVisuals(material=PBRMaterial(baseColorFactor=color,roughnessFactor=.48,metallicFactor=.25));s.add_geometry(m,node_name=name)
box([.42,.25,.28],[0,.125,0],[40,113,139,255],'equipment-case')
box([.44,.035,.30],[0,.2675,0],[24,49,62,255],'lid')
for x in [-.16,.16]:box([.045,.05,.025],[x,.245,.151],[203,210,210,255],'latch'+str(x))
box([.16,.022,.025],[0,.33,0],[25,31,35,255],'handle')
for x in [-.07,.07]:box([.02,.04,.025],[x,.30,0],[25,31,35,255],'handle-leg'+str(x))
s.export(Path(__file__).resolve().parents[1]/'frontend/public/demo/equipment-case.glb')

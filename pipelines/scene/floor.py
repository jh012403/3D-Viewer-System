"""Deterministic depth RANSAC; no completion of hidden object extents."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

def augment_floor(nodes, directory, camera):
    directory=Path(directory)
    depth=np.load(directory/'depth.npy');h,w=depth.shape
    yy,xx=np.mgrid[0:h:6,0:w:6];z=depth[yy,xx]
    points=np.stack(((xx-camera['cx'])*z/camera['fx'],-(yy-camera['cy'])*z/camera['fy'],-z),-1)
    tangent_x=np.gradient(points,axis=1);tangent_y=np.gradient(points,axis=0)
    normals=np.cross(tangent_x,tangent_y);normal_length=np.linalg.norm(normals,axis=-1)
    horizontal=abs(normals[:,:,1])/np.maximum(normal_length,1e-8)>.9
    valid=np.isfinite(points).all(-1)&(z>.1)&(yy>h*.45)&horizontal
    floors=[n for n in nodes if n['name'].lower() in ('floor','ground','road','pavement')]
    # Still-life glass shelves are not evidence of a room floor.
    if not floors and any('glass' in n['name'] and 'shelf' in n['name'] for n in nodes):
        return nodes,{'status':'no-floor-evidence'}
    p=points[valid];pixels=np.stack((xx[valid],yy[valid]),-1)
    if len(p)<100:return nodes,{'status':'insufficient-depth'}
    seed=np.median([(n['box']['min'][1]+n['box']['max'][1])/2 for n in floors]) if floors else np.percentile(p[:,1],20)
    rng=np.random.default_rng(42);best=None
    seed_points=[]
    for n in floors:
        if n.get('mask'):
            m=np.asarray(Image.open(directory/n['mask']))>0
            seed_points.extend(points[m[yy,xx]&valid].tolist())
    seed_points=np.asarray(seed_points)
    for iteration in range(1200):
        pool=seed_points if len(seed_points)>3 and iteration%2==0 else p
        sample=pool[rng.choice(len(pool),3,replace=False)]
        normal=np.cross(sample[1]-sample[0],sample[2]-sample[0]);length=np.linalg.norm(normal)
        if length<1e-8 or abs(normal[1])/length<.995:continue
        normal/=length
        if normal[1]<0:normal=-normal
        d=-sample[0]@normal
        if len(seed_points):
            if np.median(abs(seed_points@normal+d))>.05:continue
        elif abs(-d/normal[1]-seed)>max(.2,abs(seed)*.25):continue
        mask=np.abs(p@normal+d)<.045
        if best is None or mask.sum()>best[0]:best=(int(mask.sum()),mask)
    if best is None or best[0]<100:return nodes,{'status':'no-supported-horizontal-plane'}
    inliers=p[best[1]];fit=np.linalg.lstsq(np.c_[inliers[:,0],inliers[:,2],np.ones(len(inliers))],inliers[:,1],rcond=None)[0]
    normal=np.array([-fit[0],1,-fit[1]]);normal/=np.linalg.norm(normal)
    residual=np.abs(p[:,1]-(p[:,0]*fit[0]+p[:,2]*fit[1]+fit[2]))
    accepted=residual<.05;inliers=p[accepted];uv=pixels[accepted]
    floor=max(floors,key=lambda n:n.get('mask_pixels',0)) if floors else {'id':'floor-ransac','name':'floor','label':'바닥 #RANSAC','source':'depth-ransac','score':None}
    old=floor.get('box');lo=np.percentile(inliers,1,axis=0);hi=np.percentile(inliers,99,axis=0)
    floor['box']={'min':lo.tolist(),'max':hi.tolist()}
    floor['bbox2d']=[int(uv[:,0].min()),int(uv[:,1].min()),int(uv[:,0].max()+1),int(uv[:,1].max()+1)]
    floor['plane']={'normal':normal.tolist(),'offset':float(-fit[2]*normal[1]),'height_coefficients':fit.tolist(),'inliers':len(inliers),'tolerance_m':.05}
    floor['previous_visible_box']=old;floor['box_extent']='ransac-observed-floor-inliers'
    if floor not in nodes:nodes.append(floor)
    full_y,full_x=np.mgrid[:h,:w];X=(full_x-camera['cx'])*depth/camera['fx'];Y=-(full_y-camera['cy'])*depth/camera['fy']
    mask=(abs(Y-(fit[0]*X-fit[1]*depth+fit[2]))<.05)&(full_y>h*.5)&np.isfinite(depth)
    Image.fromarray(mask.astype(np.uint8)*255).save(directory/'floor-ransac.png')
    floor['sam_mask']=floor.get('mask');floor['mask']='floor-ransac.png';floor['mask_pixels']=int(mask.sum())
    # Multi-level interiors need observed landings as well as the lowest plane.
    # Exclude foreground masks so a tabletop cannot become a second floor.
    if not floors:
        eligible=residual>.12
        for n in nodes:
            if n.get('mask') and n['name'] not in ('floor','ground','road','pavement','wall','staircase'):
                m=np.asarray(Image.open(directory/n['mask']))>0
                eligible &= ~m[pixels[:,1],pixels[:,0]]
        for level in range(2):
            pool=p[eligible]
            if len(pool)<100:break
            best_level=None
            for _ in range(600):
                sample=pool[rng.choice(len(pool),3,replace=False)]
                normal=np.cross(sample[1]-sample[0],sample[2]-sample[0]);length=np.linalg.norm(normal)
                if length<1e-8 or abs(normal[1])/length<.995:continue
                normal/=length;d=-sample[0]@normal
                selected=eligible&(abs(p@normal+d)<.045)
                if best_level is None or selected.sum()>best_level.sum():best_level=selected
            if best_level is None or best_level.sum()<100:break
            q=p[best_level];uv=pixels[best_level]
            coefficients=np.linalg.lstsq(np.c_[q[:,0],q[:,2],np.ones(len(q))],q[:,1],rcond=None)[0]
            nid=f'floor-landing-{level}';m=(abs(Y-(coefficients[0]*X-coefficients[1]*depth+coefficients[2]))<.05)&(full_y>h*.45)&np.isfinite(depth)
            Image.fromarray(m.astype(np.uint8)*255).save(directory/(nid+'.png'))
            nodes.append({'id':nid,'name':'floor','label':f'층계참 바닥 #{level+1}','source':'depth-ransac','score':None,
                'mask':nid+'.png','mask_pixels':int(m.sum()),'bbox2d':[int(uv[:,0].min()),int(uv[:,1].min()),int(uv[:,0].max()+1),int(uv[:,1].max()+1)],
                'box':{'min':np.percentile(q,1,axis=0).tolist(),'max':np.percentile(q,99,axis=0).tolist()},
                'plane':{'height_coefficients':coefficients.tolist(),'inliers':len(q),'tolerance_m':.05},'box_extent':'ransac-observed-landing-inliers'})
            eligible &= abs(p[:,1]-(p[:,0]*coefficients[0]+p[:,2]*coefficients[1]+coefficients[2]))>.12
    return nodes,{'status':'estimated','node':floor['id'],'inliers':len(inliers),'plane':floor['plane'],'hidden_supports_completed':False}

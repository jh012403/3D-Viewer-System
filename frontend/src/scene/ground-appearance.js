import * as THREE from 'three';
function hull(points){
 const p=points.sort((a,b)=>a[0]-b[0]||a[1]-b[1]),cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 const half=ps=>{const h=[];for(const v of ps){while(h.length>1&&cross(h.at(-2),h.at(-1),v)<=0)h.pop();h.push(v);}return h;};
 return [...half(p).slice(0,-1),...half([...p].reverse()).slice(0,-1)];
}
export function updateFootprint(p,item){
 const key=item.object.matrixWorld.elements.join(',')+item.supportPoint.toArray().join(',');
 if(item.shadowKey===key)return;item.shadowKey=key;
 const up=p.up,x=p.gravity?.x||new THREE.Vector3(1,0,0),y=new THREE.Vector3().crossVectors(up,x).normalize();
 item.object.updateMatrixWorld(true);
 const vertices=item.localVertices.map(v=>v.clone().applyMatrix4(item.object.matrixWorld));
 const levels=vertices.map(v=>v.dot(up)).sort((a,b)=>a-b),cut=levels[Math.floor(levels.length*.02)]+.008;
 const bottom=vertices.filter(v=>v.dot(up)<=cut),polygon=hull(bottom.map(v=>[v.dot(x),v.dot(y)]));
 if(polygon.length<3)return;
 const minX=Math.min(...polygon.map(v=>v[0])),maxX=Math.max(...polygon.map(v=>v[0])),minY=Math.min(...polygon.map(v=>v[1])),maxY=Math.max(...polygon.map(v=>v[1]));
 const w=maxX-minX+.18,h=maxY-minY+.18,cx=(minX+maxX)/2,cy=(minY+maxY)/2,canvas=item.shadow.material.map.image,ctx=canvas.getContext('2d'),N=canvas.width;
 ctx.clearRect(0,0,N,N);
 const rgb=(p.floorColor||[110,107,100]).map(c=>Math.round(c*.35));
 const draw=(blur,alpha,dx,dy)=>{ctx.save();ctx.filter=`blur(${blur}px)`;ctx.fillStyle=`rgba(${rgb.join(',')},${alpha})`;ctx.beginPath();polygon.forEach(([a,b],i)=>{const u=(.5+(a-cx+dx)/w)*N,v=(.5-(b-cy+dy)/h)*N;i?ctx.lineTo(u,v):ctx.moveTo(u,v);});ctx.closePath();ctx.fill();ctx.restore();};
 // Photo light comes from camera upper right; the broad layer trails left/back.
 draw(12,.22,-.025,-.018);draw(2.2,.58,0,0);
 item.shadow.material.map.needsUpdate=true;
 item.shadow.position.copy(x).multiplyScalar(cx).addScaledVector(y,cy).addScaledVector(up,item.supportPoint.dot(up)+.003);
 item.shadow.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,up));item.shadow.scale.set(w,h,1);
 item.shadow.visible=true;
 item.shadowAudit={method:'projected lower-2-percent convex contour',contact_opacity:.58,ambient_opacity:.22,color:rgb,offset_m:[-.025,-.018],bottom_vertices:bottom.length};
}
function mean(data){
 const sum=[0,0,0];let n=0;
 for(let i=0;i<data.length;i+=4){if(data[i+3]<128||Math.max(data[i],data[i+1],data[i+2])<25)continue;for(let k=0;k<3;k++)sum[k]+=data[i+k];n++;}
 return sum.map(v=>v/Math.max(1,n));
}
export async function sampleScene(p){
 const image=new Image();image.src=new URL(p.v.manifest.source,p.v.base).href;await image.decode();
 const c=document.createElement('canvas');c.width=p.baseGraph.camera.width;c.height=p.baseGraph.camera.height;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,c.width,c.height);
 const sample=node=>{if(!node?.bbox2d)return null;const[a,b,x,y]=node.bbox2d;return mean(ctx.getImageData(a,b,x-a,y-b).data);};
 p.floorColor=sample(p.baseNodes.find(n=>n.id===p.gravity?.floorId));
 p.cartonColor=sample(p.baseNodes.find(n=>/^(cartons|cardboard boxes)$/.test(n.id)||/cardboard/.test(n.name)));
}
export function matchCarton(p,item){
 if(!p.cartonColor||!/box|carton|상자/i.test(item.name+' '+item.asset.name+' '+item.asset.specification?.kind))return;
 const records=[];
 item.object.traverse(mesh=>{
  for(const m of Array.isArray(mesh.material)?mesh.material:[mesh.material]){
   if(!m?.map?.image||!m.color)continue;
   const input=m.map,canvas=document.createElement('canvas'),image=input.image;
   canvas.width=Math.min(768,image.width);canvas.height=Math.max(1,Math.round(image.height*canvas.width/image.width));
   const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.filter='blur(0.45px)';ctx.drawImage(image,0,0,canvas.width,canvas.height);ctx.filter='none';
   const data=ctx.getImageData(0,0,canvas.width,canvas.height),source=mean(data.data),target=p.cartonColor;
   const lum=a=>.2126*a[0]+.7152*a[1]+.0722*a[2],gain=THREE.MathUtils.clamp(lum(target)/lum(source),.65,1.3);
   const temperature=target.map((v,k)=>THREE.MathUtils.clamp((v/lum(target))/(source[k]/lum(source)),.8,1.2));
   const saturation=THREE.MathUtils.clamp((Math.max(...target)-Math.min(...target))/Math.max(1,Math.max(...source)-Math.min(...source)),.6,1.15);
   for(let i=0;i<data.data.length;i+=4){const l=lum([data.data[i],data.data[i+1],data.data[i+2]]);for(let k=0;k<3;k++)data.data[i+k]=THREE.MathUtils.clamp((l+(data.data[i+k]-l)*saturation)*gain*temperature[k],0,255);}
   ctx.putImageData(data,0,0);m.map=input.clone();m.map.image=canvas;m.map.needsUpdate=true;
   // Bake a subtle bottom gradient into vertex colors, keeping the texture/UVs.
   const pos=mesh.geometry?.attributes.position;
   if(pos){let min=Infinity,max=-Infinity;for(let i=0;i<pos.count;i++){min=Math.min(min,pos.getY(i));max=Math.max(max,pos.getY(i));}
    const colors=new Float32Array(pos.count*3);for(let i=0;i<pos.count;i++){const t=(pos.getY(i)-min)/Math.max(.0001,max-min),shade=.86+.14*THREE.MathUtils.smoothstep(t,0,.55);colors.set([shade,shade,shade],i*3);}
    mesh.geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));m.vertexColors=true;
   }
   // The scene's 2+2 fill/key rig otherwise doubles the photographic albedo.
   m.color.multiplyScalar(.52);m.roughness=1;m.metalness=0;
   m.needsUpdate=true;records.push({source_mean_rgb:source,target_mean_rgb:target,exposure_gain:gain,lighting_compensation:.52,temperature_rgb:temperature,saturation,texture_size:[canvas.width,canvas.height],blur_pixels:.45});
  }
 });
 item.toneAudit={reference:'scene cardboard asset bbox; bounded RGB mean matching',materials:records};
}

import * as THREE from 'three';
import './amr.css';

function convexHull(points){
 const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 const half=ps=>{const h=[];for(const p of ps){while(h.length>1&&cross(h.at(-2),h.at(-1),p)<=0)h.pop();h.push(p);}return h;};
 const sorted=points.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
 return [...half(sorted).slice(0,-1),...half([...sorted].reverse()).slice(0,-1)];
}
export function polygonDistance(point,polygon){
 let inside=false,distance=Infinity;
 for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
  const a=polygon[j],b=polygon[i];
  if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
  const dx=b[0]-a[0],dy=b[1]-a[1],t=THREE.MathUtils.clamp(((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy||1),0,1);
  distance=Math.min(distance,Math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy));
 }
 return inside?0:distance;
}
function footprint(box,g){
 const points=[];
 for(const x of [box.min[0],box.max[0]])for(const y of [box.min[1],box.max[1]])for(const z of [box.min[2],box.max[2]]){
  const p=new THREE.Vector3(x,y,z);points.push([p.dot(g.x),p.dot(g.z)]);
 }
 return convexHull(points);
}
export function floorCells(geometry,graph,g,step=.06){
 if(!g)return [];
 const floor=graph.nodes.find(n=>n.id===g.floorId),b=floor?.bbox2d,c=graph.camera;
 if(!b)return [];
 const pixels=new Map(),positions=geometry.attributes.position;
 for(let i=0;i<positions.count;i++){
  const p=new THREE.Vector3().fromBufferAttribute(positions,i),u=c.fx*p.x/-p.z+c.cx,v=c.cy-c.fy*p.y/-p.z;
  if(u>=b[0]&&u<=b[2]&&v>=b[1]&&v<=b[3])pixels.set(`${Math.round(u/5)},${Math.round(v/5)}`,Math.abs(g.plane.distanceToPoint(p)));
 }
 const corners=[[b[0]+8,b[1]+8],[b[2]-8,b[1]+8],[b[2]-8,b[3]-8],[b[0]+8,b[3]-8]].map(([u,v])=>{
  const ray=new THREE.Ray(new THREE.Vector3(),new THREE.Vector3((u-c.cx)/c.fx,-(v-c.cy)/c.fy,-1).normalize());
  return ray.intersectPlane(g.plane,new THREE.Vector3());
 });
 if(corners.some(p=>!p))return [];
 const polygon=corners.map(p=>[p.dot(g.x),p.dot(g.z)]),origin=g.plane.coplanarPoint(new THREE.Vector3()),cells=[];
 const minX=Math.min(...polygon.map(p=>p[0])),maxX=Math.max(...polygon.map(p=>p[0])),minZ=Math.min(...polygon.map(p=>p[1])),maxZ=Math.max(...polygon.map(p=>p[1]));
 for(let x=Math.ceil(minX/step)*step;x<maxX;x+=step)for(let z=Math.ceil(minZ/step)*step;z<maxZ;z+=step){
  const point=origin.clone().addScaledVector(g.x,x).addScaledVector(g.z,z),u=c.fx*point.x/-point.z+c.cx,v=c.cy-c.fy*point.y/-point.z;
  if(u<b[0]+8||u>b[2]-8||v<b[1]+8||v>b[3]-8)continue;
  if(polygonDistance([x,z],polygon)>1e-8)continue;
  // Only observed depth agreeing with the fitted floor. Unobserved space stays blank.
  const residual=pixels.get(`${Math.round(u/5)},${Math.round(v/5)}`);
  if(residual===undefined||residual>.04)continue;
  // Keep the complete cell inside the observed floor region.
  if([[-1,-1],[-1,1],[1,-1],[1,1]].some(([a,b])=>polygonDistance([x+a*step/2,z+b*step/2],polygon)>1e-8))continue;
  cells.push({point,x,z,residual});
 }
 return cells;
}
export function classifyCells(cells,nodes,g,clearance){
 const obstacles=nodes.filter(n=>n.box&&n.id!==g.floorId&&n.source!=='depth-surface').map(n=>({id:n.id,polygon:footprint(n.box,g)}));
 return cells.map(cell=>({...cell,excluded:obstacles.some(o=>polygonDistance([cell.x,cell.z],o.polygon)<=clearance)}));
}

export class AMRAreas{
 constructor(v){
  this.v=v;this.p=v.placement;this.enabled=false;this.clearance=.5;this.step=.06;
  this.button=document.createElement('button');this.button.id='toggleAmr';this.button.textContent='AMR 영역';this.button.disabled=true;
  document.querySelector('.toolbar>div:last-child').append(this.button);
  this.panel=document.createElement('section');this.panel.id='amrPanel';this.panel.hidden=true;
  this.panel.innerHTML='<div class="amr-heading"><strong>AMR 주행 영역</strong><small>시뮬레이션</small></div><div class="amr-legend"><span class="candidate">주행 후보</span><span class="excluded">이격 제외</span></div><label>자산 이격 거리 <input id="amrClearance" type="number" min="0" max="2" step="0.1" value="0.5"> m</label><p id="amrSummary"></p><small>확인된 바닥 영역 · 사진 기반 추정</small>';
  v.container.append(this.panel);
  this.button.onclick=()=>{this.enabled=!this.enabled;this.panel.hidden=!this.enabled;this.button.classList.toggle('active',this.enabled);this.button.setAttribute('aria-pressed',String(this.enabled));if(this.mesh)this.mesh.visible=this.enabled;this.signature='';this.refresh();};
  this.panel.querySelector('input').onchange=e=>{const value=Number(e.target.value);this.clearance=Number.isFinite(value)?THREE.MathUtils.clamp(value,0,2):.5;e.target.value=this.clearance;this.signature='';this.refresh();};
  const oldLoad=this.p.loadGraph.bind(this.p);this.p.loadGraph=async(...args)=>{await oldLoad(...args);this.clear();this.cells=floorCells(this.v.surface.geometry,this.p.baseGraph,this.p.gravity,this.step);this.button.disabled=!this.cells.length;this.button.title=this.cells.length?'확인된 바닥의 주행 후보와 자산 이격 제외 영역':'확인된 바닥이 있는 장면에서 사용할 수 있습니다';this.refresh();};
  const oldRender=this.p.render.bind(this.p);this.p.render=()=>{if(this.enabled)this.refresh();oldRender();};
 }
 clear(){if(this.mesh){this.p.objects.remove(this.mesh);this.mesh.geometry.dispose();this.mesh.material.dispose();this.mesh.dispose();this.mesh=null;}this.signature='';this.audit=null;this.enabled=false;this.panel.hidden=true;this.button.classList.remove('active');this.button.setAttribute('aria-pressed','false');}
 refresh(){
  if(!this.enabled||!this.p.gravity||!this.cells?.length)return;
  const nodes=this.p.graph.nodes.filter(n=>n.asset_id),draft=this.v.simulation.draft;
  if(draft){const box=new THREE.Box3().setFromObject(draft.object);nodes.push({id:draft.id,box:{min:box.min.toArray(),max:box.max.toArray()}});}
  const signature=JSON.stringify([this.clearance,nodes.map(n=>[n.id,n.box])]);
  if(signature===this.signature)return;this.signature=signature;
  const cells=classifyCells(this.cells,nodes,this.p.gravity,this.clearance);
  if(!this.mesh){
   const material=new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.35,depthWrite:false,side:THREE.DoubleSide});this.p.softenOcclusion(material);
   this.mesh=new THREE.InstancedMesh(new THREE.PlaneGeometry(this.step*.94,this.step*.94),material,cells.length);this.mesh.renderOrder=-3;this.mesh.frustumCulled=false;this.p.objects.add(this.mesh);
  }
  const q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,0,1),this.p.up),matrix=new THREE.Matrix4(),scale=new THREE.Vector3(1,1,1);
  cells.forEach((c,i)=>{matrix.compose(c.point.clone().addScaledVector(this.p.up,.006),q,scale);this.mesh.setMatrixAt(i,matrix);this.mesh.setColorAt(i,new THREE.Color(c.excluded?'#ff615d':'#35dca6'));});
  this.mesh.instanceMatrix.needsUpdate=true;this.mesh.instanceColor.needsUpdate=true;this.mesh.visible=true;
  const excluded=cells.filter(c=>c.excluded).length;
  this.audit={scene:this.v.manifest.id,simulation:true,scope:'observed floor candidate cells; no robot footprint or route feasibility certification',cell_size_m:this.step,clearance_m:this.clearance,cells:cells.length,candidate_cells:cells.length-excluded,excluded_cells:excluded,obstacles:nodes.filter(n=>n.id!==this.p.gravity.floorId).map(n=>n.id),floor_up:this.p.up.toArray()};
  this.panel.querySelector('#amrSummary').textContent=`주행 후보 약 ${((cells.length-excluded)*this.step**2).toFixed(2)}m² · 제외 약 ${(excluded*this.step**2).toFixed(2)}m²`;
 }
}

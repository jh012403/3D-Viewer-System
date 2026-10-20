import * as THREE from 'three';
const median=a=>[...a].sort((a,b)=>a-b)[Math.floor(a.length/2)];
function orthogonalFit(points){
 const center=new THREE.Vector3();for(const p of points)center.add(p);center.divideScalar(points.length);
 const a=Array.from({length:3},()=>[0,0,0]),v=[[1,0,0],[0,1,0],[0,0,1]];
 for(const point of points){const d=point.clone().sub(center).toArray();for(let i=0;i<3;i++)for(let j=0;j<3;j++)a[i][j]+=d[i]*d[j];}
 // Jacobi diagonalization of the symmetric covariance matrix.
 for(let step=0;step<32;step++){
  let p=0,q=1;for(const [i,j]of [[0,2],[1,2]])if(Math.abs(a[i][j])>Math.abs(a[p][q])){p=i;q=j;}
  if(Math.abs(a[p][q])<1e-12)break;
  const angle=.5*Math.atan2(2*a[p][q],a[q][q]-a[p][p]),c=Math.cos(angle),s=Math.sin(angle);
  const app=a[p][p],aqq=a[q][q],apq=a[p][q];
  for(let k=0;k<3;k++)if(k!==p&&k!==q){const x=a[k][p],y=a[k][q];a[k][p]=a[p][k]=c*x-s*y;a[k][q]=a[q][k]=s*x+c*y;}
  a[p][p]=c*c*app-2*s*c*apq+s*s*aqq;a[q][q]=s*s*app+2*s*c*apq+c*c*aqq;a[p][q]=a[q][p]=0;
  for(let k=0;k<3;k++){const x=v[k][p],y=v[k][q];v[k][p]=c*x-s*y;v[k][q]=s*x+c*y;}
 }
 const k=[0,1,2].sort((i,j)=>a[i][i]-a[j][j])[0],normal=new THREE.Vector3(v[0][k],v[1][k],v[2][k]).normalize();
 // Choose the half-space containing the camera, not a camera-vertical direction.
 if(normal.dot(center)>0)normal.negate();
 return {center,normal,constant:-normal.dot(center)};
}
export function fitSceneGravity(geometry,graph){
 const floor=graph.nodes.find(n=>n.asset_id==='EQ-0001'&&/floor|바닥|ground/i.test(n.name+' '+n.label))
  ||graph.nodes.find(n=>/^(floor|ground|바닥)$/.test(n.name));
 if(!floor?.bbox2d)return null;
 const c=graph.camera,b=floor.bbox2d,p=geometry.attributes.position,points=[];
 for(let i=0;i<p.count;i++){const point=new THREE.Vector3().fromBufferAttribute(p,i),z=-point.z;if(z<=0)continue;
  const u=c.fx*point.x/z+c.cx,v=c.cy-c.fy*point.y/z;
  if(u>b[0]+8&&u<b[2]-8&&v>b[1]+8&&v<b[3]-8)points.push(point);
 }
 if(points.length<30)return null;
 let selected=points,fit;
 for(let i=0;i<5;i++){fit=orthogonalFit(selected);const residual=points.map(p=>Math.abs(p.dot(fit.normal)+fit.constant)),limit=Math.max(.008,2.8*median(residual));selected=points.filter((p,i)=>residual[i]<=limit);if(selected.length<30)return null;}
 fit=orthogonalFit(selected);
 const up=fit.normal,plane=new THREE.Plane(up,fit.constant),x=new THREE.Vector3(1,0,0).projectOnPlane(up).normalize(),z=new THREE.Vector3().crossVectors(x,up).normalize();
 return {up,plane,x,z,floorId:floor.id,audit:{method:'floor-ROI trimmed orthogonal least squares',asset_id:floor.asset_id,points:points.length,inliers:selected.length,normal:up.toArray(),constant:fit.constant,rms_m:Math.sqrt(selected.reduce((s,p)=>s+plane.distanceToPoint(p)**2,0)/selected.length),camera_vertical_angle_degrees:THREE.MathUtils.radToDeg(up.angleTo(new THREE.Vector3(0,1,0)))}};
}

export function objectVertices(object){
 object.updateMatrixWorld(true);const inverse=object.matrixWorld.clone().invert(),points=[];
 object.traverse(n=>{const p=n.geometry?.attributes.position;if(!p)return;const matrix=inverse.clone().multiply(n.matrixWorld);for(let i=0;i<p.count;i++)points.push(new THREE.Vector3().fromBufferAttribute(p,i).applyMatrix4(matrix));});
 return points;
}
export function projectedBounds(item,up){
 item.object.updateMatrixWorld(true);
 const m=item.object.matrixWorld.elements,coeff=[0,4,8].map(i=>m[i]*up.x+m[i+1]*up.y+m[i+2]*up.z),key=coeff.join(',');
 if(item.heightKey!==key){const heights=item.localVertices.map(p=>p.x*coeff[0]+p.y*coeff[1]+p.z*coeff[2]).sort((a,b)=>a-b);
  item.heightKey=key;item.heightBounds={bottom:heights[Math.floor((heights.length-1)*.02)],min:heights[0],top:heights.at(-1)};
 }
 const offset=m[12]*up.x+m[13]*up.y+m[14]*up.z;
 return Object.fromEntries(Object.entries(item.heightBounds).map(([k,v])=>[k,v+offset]));
}

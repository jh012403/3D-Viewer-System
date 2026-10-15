// All axes are in the fixed original camera frame, in meters.
export function relations(nodes){
  const edges=[], add=(a,b,relation)=>edges.push({source:a.id,target:b.id,relation,method:'3d-aabb'});
  const overlap=(a,b,k)=>Math.max(0,Math.min(a.max[k],b.max[k])-Math.max(a.min[k],b.min[k]));
  for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
    const a=nodes[i],b=nodes[j];if(!a.box||!b.box)continue;
    const A=a.box,B=b.box,t=.04;
    const footprint=overlap(A,B,0)*overlap(A,B,2);
    const minArea=Math.min((A.max[0]-A.min[0])*(A.max[2]-A.min[2]),(B.max[0]-B.min[0])*(B.max[2]-B.min[2]));
    const supported=footprint/Math.max(minArea,1e-6)>.25;
    if(supported&&Math.abs(A.min[1]-B.max[1])<t){add(a,b,'on');add(b,a,'under');}
    else if(supported&&Math.abs(B.min[1]-A.max[1])<t){add(b,a,'on');add(a,b,'under');}
    else if(supported&&A.max[1]<B.min[1]-t)add(a,b,'under');
    else if(supported&&B.max[1]<A.min[1]-t)add(b,a,'under');
    if(A.max[0]<B.min[0]-t){add(a,b,'left of');add(b,a,'right of');}
    else if(B.max[0]<A.min[0]-t){add(b,a,'left of');add(a,b,'right of');}
    if(A.min[2]>B.max[2]+t){add(a,b,'in front of');add(b,a,'behind');}
    else if(B.min[2]>A.max[2]+t){add(b,a,'in front of');add(a,b,'behind');}
    const dx=Math.max(0,A.min[0]-B.max[0],B.min[0]-A.max[0]);
    const dz=Math.max(0,A.min[2]-B.max[2],B.min[2]-A.max[2]);
    if(Math.hypot(dx,dz)>.04&&Math.hypot(dx,dz)<.5&&overlap(A,B,1)>.05){add(a,b,'next to');add(b,a,'next to');}
  }
  return edges;
}

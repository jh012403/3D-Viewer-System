// All axes are in the fixed original camera frame, in meters.
export function relationCandidates(nodes){
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

export const RELATION_POLICY='nearest-support-neighbors-v2';
const priority=r=>({on:0,under:1,'next to':2,'left of':3,'right of':3,'in front of':3,behind:3}[r]??9);
const distance=(a,b)=>Math.hypot(...[0,1,2].map(k=>Math.max(0,a.box.min[k]-b.box.max[k],b.box.min[k]-a.box.max[k])));
const centerDistance=(a,b)=>Math.hypot(...[0,1,2].map(k=>(a.box.min[k]+a.box.max[k]-b.box.min[k]-b.box.max[k])/2));
const pairKey=e=>[e.source,e.target].sort().join('|');
// Persist a sparse graph, not a display filter. Inverse predicates are redundant
// facts about the same unordered pair and are not stored twice.
export function pruneRelations(nodes,candidates){
  const byId=new Map(nodes.map(n=>[n.id,n])),support=new Map();
  const valid=candidates.filter(e=>e.source!==e.target&&byId.get(e.source)?.box&&byId.get(e.target)?.box);
  const gap=e=>Math.abs(byId.get(e.source).box.min[1]-byId.get(e.target).box.max[1]);
  const on=valid.filter(e=>e.relation==='on').sort((a,b)=>
    (a.method==='raycast-support-contact'?0:1)-(b.method==='raycast-support-contact'?0:1)||gap(a)-gap(b)||
    centerDistance(byId.get(a.source),byId.get(a.target))-centerDistance(byId.get(b.source),byId.get(b.target))||a.target.localeCompare(b.target));
  for(const e of on)if(!support.has(e.source))support.set(e.source,e);
  const chosen=[...support.values()],used=new Set(chosen.map(pairKey));
  // Local neighbor selection is based on geometry, independent of class names.
  const availablePairs=new Set(valid.filter(e=>e.relation!=='on'&&!used.has(pairKey(e))).map(pairKey));
  const local=new Map(nodes.filter(n=>n.box).map(a=>[a.id,new Set(nodes.filter(b=>b.box&&b.id!==a.id&&availablePairs.has([a.id,b.id].sort().join('|')))
    .sort((b,c)=>distance(a,b)-distance(a,c)||centerDistance(a,b)-centerDistance(a,c)||b.id.localeCompare(c.id)).slice(0,3).map(n=>n.id))]));
  const sameCategoryClose=e=>{
    const a=byId.get(e.source),b=byId.get(e.target);
    if((a.name||'').toLowerCase()!==(b.name||'').toLowerCase())return true;
    const extent=n=>Math.hypot(...[0,1,2].map(k=>n.box.max[k]-n.box.min[k]));
    return distance(a,b)<=Math.min(.75,.5*Math.min(extent(a),extent(b)));
  };
  const canonical=e=>{
    if(e.relation==='right of')return {...e,source:e.target,target:e.source,relation:'left of'};
    if(e.relation==='behind')return {...e,source:e.target,target:e.source,relation:'in front of'};
    if(e.relation==='next to'&&e.source>e.target)return {...e,source:e.target,target:e.source};
    return e;
  };
  const rest=valid.filter(e=>e.relation!=='on'&&local.get(e.source)?.has(e.target)&&local.get(e.target)?.has(e.source)&&sameCategoryClose(e))
    .map(canonical).sort((a,b)=>priority(a.relation)-priority(b.relation)||distance(byId.get(a.source),byId.get(a.target))-distance(byId.get(b.source),byId.get(b.target))||a.source.localeCompare(b.source)||a.target.localeCompare(b.target));
  for(const e of rest){const key=pairKey(e);if(used.has(key))continue;used.add(key);chosen.push(e);}
  // Remove same-predicate facts implied by a path of length >=2.
  // next to is intentionally excluded: adjacency is not transitive.
  const result=chosen.filter(edge=>{
    if(edge.relation==='next to')return true;
    const seen=new Set([edge.source]),stack=[edge.source];
    while(stack.length){const id=stack.pop();for(const other of chosen){
      if(other===edge||other.relation!==edge.relation||other.source!==id)continue;
      if(other.target===edge.target)return false;
      if(!seen.has(other.target)){seen.add(other.target);stack.push(other.target);}
    }}return true;
  });
  return result.map(e=>({...e,pruning_policy:RELATION_POLICY}));
}
export function relations(nodes,contactEdges=[]){return pruneRelations(nodes,[...relationCandidates(nodes),...contactEdges]);}

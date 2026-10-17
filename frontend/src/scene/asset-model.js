const round=x=>Math.round(x*1000)/1000;
export function categoryOf(n){
 if(['설비','적재물','공구','구조물','기타'].includes(n.category))return n.category;
 const s=(n.name+' '+(n.asset?.category||'')).toLowerCase();
 if(/floor|wall|ceiling|column|table|shelf|rack|door|rail|platform/.test(s))return '구조물';
 if(/machine|truck|microscope|instrument|motor|printer|computer/.test(s))return '설비';
 if(/box|carton|pallet|container|crate/.test(s))return '적재물';
 if(/tool|clamp|beaker|flask|tray|tweezer/.test(s))return '공구';return '기타';
}
export function boxDistance(a,b){return Math.hypot(...[0,1,2].map(i=>Math.max(0,a.min[i]-b.max[i],b.min[i]-a.max[i])));}
export function zoneOf(box,zones=[]){
 const x=(box.min[0]+box.max[0])/2,z=(box.min[2]+box.max[2])/2;
 const containing=zones.filter(v=>x>=v.bounds.min[0]&&x<=v.bounds.max[0]&&z>=v.bounds.min[2]&&z<=v.bounds.max[2]);
 if(containing.length)return containing.at(-1).id;
 return zones.slice().sort((a,b)=>Math.hypot(x-(a.bounds.min[0]+a.bounds.max[0])/2,z-(a.bounds.min[2]+a.bounds.max[2])/2)-Math.hypot(x-(b.bounds.min[0]+b.bounds.max[0])/2,z-(b.bounds.min[2]+b.bounds.max[2])/2))[0]?.id||'미지정';
}
export function enrichAssets(graph,registry){
 for(const n of graph.nodes){
  if(n.source==='depth-surface')continue;
  if(!registry.ids.has(n.id)){const id=n.asset_id||`EQ-${String(registry.next++).padStart(4,'0')}`;registry.ids.set(n.id,id);registry.next=Math.max(registry.next,Number(id.slice(3))+1);}
  const b=n.box,meta=n.asset?.specification||{},size=b?b.max.map((v,i)=>round(v-b.min[i])):[0,0,0];
  Object.assign(n,{asset_id:registry.ids.get(n.id),asset_name:n.label||n.name,classification:categoryOf(n),center_m:b?b.min.map((v,i)=>round((v+b.max[i])/2)):[0,0,0],dimensions_m:{width:size[0],depth:size[2],height:size[1]},zone:n.zone||zoneOf(b,graph.zones),status:n.status||'등록됨',registration_source:n.source==='placed-glb'?'신규 반입':'현장 인식',dimension_source:'단안 깊이 또는 메시 정규화 기반 추정',specification:{kind:meta.kind||n.name,materials:meta.materials||[],provider:meta.provider||'현장 큐레이션 / GLB',estimated_size_m:{width:size[0],depth:size[2],height:size[1]}}});
 }
 const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
 for(const e of graph.edges){e.operational_label=e.relation==='on'?'적재':e.relation==='next to'?'인접':e.relation==='attached to'?'부착':e.relation;e.distance_m=e.relation==='next to'&&nodes.get(e.source)?.box&&nodes.get(e.target)?.box?round(boxDistance(nodes.get(e.source).box,nodes.get(e.target).box)):null;}
 return graph;
}
export function assetRegister(graph){return {schema:'prism.asset-register/1.0',aas_style:true,aas_conformance_claim:false,scene_id:graph.scene_id,units:'m',geometry:'monocular-estimate',assets:graph.nodes.filter(n=>n.asset_id).map(n=>({id:n.asset_id,idShort:n.asset_id.replace('-','_'),assetInformation:{assetKind:'Instance',globalAssetId:`urn:prism:${graph.scene_id}:${n.asset_id}`},submodels:{identification:{name:n.asset_name,classification:n.classification,source:n.registration_source},technicalData:{center_m:n.center_m,dimensions_m:n.dimensions_m,dimension_source:n.dimension_source,specification:n.specification},operations:{zone:n.zone,status:n.status,status_source:'registration-workflow',sensor_data:false}}}))};}

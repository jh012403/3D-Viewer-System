import * as THREE from 'three';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {assetRegister} from './asset-model.js';
const $=s=>document.querySelector(s),escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
const jsonBlob=x=>new Blob([JSON.stringify(x,null,2)],{type:'application/json'});
const dataUrl=blob=>new Promise(resolve=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.readAsDataURL(blob);});
export class TwinExports{
 constructor(v){
  this.v=v;this.p=v.placement;const box=document.createElement('section');box.id='twinExports';box.innerHTML='<h3>디지털트윈 출력</h3><div class="controls"><button id="exportRegister">자산 대장 JSON</button><button id="exportRelations">관계 그래프 JSON</button><button id="exportGltf">자산 씬 glTF</button></div><button id="exportReport">배치 검토 리포트 · PDF</button><p class="muted">배경을 제외한 자산 씬과 AAS 스타일 대장을 저장합니다.</p>';$('#placement').append(box);
  const bind=(id,fn)=>$('#'+id).onclick=async()=>{try{this.ready();await fn();}catch(e){v.placement.status(e.message,true);}};
  bind('exportRegister',()=>download(jsonBlob(assetRegister(this.p.graph)),'asset-register.json'));
  bind('exportRelations',()=>download(jsonBlob(this.p.graph),'asset-relations.json'));
  bind('exportGltf',async()=>{download(jsonBlob(await this.gltf()),'asset-scene.gltf');this.p.status('배경을 제외한 자산 씬 glTF를 저장했습니다.');});
  $('#exportReport').onclick=async()=>{let popup;try{this.ready();popup=window.open('about:blank','_blank');if(!popup)throw Error('리포트 팝업을 허용해 주세요.');popup.document.write('<p>리포트 생성 중…</p>');const html=await this.report();popup.document.open();popup.document.write(html);popup.document.close();this.p.status('리포트에서 PDF 저장을 누르면 인쇄 창이 열립니다.');}catch(e){popup?.close();this.p.status(e.message,true);}};
  const oldExport=this.p.export.bind(this.p);this.p.export=async()=>{
   this.ready();this.v.hidePresentationOverlays=true;
   const overlays=[...(v.dashboard?.zoneObjects||[]),v.simulation?.helper,v.simulation?.safety].filter(Boolean),states=overlays.map(o=>o.visible);for(const o of overlays)o.visible=false;
   try{return await oldExport();}finally{this.v.hidePresentationOverlays=false;overlays.forEach((o,i)=>o.visible=states[i]);}
  };
 }
 ready(){if(!this.v.manifest)throw Error('현장을 먼저 선택하세요.');if(this.v.simulation?.draft)throw Error('반입 미리보기를 확정하거나 취소한 뒤 출력하세요.');}
 async gltf(){
  this.ready();const scene=new THREE.Scene(),made=[];scene.name=this.v.manifest.title;scene.userData={schema:'prism.digital-twin/1',scene_id:this.v.manifest.id,units:'meters',background_excluded:true,zones:this.p.graph.zones||[],asset_register:assetRegister(this.p.graph)};
  for(const n of this.p.graph.nodes.filter(n=>n.asset_id)){
   const item=this.p.items.find(i=>i.id===n.id);let object;
   if(item){object=item.object.clone(true);object.traverse(o=>{if(o.material){o.material=Array.isArray(o.material)?o.material.map(m=>m.clone()):o.material.clone();made.push(...(Array.isArray(o.material)?o.material:[o.material]));}});}
   else{const min=new THREE.Vector3(...n.box.min),max=new THREE.Vector3(...n.box.max),size=max.clone().sub(min);const geometry=new THREE.BoxGeometry(size.x,size.y,size.z),material=new THREE.MeshStandardMaterial({color:n.zone==='Zone A'?0x50bdd3:0xe8b85c,transparent:true,opacity:.25});made.push(geometry,material);object=new THREE.Mesh(geometry,material);object.position.copy(min.add(max).multiplyScalar(.5));}
   object.name=n.asset_id+' '+n.asset_name;object.userData={asset_id:n.asset_id,name:n.asset_name,classification:n.classification,zone:n.zone,status:n.status,registration_source:n.registration_source,dimensions_m:n.dimensions_m,specification:n.specification};scene.add(object);
  }
  try{return await new GLTFExporter().parseAsync(scene,{binary:false,onlyVisible:true});}finally{for(const r of made)r.dispose();}
 }
 async report(){
  this.ready();const exported=await this.p.export(),image=await dataUrl(exported.image),graph=exported.graph,register=assetRegister(graph),items=this.p.items;
  const checked=items.map(item=>({item,result:this.v.simulation.check(item)})),issues=checked.reduce((sum,r)=>sum+r.result.collisions.length+r.result.near.length,0);
  const rows=graph.nodes.filter(n=>n.asset_id).map(n=>`<tr class="${n.registration_source==='신규 반입'?'new':''}"><td>${escape(n.asset_id)}</td><td>${escape(n.asset_name)}</td><td>${escape(n.classification)}</td><td>${escape(n.zone)}</td><td>${[n.dimensions_m.width,n.dimensions_m.depth,n.dimensions_m.height].map(v=>v.toFixed(2)).join(' × ')}</td><td>${escape(n.registration_source)}</td></tr>`).join('');
  const specifications=items.map(i=>{const n=graph.nodes.find(n=>n.id===i.id),d=n.dimensions_m;return `${escape(n.asset_id)} ${escape(n.asset_name)} · ${escape(n.specification.kind)} · 재질 ${escape(n.specification.materials.join(', ')||'미확인')} · ${d.width.toFixed(2)} × ${d.depth.toFixed(2)} × ${d.height.toFixed(2)}m`;}).join('<br>')||'신규 반입 자산 없음';
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>PRISM 배치 검토 리포트</title><style>@page{size:A4;margin:12mm}*{box-sizing:border-box}body{font:11px 'Segoe UI','Malgun Gothic',sans-serif;color:#203445;margin:0;background:#edf2f6}.sheet{width:186mm;min-height:270mm;margin:20px auto;padding:8mm;background:white}header{display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #206a80;padding-bottom:12px}h1{font-size:24px;margin:0}h2{font-size:14px;margin:15px 0 8px}small{color:#66818f}.hero{width:100%;height:88mm;object-fit:contain;background:#10202d;margin-top:14px}.review{padding:12px;background:#edf7f8;border-left:4px solid #278b8e;line-height:1.8}.spec{font-size:10px;line-height:1.7}table{width:100%;border-collapse:collapse;font-size:9px}th,td{padding:7px 5px;text-align:left;border-bottom:1px solid #dce5eb}th{background:#e6eff4}.new{background:#e7f6ef}.note{font-size:9px;line-height:1.6;color:#63808f;margin-top:14px}.actions{text-align:center;padding:16px}button{background:#205e75;color:white;border:0;border-radius:4px;padding:12px 24px;cursor:pointer}@media print{body{background:white}.sheet{margin:0;padding:0;width:auto;min-height:0}.actions{display:none}}</style></head><body><div class="actions"><button onclick="window.print()">PDF 저장 / 인쇄</button></div><article class="sheet"><header><div><small>PRISM · DIGITAL TWIN</small><h1>신규 자산 배치 검토</h1></div><div>${escape(this.v.manifest.title)}<br><small>${escape(new Date().toLocaleString('ko-KR'))}</small></div></header><img class="hero" src="${image}" alt="원본 시점 현장 렌더"><h2>반입 검토 결과</h2><div class="review"><b>${issues?'검토 필요':'현재 검토 기준 충족'}</b> · 반입 ${items.length}개 / 간섭 ${checked.reduce((s,r)=>s+r.result.collisions.length,0)}건 / 이격 부족 ${checked.reduce((s,r)=>s+r.result.near.length,0)}건<br>선택 이격 기준 ${this.v.simulation.clearance.toFixed(2)}m · 추정 AABB 기반 검사</div><h2>반입 자산 사양</h2><div class="spec">${specifications}</div><h2>변경된 자산 대장 <small>${register.assets.length} assets · 녹색은 신규 반입</small></h2><table><thead><tr><th>ID</th><th>자산명</th><th>분류</th><th>구역</th><th>W × D × H (m)</th><th>출처</th></tr></thead><tbody>${rows}</tbody></table><p class="note">사진 기반 큐레이션 및 단안 추정 공간입니다. 크기·거리·점유율은 실측값이 아니며 현장 안전 인증을 대신하지 않습니다. ${items.some(i=>i.asset.demo)?'이번 반입 자산은 시연용으로 제작된 GLB입니다.':''}<br>AAS 스타일 자산 데이터이며 표준 적합성을 선언하지 않습니다. 배경 splat은 glTF 출력에서 제외됩니다.</p></article></body></html>`;
 }
}

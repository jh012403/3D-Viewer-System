import * as THREE from 'three';
const $=s=>document.querySelector(s);
function occupancy(nodes,zone){
 const b=zone.bounds,rects=nodes.filter(n=>n.classification!=='구조물').map(n=>[Math.max(b.min[0],n.box.min[0]),Math.min(b.max[0],n.box.max[0]),Math.max(b.min[2],n.box.min[2]),Math.min(b.max[2],n.box.max[2])]).filter(r=>r[1]>r[0]&&r[3]>r[2]);
 const xs=[...new Set(rects.flatMap(r=>r.slice(0,2)))].sort((a,b)=>a-b);let area=0;
 for(let i=1;i<xs.length;i++){const mid=(xs[i]+xs[i-1])/2,ys=rects.filter(r=>r[0]<=mid&&r[1]>=mid).map(r=>r.slice(2)).sort((a,b)=>a[0]-b[0]);let len=0,end=-Infinity;for(const[a,b]of ys){len+=Math.max(0,b-Math.max(a,end));end=Math.max(end,b);}area+=(xs[i]-xs[i-1])*len;}
 return Math.round(100*area/Math.max(.001,(b.max[0]-b.min[0])*(b.max[2]-b.min[2])));
}
export class TwinDashboard{
 constructor(v){
  this.v=v;this.p=v.placement;this.zoneObjects=[];
  document.body.classList.add('twin-shell');document.title='PRISM | Digital Twin Operations';
  $('.brand span').textContent='/ DIGITAL TWIN';$('.eyebrow').textContent='현장에서 자산으로, 자산에서 운영으로';$('.local').textContent='LOCAL · CONNECTED';
  $('.library h1').innerHTML='현장을<br>연결하세요.';$('.library .muted').textContent='사진 기반 공간 복원과 신규 자산 반입 검토';
  $('.library .section-label').textContent='01 / SITES';$('.library-bottom').textContent='PRISM OPERATIONS · LOCAL CACHE';
  const mesh=document.createElement('a');mesh.href='/prismscan-v2.html';mesh.className='mesh-link';mesh.textContent='사진 → 3D 메시 생성 ↗';mesh.target='_blank';$('header').insertBefore(mesh,$('.local'));
  const kpi=document.createElement('div');kpi.id='kpi';kpi.innerHTML='<div><small>등록 자산</small><strong id="kpiTotal">—</strong></div><div><small>구역 점유율 · 추정</small><strong id="kpiZones">—</strong></div><div><small>반입 간섭 / 이격 경고</small><strong id="kpiWarnings">0 / 0</strong></div><div><small>마지막 갱신</small><strong id="kpiTime">—</strong></div>';$('header').after(kpi);
  const tabs=$('.inspector-tabs');tabs.innerHTML='<button id="tabAssets" class="active">자산 대장</button><button id="tabGraph">관계 그래프</button><button id="tabEdit">배치</button>';
  this.ledger=document.createElement('section');this.ledger.id='assetLedger';tabs.after(this.ledger);
  for(const [id,panel]of [['tabAssets','assets'],['tabGraph','graph'],['tabEdit','edit']])$('#'+id).onclick=()=>this.tab(panel);
  this.tab('assets');
  const toggle=document.createElement('button');toggle.id='toggleIds';toggle.textContent='ID 라벨 켜짐';toggle.onclick=()=>{this.labels.hidden=!this.labels.hidden;toggle.textContent='ID 라벨 '+(this.labels.hidden?'꺼짐':'켜짐');};$('.toolbar>div:last-child').append(toggle);
  this.labels=document.createElement('div');this.labels.className='asset-id-layer';v.container.append(this.labels);
  const oldRender=this.p.render.bind(this.p);this.p.render=()=>{this.projectLabels();this.warningKpi();oldRender();};
  const oldLoad=this.p.loadGraph.bind(this.p);this.p.loadGraph=async(...args)=>{await oldLoad(...args);this.buildZones();this.render();$('#assetSpec')?.remove();};
  window.addEventListener('asset-register-changed',()=>this.render());
 }
 tab(panel){const inspector=$('.inspector');inspector.dataset.panel=panel;inspector.scrollTop=0;inspector.classList.toggle('graph-mode',panel==='graph');for(const id of ['tabAssets','tabGraph','tabEdit'])$('#'+id).classList.toggle('active',id===({assets:'tabAssets',graph:'tabGraph',edit:'tabEdit'}[panel]));this.v.resize?.();}
 render(){
  const graph=this.p.graph;if(!graph?.nodes)return;const nodes=graph.nodes.filter(n=>n.asset_id);
  $('#kpiTotal').textContent=String(nodes.length).padStart(2,'0');$('#kpiZones').textContent=(graph.zones||[]).map(z=>z.id.replace('Zone ','')+' '+occupancy(nodes,z)+'%').join(' / ')||'미지정';$('#kpiTime').textContent=new Date().toLocaleTimeString('ko-KR',{hour12:false});this.warningKpi();
  const old=new Set(this.ledger.querySelectorAll('[data-id]')?Array.from(this.ledger.querySelectorAll('[data-id]'),r=>r.dataset.id):[]);
  this.ledger.innerHTML='<div class="ledger-heading"><h2>현장 자산 대장</h2><span>ASSET REGISTER</span></div><p class="muted">행을 선택해 위치와 사양을 확인하세요.</p><div class="ledger-scroll"><table><thead><tr><th>ID · 자산</th><th>분류 / 구역</th><th>W×D×H (m)</th><th>상태</th></tr></thead><tbody></tbody></table></div><p class="ledger-note">좌표·크기·점유율은 사진 기반 추정값입니다.</p>';
  for(const n of nodes){const row=document.createElement('tr');row.dataset.id=n.id;row.tabIndex=0;row.classList.toggle('arriving',old.size>0&&!old.has(n.id));
   const d=n.dimensions_m;for(const value of [n.asset_id+'\n'+n.asset_name,n.classification+'\n'+n.zone,[d.width,d.depth,d.height].map(v=>v.toFixed(2)).join('×'),n.status]){const td=document.createElement('td');td.textContent=value;row.append(td);}
   row.onclick=()=>{const item=this.p.items.find(i=>i.id===n.id);if(item)this.p.select(item);this.p.highlight(n);};row.onkeydown=e=>{if(e.key==='Enter')row.click();};this.ledger.querySelector('tbody').append(row);
  }
  this.labels.replaceChildren();for(const n of nodes){const b=document.createElement('button');b.textContent=n.asset_id;b.dataset.id=n.id;b.onclick=()=>this.p.highlight(n);b.onmouseenter=()=>this.p.outline(n);b.onmouseleave=()=>this.p.outline(graph.nodes.find(n=>n.id===this.p.selectedGraphId));this.labels.append(b);}
 }
 warningKpi(){const s=this.v.simulation?.result;$('#kpiWarnings').textContent=`${s?.collisions.length||0} / ${s?.near.length||0}`;$('#kpiWarnings').className=s?.state==='collision'?'danger':s?.state==='clearance'?'warning':'';}
 projectLabels(){if(this.labels.hidden||!this.v.manifest)return;const rect=this.v.renderer.domElement.getBoundingClientRect(),container=this.v.container.getBoundingClientRect();
  for(const button of this.labels.children){const n=this.p.graph.nodes.find(n=>n.id===button.dataset.id);if(!n?.box)continue;const point=new THREE.Vector3((n.box.min[0]+n.box.max[0])/2,n.box.max[1],(n.box.min[2]+n.box.max[2])/2).project(this.v.camera);button.hidden=point.z>1||point.z<-1||Math.abs(point.x)>.96||Math.abs(point.y)>.94;button.style.left=(rect.left-container.left+(point.x+1)*rect.width/2)+'px';button.style.top=(rect.top-container.top+(1-point.y)*rect.height/2)+'px';}
 }
 buildZones(){for(const o of this.zoneObjects){this.p.objects.remove(o);o.geometry.dispose();o.material.dispose();}this.zoneObjects=[];
  for(const z of this.p.graph.zones||[]){const b=z.bounds,y=b.min[1]+.012;const pts=[[b.min[0],y,b.min[2]],[b.max[0],y,b.min[2]],[b.max[0],y,b.max[2]],[b.min[0],y,b.max[2]]].map(p=>new THREE.Vector3(...p));const line=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineDashedMaterial({color:z.color,transparent:true,opacity:.5,dashSize:.12,gapSize:.08,depthTest:false}));line.computeLineDistances();this.p.objects.add(line);this.zoneObjects.push(line);}
 }
}

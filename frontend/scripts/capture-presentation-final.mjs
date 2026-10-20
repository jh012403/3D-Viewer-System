import {chromium} from '@playwright/test';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const out='../docs/presentation',raw='../storage/presentation-final',scene='twin-logistics',job='job_000003';
await mkdir(out,{recursive:true});await mkdir(raw+'/frames',{recursive:true});
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:1}),p=await context.newPage();
const errors=[];p.on('pageerror',e=>errors.push(e.message));
const data=(b,type='image/png')=>`data:${type};base64,${b.toString('base64')}`;
const file=async(path,type)=>data(await readFile(path),type);
const css=`
.local,.statusbar,.ledger-note,.graph-meta,#objectHint,#recordCaption,.inspector>.section-label,#details,.progress-panel,.library-bottom{display:none!important}
.twin-node,.twin-edge,#assetLedger tr{animation:none!important}
.library .section-label,.library .muted,.source-card,.library h1,.library .upload,.library label{display:none!important}
.library:before{content:'시연 현장';display:block;font-size:22px;margin:8px 0 24px;color:#c5f0f4}
.library .scene-card:not(.active){display:none!important}
.twin-shell main{grid-template-columns:190px minmax(420px,1fr) 500px}
.twin-shell #assetLedger table{font-size:12px}.twin-shell #assetLedger td{padding:15px 8px}
.toolbar button{font-size:11px!important}.placement-spot{display:none!important}
#assetSpec p{font-size:15px;line-height:1.7}#assetSpec h3{font-size:20px}
.asset-id-layer button{font-size:18px!important;font-weight:700!important;padding:5px 8px!important;text-shadow:0 1px 3px #000} #toggleAmr,#surface,#analyze{display:none!important}
#placement>h2,#placement>p,#placement>label,#placement>input,#placement>.controls,#placement>#demoProp,#placement>#twinExports,#export{display:none!important}
#simulation .muted{display:none!important}
#placement>:not(#simulation){display:none!important}
`;
async function load(){
 await p.goto('http://127.0.0.1:5173/scene.html?scene='+scene);
 await p.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});
 await p.addStyleTag({content:css});await p.waitForTimeout(1200);
}
async function tidy(){
 await p.evaluate(()=>{const v=window.sceneWorkspace;v.placement.controls.detach();v.placement.outline(null);if(v.simulation.helper)v.simulation.helper.visible=false;if(v.simulation.safety)v.simulation.safety.visible=false;v.hidePresentationOverlays=true;});
 await p.waitForTimeout(300);
}
async function shot(selector){
 if(!['#graph','#assetLedger','#assetSpec'].includes(selector))return await p.locator(selector).screenshot();
 const cdp=await context.newCDPSession(p);
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:2,mobile:false});
 const result=await p.locator(selector).screenshot();
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:1,mobile:false});await cdp.detach();return result;
}
async function stage(title,kicker,panels,{columns,foot='',contain=true,strip}={}){
 const page=await context.newPage();
 await page.setContent(`<html lang="ko"><meta charset="utf-8"><style>
 *{box-sizing:border-box}body{margin:0;background:#0b1722;color:#e7f3f8;font-family:"Malgun Gothic",sans-serif}
 main{width:1920px;height:1080px;padding:54px 64px;display:flex;flex-direction:column}
 header{height:142px;flex:none}.kpi-strip{width:100%;height:84px;object-fit:contain;margin-bottom:18px;flex:none}small{font-size:17px;letter-spacing:3px;color:#68d0db}h1{font-size:42px;margin:14px 0;font-weight:600}
 section{display:grid;grid-template-columns:${columns||panels.map(()=>'minmax(0,1fr)').join(' ')};gap:26px;flex:1;min-height:0}
 article{display:flex;flex-direction:column;min-height:0;min-width:0;background:#102431;border:1px solid #2a4958;border-radius:18px;overflow:hidden}
 .image{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;padding:16px}img{width:100%;height:100%;object-fit:${contain?'contain':'cover'}}
 .label{height:76px;flex:none;display:flex;align-items:center;justify-content:center;gap:16px;border-top:1px solid #294351;font-size:26px;font-weight:600}
 .num{font-size:15px;color:#6acbd5;letter-spacing:2px}footer{height:40px;padding-top:18px;font-size:14px;color:#83a1b2}
 </style><main><header><small>PRISM / DIGITAL TWIN · 물류 창고</small><h1>${title}</h1></header>${strip?`<img class="kpi-strip" src="${data(strip)}">`:''}<section>${panels.map((v,i)=>`<article><div class="image"><img src="${typeof v.image==='string'?v.image:data(v.image)}"></div><div class="label"><span class="num">0${i+1}</span>${v.label}</div></article>`).join('')}</section><footer>${foot||'사진 기반 디지털트윈 · 물류 창고'}</footer></main></html>`);
 await page.locator('img').evaluateAll(imgs=>Promise.all(imgs.map(i=>i.decode())));
 const bounds=await page.locator('article').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,bottom:r.bottom};}));
 assert(bounds.every(r=>r.left>=0&&r.right<=1920&&r.bottom<=1080),JSON.stringify(bounds));
 await writeFile(raw+'/'+kicker+'.html',await page.content());
 await page.screenshot({path:out+'/'+kicker+'.png'});await page.close();
}
async function prepare(){
 await p.locator('#tabEdit').click();
 await p.evaluate(()=>{window.sceneWorkspace.hidePresentationOverlays=false;});
 // Hidden presentation controls remain functional through the original UI handlers.
 await p.evaluate(()=>document.querySelector('#refreshGenerated').click());
 await p.waitForFunction(()=>Array.from(document.querySelector('#generatedAsset').options).some(o=>o.value==='job_000003'));
 await p.evaluate(job=>{const s=document.querySelector('#generatedAsset');s.value=job;s.dispatchEvent(new Event('change',{bubbles:true}));},job);
 await p.evaluate(()=>document.querySelector('#placeGenerated').click());
 await p.waitForFunction(()=>window.sceneWorkspace.placement.pending);
 await p.evaluate(()=>{const v=window.sceneWorkspace;document.querySelector('#assetSpec')?.remove();v.placement.pending.name='반입 상자';v.placement.pending.asset.specification.kind='골판지 상자';v.placement.pending.asset.specification.materials=['골판지','종이'];v.placement.placeAtSpot(v.placement.spots[0]);});
 await height(.35);
}
async function height(value){await p.evaluate(value=>{const e=document.querySelector('#assetHeight');e.value=String(value);e.dispatchEvent(new Event('change',{bubbles:true}));},value);}
async function collide(){
 await p.evaluate(()=>{
  const v=window.sceneWorkspace,s=v.simulation,item=s.draft;
  const target=v.placement.baseNodes.find(n=>n.id==='jack'),b=target.box;
  item.object.position.set((b.min[0]+b.max[0])/2,Math.max(item.supportPoint.y,b.min[1]),(b.min[2]+b.max[2])/2);
  item.supportPoint.copy(item.object.position);s.inspect();v.placement.controls.detach();
  const r=s.result;document.querySelector('#simulationResult').textContent=`간섭 ${r.collisions.length}건 · 이격 부족 ${r.near.length}건 · 기준 ${s.clearance.toFixed(2)}m`;
 });
 assert.equal(await p.evaluate(()=>window.sceneWorkspace.simulation.result.state),'collision');
 await p.evaluate(()=>document.activeElement?.blur());
 await p.waitForTimeout(500);
}
try{
 await load();await tidy();
 await p.evaluate(()=>{const v=window.sceneWorkspace;v.dashboard.labels.hidden=true;v.reset(true);v.controls.enableDamping=false;const d=v.camera.position.clone().sub(v.controls.target);d.applyAxisAngle(d.clone().set(0,1,0),3*Math.PI/180);v.camera.position.copy(v.controls.target).add(d);v.controls.update();});
 await p.waitForTimeout(500);
 await stage('사진에서 현장 공간으로','02_현장복원',[
  {image:await file('../storage/scene_cache/twin-logistics/source.jpg','image/jpeg'),label:'원본 현장 사진'},
  {image:await shot('#viewport'),label:'3D 복원 · 3° 회전 시점'}]);
 await p.evaluate(()=>{const v=window.sceneWorkspace;v.reset(true);v.dashboard.labels.hidden=false;});
 await prepare();await p.waitForTimeout(900);
 await p.evaluate(()=>window.sceneWorkspace.placement.controls.detach());
 await p.screenshot({path:out+'/09_배치시뮬레이션.png'});
 await collide();await p.screenshot({path:out+'/10_간섭경고.png'});
 await p.locator('#findSafe').click();
 assert.equal(await p.evaluate(()=>window.sceneWorkspace.simulation.result.state),'clear');
 await p.locator('#confirmAsset').click();await p.waitForTimeout(900);await tidy();
 await p.locator('#tabAssets').click();await p.screenshot({path:out+'/01_대표.png'});
 const ledger=await shot('#assetLedger');
 await stage('현장 자산을 하나의 대장으로','04_자산대장',[{image:ledger,label:'ID · 분류 · 구역 · 크기 · 상태'}]);
 await p.locator('#tabGraph').click();await p.waitForTimeout(700);
 const graph=await shot('#graph');
 await stage('구역별 자산 연결과 이격 거리','05_관계그래프',[{image:graph,label:'구역별 관계 · 적재 · 인접'}]);
 await stage('반입 확정과 동시에 운영 정보 갱신','11_대장갱신',[
  {image:ledger,label:'EQ-0008 · 자산 대장 추가'},
  {image:graph,label:'반입 자산 · 관계 추가'}],{strip:await shot('#kpi')});
 await p.evaluate(()=>{const v=window.sceneWorkspace;v.placement.highlight(v.placement.graph.nodes.find(n=>n.id==='pallet'));});
 await p.waitForTimeout(300);
 await stage('현장 자산의 위치와 사양 확인','03_자산인식',[
  {image:await shot('#viewport'),label:'자산 ID · 선택 윤곽'},
  {image:await shot('#assetSpec'),label:'선택 자산 정보'}],{columns:'2fr 1fr'});
 await p.evaluate(()=>{const v=window.sceneWorkspace;v.placement.highlight(v.placement.graph.nodes.find(n=>n.source==='placed-glb'));});
 const card=await shot('#assetSpec');await tidy();
 await p.evaluate(()=>window.sceneWorkspace.dashboard.labels.hidden=true);
 await stage('반입 상자의 바닥 정렬과 접지 보정','08_배치보정',[
  {image:await file('../docs/placement-correction/before-original-view.png'),label:'보정 전'},
  {image:await shot('#viewport canvas'),label:'보정 후 · 정렬·음영·접촉 그림자'}]);
 await p.evaluate(()=>window.sceneWorkspace.dashboard.labels.hidden=false);
 const modelPage=await context.newPage();
 await modelPage.goto('http://127.0.0.1:5173/prismscan-v2.html?page=viewer&jobId='+job);
 await modelPage.waitForFunction(()=>document.querySelector('model-viewer.result-model')?.loaded,{},{timeout:120000});
 await modelPage.setViewportSize({width:1000,height:1000});
 await modelPage.evaluate(()=>{setViewerMaterialControl('environment','neutral');const m=document.querySelector('model-viewer.result-model');document.body.append(m);for(const e of document.body.children)if(e!==m)e.style.display='none';m.cameraOrbit='160deg 55deg 105%';m.style.cssText='position:fixed;inset:0;width:100vw;height:100vh;z-index:99999;background:#102431';});
 await modelPage.waitForTimeout(1800);const model=await modelPage.locator('model-viewer.result-model').screenshot();await modelPage.close();
 await stage('일반 물체 사진에서 3D 메시로','06_메시생성',[
  {image:await file('../storage/box-correction/box-three-quarter.jpg','image/jpeg'),label:'물체 사진'},
  {image:await file('../storage/temp/job_000003/sam2_candidates/candidates/sam3_text_0000/mask.png'),label:'분리 마스크'},
  {image:model,label:'생성된 3D 메시'}],{foot:'실제 완료 작업 · SAM3 → FastVLM → TRELLIS.2'});
 await stage('생성 자산의 종류·재질·크기','07_사양카드',[{image:model,label:'일반 물체 · 반입 상자'},{image:card,label:'자산 사양 카드'}]);
 await mkdir(out+'/exports',{recursive:true});
 for(const [id,name] of [['exportRegister','asset-register.json'],['exportRelations','asset-relations.json']]){
  const pending=p.waitForEvent('download');await p.evaluate(id=>document.getElementById(id).click(),id);
  await (await pending).saveAs(out+'/exports/'+name);
 }
 const exported=await p.evaluate(async()=>{
  const r=await window.sceneWorkspace.placement.export();
  return await new Promise(resolve=>{const f=new FileReader();f.onload=()=>resolve(f.result);f.readAsDataURL(r.image);});
 });
 await writeFile(out+'/exports/render.png',Buffer.from(exported.split(',')[1],'base64'));
 const previews=[];
 for(const name of ['asset-register.json','asset-relations.json']){
  const obj=JSON.parse(await readFile(out+'/exports/'+name,'utf8'));
  const preview=await context.newPage();
  await preview.setContent('<meta charset="utf-8"><style>body{background:#102431;color:#c6ebed;font:20px Consolas,monospace;padding:30px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h2></h2><pre></pre>');
  await preview.locator('h2').textContent();
  await preview.locator('h2').evaluate((e,t)=>e.textContent=t,name+' · 발췌');
  await preview.locator('pre').evaluate((e,t)=>e.textContent=t,JSON.stringify(obj,null,2).slice(0,2200));
  await preview.setViewportSize({width:750,height:1000});previews.push(await preview.screenshot());await preview.close();
 }
 await stage('현장 렌더와 운영 데이터를 함께 저장','12_출력물',[
  {image:exported,label:'원본 시점 렌더 PNG'},
  {image:previews[0],label:'자산 대장 JSON'},
  {image:previews[1],label:'관계 그래프 JSON'}],{foot:'실제 내보내기 파일 · JSON은 첫 부분 발췌'});
 if(!process.argv.includes('--stills-only')){
  const intro=await context.newPage();await intro.setContent(`<style>body{margin:0}img{width:1920px;height:1080px}</style><img src="${await file(out+'/06_메시생성.png')}">`);
  await intro.locator('img').evaluate(i=>i.decode());
  for(let i=0;i<20;i++)await intro.screenshot({path:`${raw}/frames/${String(i).padStart(3,'0')}.png`});
  await intro.close();await load();await prepare();await p.waitForTimeout(900);
  await p.evaluate(()=>window.sceneWorkspace.placement.controls.detach());
  for(let i=20;i<120;i++){
   if(i===38)await collide();
   if(i===62)await p.locator('#findSafe').click();
   if(i===82)await p.locator('#confirmAsset').click();
   if(i===94){await tidy();await p.locator('#tabAssets').click();}
   if(i===106)await p.locator('#tabGraph').click();
   await p.screenshot({path:`${raw}/frames/${String(i).padStart(3,'0')}.png`});await p.waitForTimeout(65);
  }
 }
 assert.deepEqual(errors,[]);
 await writeFile(out+'/capture.json',JSON.stringify({scene,job,files:12,frames:120,fps:10,errors,missing:[],notes:'Actual completed generation results; GIF opens with photo/mask/mesh comparison, then actual placement UI. Inference wait omitted. Photo-verified Korean kind/material aliases. Presentation-only CSS. Before correction uses historical original-camera capture.'},null,2));
 console.log('12 PNGs and 120 GIF frames captured.');
}finally{await browser.close();}

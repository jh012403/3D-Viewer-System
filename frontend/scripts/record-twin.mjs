import {chromium} from '@playwright/test';import {mkdir,readFile,writeFile} from 'node:fs/promises';import assert from 'node:assert/strict';
const phase=process.argv[2]||'intro',scenes=['twin-logistics','twin-laboratory','twin-workbench','twin-factory'],heights=[.35,.10,.12,.70];
const job=phase==='outro'?JSON.parse(await readFile('../docs/twin-real-mesh-run.json','utf8')).job:null;
await mkdir('../storage/twin_recordings',{recursive:true});await mkdir('../docs/twin-videos/results',{recursive:true});
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});const rows=[];
async function caption(p,text){await p.evaluate(text=>{let c=document.querySelector('#recordCaption');if(!c){c=document.createElement('div');c.id='recordCaption';c.style.cssText='position:fixed;top:161px;left:50%;transform:translateX(-50%);z-index:99;padding:10px 22px;border-radius:30px;background:#173b4eee;color:#c6f5fa;border:1px solid #579eaf;font:13px Malgun Gothic;pointer-events:none';document.body.append(c);}c.textContent=text;},text);}
try{for(const [index,scene]of scenes.entries()){
 const ctx=await browser.newContext({viewport:{width:1800,height:1100},recordVideo:{dir:'../storage/twin_recordings',size:{width:1800,height:1100}}}),p=await ctx.newPage(),errors=[],external=[];let report;
 p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(/^https?:/.test(r.url())&&!/127\.0\.0\.1|localhost/.test(r.url()))external.push(r.url());});
 await p.goto('http://127.0.0.1:5173/scene.html');await p.waitForSelector(`[data-scene="${scene}"]`);await caption(p,'01 · 현장을 불러옵니다');await p.waitForTimeout(700);await p.locator(`[data-scene="${scene}"]`).click();
 await p.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});await p.waitForTimeout(700);
 if(phase==='intro'){
  await caption(p,'02 · 원본 시점 주변 ±5° 공간 탐색');const canvas=p.locator('#viewport canvas').first(),r=await canvas.boundingBox(),x=r.x+r.width*.5,y=r.y+r.height*.5;
  await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(x+230,y,{steps:35});await p.mouse.up();await p.waitForTimeout(1000);await p.mouse.down();await p.mouse.move(x-230,y,{steps:55});await p.mouse.up();await p.waitForTimeout(1000);await p.locator('#reset').click();
  await caption(p,'03 · 자산 대장과 구역별 관계를 확인합니다');await p.locator('#assetLedger tbody tr').nth(2).click();await p.waitForTimeout(1600);await p.locator('#tabGraph').click();await p.waitForTimeout(1700);await p.screenshot({path:`../docs/screenshots/twin-stage7-${scene}-intro.png`});
  await caption(p,'다음 · 실제 사진 → 메시 생성 기록 (대기 구간 편집)');await p.waitForTimeout(1600);
 }else{
  await p.locator('#tabEdit').click();await caption(p,'04 · 실제 생성한 GLB를 현장으로 반입합니다');await p.locator('#refreshGenerated').click();await p.locator('#generatedAsset').selectOption(job);await p.locator('#placeGenerated').click();await p.waitForFunction(()=>window.sceneWorkspace.placement.pending);await p.locator('[data-spot="spot-0"]').click();
  await p.locator('#assetHeight').fill('1.20');await p.locator('#assetHeight').dispatchEvent('change');await caption(p,'크기·위치 검토 · 간섭 발생 시 반입 확정 차단');
  assert.equal(await p.evaluate(()=>window.sceneWorkspace.simulation.result.state),'collision');assert(await p.locator('#confirmAsset').isDisabled());await p.waitForTimeout(1900);await p.screenshot({path:`../docs/screenshots/twin-stage7-${scene}-interference.png`});
  await p.locator('#assetHeight').fill(String(heights[index]));await p.locator('#assetHeight').dispatchEvent('change');
  if(index===1||index===2){await p.locator('#clearance').fill('0.10');await p.locator('#clearance').dispatchEvent('change');await caption(p,'작업대 소형 공구 · 검토 기준을 0.10m로 선택');await p.waitForTimeout(1300);}
  await p.locator('#findSafe').click();
  for(const factor of [.8,.6,.4]){if(await p.evaluate(()=>window.sceneWorkspace.simulation.result.state)==='clear')break;await p.locator('#assetHeight').fill((heights[index]*factor).toFixed(2));await p.locator('#assetHeight').dispatchEvent('change');await p.waitForTimeout(600);await p.locator('#findSafe').click();}
  assert.equal(await p.evaluate(()=>window.sceneWorkspace.simulation.result.state),'clear');await caption(p,'간섭 해소 · 확인된 지지면으로 이동');await p.waitForTimeout(1400);await p.locator('#confirmAsset').click();await p.waitForTimeout(800);await p.evaluate(()=>window.sceneWorkspace.placement.controls.detach());
  await p.locator('#tabAssets').click();await caption(p,'05 · 신규 ID 발급 · 자산 대장과 KPI 갱신');await p.waitForTimeout(1600);await p.locator('#tabGraph').click();await p.waitForTimeout(1800);await p.screenshot({path:`../docs/screenshots/twin-stage7-${scene}-registered.png`});
  await p.locator('#tabEdit').click();await caption(p,'06 · 원본 렌더와 관계 그래프를 저장합니다');const downloads=[];p.on('download',d=>downloads.push(d.saveAs(`../docs/twin-videos/results/${scene}-${d.suggestedFilename()}`)));await p.locator('#export').click();await p.waitForTimeout(1400);await Promise.all(downloads);
  const pop=p.waitForEvent('popup');await p.locator('#exportReport').click();report=await pop;await report.waitForSelector('.sheet');await report.locator('.hero').evaluate(im=>im.decode());await report.waitForTimeout(1000);await report.pdf({path:`../docs/twin-videos/results/${scene}-report.pdf`,format:'A4',preferCSSPageSize:true,printBackground:true});await report.screenshot({path:`../docs/screenshots/twin-stage7-${scene}-report.png`,fullPage:true});await report.waitForTimeout(2600);
  rows.push(await p.evaluate(()=>{const v=window.sceneWorkspace;return {scene:v.manifest.id,assets:v.placement.graph.nodes.filter(n=>n.asset_id).length,placed:v.placement.items.length,job:v.placement.items[0]?.asset.source_job,checks:v.simulation.history};}));
 }
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);const video=p.video(),reportVideo=report?.video();await ctx.close();await video.saveAs(`../storage/twin_recordings/${scene}-${phase}.webm`);if(reportVideo)await reportVideo.saveAs(`../storage/twin_recordings/${scene}-report.webm`);console.log(scene,phase,'recorded');
}
await writeFile(`../docs/twin-recording-${phase}.json`,JSON.stringify({phase,job,rows},null,2));
}finally{await browser.close();}

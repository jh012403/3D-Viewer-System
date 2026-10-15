import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const scenes=['sunroom','ceramics','d4f646fcc79650d6','hall'];
const raw='../storage/demo_recordings',results='../docs/demo-videos/results';await mkdir(raw,{recursive:true});await mkdir(results,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const report=[];
try{
 for(const scene of scenes){
  const context=await browser.newContext({viewport:{width:1600,height:1000},recordVideo:{dir:raw,size:{width:1600,height:1000}},acceptDownloads:true});
  const page=await context.newPage(),errors=[],external=[],inference=[],downloads=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith('http://127.0.0.1:5173'))external.push(r.url());if(r.method()==='POST'&&/scene-api\/(build|graphs)/.test(r.url()))inference.push(r.url());});
  page.on('download',d=>downloads.push(d));
  await page.goto('http://127.0.0.1:5173/scene.html');await page.locator(`[data-scene="${scene}"]`).waitFor();
  await page.evaluate(()=>{
    const caption=document.createElement('div');caption.id='record-caption';caption.style.cssText='position:fixed;top:91px;left:50%;transform:translateX(-50%);z-index:40;background:#17291fea;border:1px solid #526c55;border-radius:30px;padding:10px 22px;color:#e0f5d8;font:13px "Malgun Gothic",sans-serif;pointer-events:none;box-shadow:0 4px 24px #0004';document.body.append(caption);
    const cursor=document.createElement('div');cursor.id='record-cursor';cursor.style.cssText='position:fixed;z-index:100;pointer-events:none;width:17px;height:17px;border:2px solid #edffe7;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 8px #122d1b;background:#a5d79b55';document.body.append(cursor);
    addEventListener('pointermove',e=>{cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';});addEventListener('pointerdown',()=>cursor.style.background='#d5ffb9');addEventListener('pointerup',()=>cursor.style.background='#a5d79b55');
  });
  const caption=async text=>page.evaluate(text=>document.querySelector('#record-caption').textContent=text,text);
  await caption('01  ·  사진 속 공간을 선택합니다');await page.waitForTimeout(1100);
  await page.locator(`[data-scene="${scene}"]`).click();
  await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});await page.waitForTimeout(900);
  await caption('02  ·  사진을 3D 공간으로 둘러봅니다');
  const rect=await page.locator('canvas').first().boundingBox(),cx=rect.x+rect.width*.52,cy=rect.y+rect.height*.42;
  await page.mouse.move(cx,cy);await page.mouse.down();
  for(let i=1;i<=24;i++){await page.mouse.move(cx+i*.5,cy);await page.waitForTimeout(35);}
  await page.waitForTimeout(500);
  for(let i=1;i<=48;i++){await page.mouse.move(cx+12-i*.5,cy);await page.waitForTimeout(30);}
  await page.mouse.up();await page.waitForTimeout(600);await page.locator('#reset').click();await page.waitForTimeout(500);
  await caption('03  ·  물체와 관계를 함께 살펴봅니다');await page.locator('#tabGraph').click();await page.waitForTimeout(600);
  const label=await page.evaluate(()=>window.sceneWorkspace.placement.baseNodes.find(n=>n.outline&& !['floor','table','glass shelf'].includes(n.name))?.label);
  await page.getByRole('button',{name:label,exact:true}).hover();await page.waitForTimeout(1100);await page.getByRole('button',{name:label,exact:true}).click();await page.waitForTimeout(900);
  await caption('04  ·  추천 위치에 물체를 놓습니다');await page.locator('#tabEdit').click();await page.locator('#demoProp').click();
  await page.waitForFunction(()=>window.sceneWorkspace.placement.pending);await page.waitForTimeout(600);await page.locator('#tabGraph').click();
  await page.locator('[data-spot="spot-0"]').click();await page.waitForFunction(()=>window.sceneWorkspace.placement.items.length===1);
  await page.waitForTimeout(800);await page.evaluate(()=>window.sceneWorkspace.placement.controls.detach());
  await caption('물체와 관계가 자연스럽게 이어집니다');await page.waitForTimeout(1600);
  await page.screenshot({path:`../docs/screenshots/demo-stage6-${scene}-graph.png`});
  await caption('05  ·  완성된 공간을 저장합니다');await page.locator('#tabEdit').click();await page.locator('#export').click();
  for(let i=0;i<100&&downloads.length<2;i++)await page.waitForTimeout(100);
  assert.equal(downloads.length,2);
  for(const d of downloads)await d.saveAs(`${results}/${scene}-${d.suggestedFilename()}`);
  await page.locator('#tabGraph').click();await page.waitForTimeout(900);
  await page.screenshot({path:`../docs/screenshots/demo-stage6-${scene}-saved.png`});await page.waitForTimeout(2200);
  const state=await page.evaluate(()=>{const p=window.sceneWorkspace.placement;return {title:window.sceneWorkspace.manifest.title,curated:p.graph.curated,nodes:p.graph.nodes.length,edges:p.graph.edges.length,overlap:p.overlaps(p.items[0]),settled:!p.items[0].landing};});
  assert(!state.overlap);assert(state.settled);assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.deepEqual(inference,[]);
  const video=page.video();await context.close();await video.saveAs(`${raw}/${scene}.webm`);
  report.push({scene,...state,downloads:downloads.length,errors,external,inference,raw:`storage/demo_recordings/${scene}.webm`});console.log(scene+' recorded');
 }
 await writeFile('../docs/demo-recording-run.json',JSON.stringify(report,null,2));
}finally{await browser.close();}

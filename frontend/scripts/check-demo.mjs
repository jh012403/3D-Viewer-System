import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const phase=process.argv[2]||'demo-stage3';
const spot=process.argv[3]||'spot-0';
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const rows=[],errors=[];
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}});page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 for(const scene of ['sunroom','ceramics','d4f646fcc79650d6','hall']){
  await page.goto('http://127.0.0.1:5173/scene.html?scene='+scene);
  await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy,{},{timeout:120000});
  if(await page.locator('#tabAssets').count())await page.locator('#tabEdit').click();
  await page.locator('#demoProp').click();await page.waitForFunction(()=>window.sceneWorkspace.placement.pending);
  await page.locator(`[data-spot="${spot}"]`).click();
  await page.waitForFunction(()=>window.sceneWorkspace.placement.items.length===1,{},{timeout:20000});
  await page.waitForTimeout(900);await page.evaluate(()=>window.sceneWorkspace.placement.controls.detach());
  const row=await page.evaluate(()=>{const p=window.sceneWorkspace.placement,i=p.items[0];return {scene:window.sceneWorkspace.manifest.id,nodes:p.graph.nodes.length,edges:p.graph.edges.length,overlap:p.overlaps(i),position:i.object.position.toArray(),support:i.supportTarget,settled:!i.landing};});
  assert(!row.overlap);assert(row.settled);rows.push(row);
  await page.screenshot({path:`../docs/screenshots/${phase}-${scene}-placement.png`});
  await page.locator('#tabGraph').click();await page.screenshot({path:`../docs/screenshots/${phase}-${scene}-graph.png`});
  if(phase==='demo-stage4'){
    const label=await page.evaluate(()=>window.sceneWorkspace.placement.baseNodes.find(n=>n.outline)?.label);
    await page.getByRole('button',{name:label,exact:true}).hover();
    assert.equal(await page.evaluate(()=>window.sceneWorkspace.placement.boxHelper?.type),'LineLoop');
    await page.screenshot({path:`../docs/screenshots/${phase}-${scene}-outline.png`});
  }
 }
 assert.deepEqual(errors,[]);await writeFile(`../docs/${phase}-browser.json`,JSON.stringify({rows,errors},null,2));console.log(JSON.stringify({rows,errors}));
}finally{await browser.close();}

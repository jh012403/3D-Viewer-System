import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const stage=process.argv[2]||'twin-stage1',scenes=['twin-logistics','twin-laboratory','twin-workbench','twin-factory'];
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const errors=[],rows=[];
try{const page=await browser.newPage({viewport:{width:1800,height:1100}});page.on('pageerror',e=>errors.push(e.message));
for(const scene of scenes){
 await page.goto('http://127.0.0.1:5173/scene.html?scene='+scene);
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});
 await page.waitForTimeout(500);
 if(stage==='twin-stage1')await page.locator('#tabGraph').click();
 if(stage==='twin-stage2'){
  await page.locator('#tabGraph').click();
  await page.evaluate(()=>{const p=window.sceneWorkspace.placement;p.highlight(p.graph.nodes.find(n=>n.classification!=='구조물'));});
  assert(await page.locator('#assetSpec').isVisible());
  const assets=await page.evaluate(()=>window.sceneWorkspace.placement.graph.nodes.filter(n=>n.asset_id));
  assert.equal(new Set(assets.map(n=>n.asset_id)).size,assets.length);assert(assets.every(n=>n.dimensions_m.width>0&&n.dimensions_m.height>0));
 }
 const row=await page.evaluate(()=>{const v=window.sceneWorkspace;return {scene:v.manifest.id,nodes:v.placement.graph.nodes.length,edges:v.placement.graph.edges.length,zones:v.placement.baseGraph.zones.length,spots:v.placement.spots.length};});
 assert(row.nodes>=6&&row.nodes<=10);assert(row.edges>=8&&row.edges<=12);rows.push(row);
 await page.screenshot({path:`../docs/screenshots/${stage}-${scene}.png`});
 if(stage==='twin-stage3'){
  assert.equal(await page.locator('#assetLedger tbody tr').count(),row.nodes);
  await page.locator('#assetLedger tbody tr').nth(1).click();assert(await page.locator('#assetSpec').isVisible());
  await page.locator('#tabGraph').click();assert(await page.locator('.zone-group').count()>=2);
  await page.screenshot({path:`../docs/screenshots/${stage}-${scene}-graph.png`});
  await page.locator('#toggleIds').click();assert(await page.locator('.asset-id-layer').isHidden());
 }
}
assert.deepEqual(errors,[]);await writeFile(`../docs/${stage}-browser.json`,JSON.stringify({rows,errors},null,2));console.log(JSON.stringify({rows,errors}));
}finally{await browser.close();}

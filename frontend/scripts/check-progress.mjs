import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}});
 await page.route('**/background.ply',async route=>{await new Promise(r=>setTimeout(r,1200));await route.continue();});
 await page.goto('http://127.0.0.1:5173/scene.html?scene=sunroom');
 await page.locator('.scene-progress').waitFor({state:'visible'});await page.screenshot({path:'../docs/screenshots/demo-stage5-cache-load.png'});
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});
 await page.waitForTimeout(500);
 // UI-only preview of the real worker stages; does not fake a generation run.
 for(let stage=0;stage<4;stage++){
  await page.evaluate(async stage=>(await import('/src/scene/progress.js')).showProgress(stage),stage);
  assert.equal(await page.locator('.scene-progress li.current').count(),1);
  await page.screenshot({path:`../docs/screenshots/demo-stage5-processing-${stage}.png`});
 }
 console.log('Cached loader and four processing UI states displayed; no model inference executed.');
}finally{await browser.close();}

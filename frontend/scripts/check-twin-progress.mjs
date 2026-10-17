import {chromium} from '@playwright/test';import assert from 'node:assert/strict';
const b=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
try{const p=await b.newPage({viewport:{width:1800,height:1100}});
await p.goto('http://127.0.0.1:5173/scene.html?scene=twin-logistics');await p.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});
await p.waitForTimeout(500);
for(let stage=0;stage<5;stage++){await p.evaluate(async s=>(await import('/src/scene/progress.js')).showProgress(s),stage);assert.equal(await p.locator('.scene-progress').last().locator('li').count(),5);await p.screenshot({path:`../docs/screenshots/twin-stage6-process-preview-${stage}.png`});}
await p.goto('http://127.0.0.1:5173/prismscan-v2.html');await p.evaluate(()=>{S.page='processing';S.proc=resolveProgress({status:'running',type:'image_to_3d',stage:'asset_metadata_running'});render();});
await p.waitForTimeout(1000);await p.screenshot({path:'../docs/screenshots/twin-stage6-mesh-preview.png'});
console.log('UI-only stage previews; not evidence of inference.');
}finally{await b.close();}

import {fileURLToPath} from 'node:url';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/scene.html');
 await page.locator('#cacheOnly').uncheck();
 const response=page.waitForResponse(r=>r.url().endsWith('/scene-api/build')&&r.request().method()==='POST');
 await page.setInputFiles('#photo','../.runtime/sam3/assets/images/groceries.jpg');
 const submitted=await response;assert.ok(submitted.ok());const {id}=await submitted.json();
 for(let i=0;i<400;i++){
  await page.waitForTimeout(1500);
  const job=await (await page.request.get('http://127.0.0.1:5173/scene-api/jobs/'+id)).json();
  if(i%20===0)console.log(JSON.stringify(job));
  assert.notEqual(job.status,'failed',job.message);
  if(job.status==='ready')break;
  if(i===399)throw Error('Upload inference timed out');
 }
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.baseNodes.length>0,{},{timeout:120000});
 await page.locator('#tabGraph').click();await page.waitForTimeout(2000);
 const state=await page.evaluate(()=>({id:window.sceneWorkspace.manifest.id,nodes:window.sceneWorkspace.placement.baseNodes.length,splats:window.sceneWorkspace.splat.packedSplats.numSplats}));
 assert.ok(state.nodes>0);assert.ok(state.splats>0);assert.deepEqual(errors,[]);
 await page.screenshot({path:'../docs/screenshots/stage2-upload.png',timeout:120000});
 await writeFile('../docs/scene-upload-check.json',JSON.stringify({state,errors},null,2));
 console.log(JSON.stringify({state,errors}));
}finally{await browser.close();}

import {fileURLToPath} from 'node:url';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const errors=[],external=[],inference=[],results=[];
const phase=process.argv[2]||'stage2';
try {
 const page=await browser.newPage({viewport:{width:1600,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{
  if(/^https?:/.test(r.url())&&!r.url().startsWith('http://127.0.0.1:5173'))external.push(r.url());
  if(r.method()==='POST'&&/scene-api\/(build|graphs)/.test(r.url()))inference.push(r.url());
 });
 for(const scene of ['sunroom','ceramics','hall','d4f646fcc79650d6']){
  await page.goto('http://127.0.0.1:5173/scene.html?scene='+scene);
  await page.waitForFunction(()=>window.sceneWorkspace?.placement?.baseNodes.length>0,{},{timeout:120000});
  await page.locator('#tabGraph').click();
  await page.locator('.graph-nodes button').nth(1).click();
  const state=await page.evaluate(()=>{
   const p=window.sceneWorkspace.placement;
   return {nodes:p.graph.nodes.length,edges:p.graph.edges.length,selected:p.selectedGraphId,highlight:!!p.boxHelper};
  });
  assert.ok(state.highlight);assert.ok(state.selected);
  const persisted=await (await page.request.get('http://127.0.0.1:5173/scene-cache/'+scene+'/graph.json')).json();
  assert.equal(state.edges,persisted.edges.length);
  assert.ok(state.edges<=state.nodes*3);
  await page.waitForTimeout(2000);
  await page.screenshot({path:'../docs/screenshots/'+phase+'-'+scene+'.png',timeout:120000});
  results.push({scene,...state});
 }
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.deepEqual(inference,[]);
 await writeFile('../docs/'+phase+'-graph-browser-check.json',JSON.stringify({results,errors,external,inference},null,2));
 console.log(JSON.stringify({results,errors,external,inference}));
}finally{await browser.close();}

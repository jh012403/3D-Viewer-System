import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const out='../docs/amr-areas';await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[],run={};
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')console.log(m.text());});
async function audit(){await page.waitForTimeout(250);return page.evaluate(()=>window.sceneWorkspace.amr.audit);}
try{
 await page.goto('http://127.0.0.1:5173/scene.html?scene=twin-logistics');
 await page.waitForFunction(()=>window.sceneWorkspace?.amr?.cells?.length&&!window.sceneWorkspace.loading,null,{timeout:120000});
 assert.equal(await page.locator('#amrPanel').isVisible(),false);
 await page.locator('#toggleAmr').click();run.before=await audit();console.log('BEFORE',JSON.stringify(run.before));
 assert(run.before.candidate_cells>0);assert(run.before.excluded_cells>0);
 await page.screenshot({path:out+'/01-floor-areas.png'});
 await page.evaluate(async()=>{const v=window.sceneWorkspace;await v.placement.importGenerated('job_000003');v.placement.pending.name='반입 상자';v.placement.placeAtSpot(v.placement.spots[0]);const size=document.querySelector('#assetHeight');size.value='.35';size.dispatchEvent(new Event('change'));v.placement.controls.detach();});
 run.draft=await audit();console.log('DRAFT',JSON.stringify(run.draft));assert(run.draft.excluded_cells>run.before.excluded_cells);
 assert(await page.evaluate(()=>window.sceneWorkspace.simulation.confirm()));
 await page.waitForTimeout(900);
 await page.evaluate(()=>{const v=window.sceneWorkspace;v.hidePresentationOverlays=true;if(v.simulation.helper)v.simulation.helper.visible=false;if(v.simulation.safety)v.simulation.safety.visible=false;});
 run.placed=await audit();assert.equal(run.placed.excluded_cells,run.draft.excluded_cells);
 await page.screenshot({path:out+'/02-intake-exclusion.png'});
 await page.locator('#amrClearance').fill('0.8');await page.locator('#amrClearance').dispatchEvent('change');run.wider=await audit();
 assert(run.wider.excluded_cells>=run.placed.excluded_cells);await page.screenshot({path:out+'/03-clearance-expanded.png'});
 await page.locator('#amrClearance').fill('0');await page.locator('#amrClearance').dispatchEvent('change');run.zero=await audit();assert(run.zero.excluded_cells<run.placed.excluded_cells);
 await page.locator('#toggleAmr').click();assert.equal(await page.evaluate(()=>window.sceneWorkspace.amr.mesh.visible),false);
 await page.evaluate(()=>document.querySelector('#remove').click());
 await page.evaluate(()=>{const input=document.querySelector('#amrClearance');input.value='.5';input.dispatchEvent(new Event('change'));document.querySelector('#toggleAmr').click();});
 run.removed=await audit();assert.equal(run.removed.excluded_cells,run.before.excluded_cells);
 await page.locator('[data-scene="ceramics"]').click();
 await page.waitForFunction(()=>window.sceneWorkspace.manifest.id==='ceramics'&&!window.sceneWorkspace.loading);
 assert(await page.locator('#toggleAmr').isDisabled());assert.equal(await page.locator('#amrPanel').isVisible(),false);
 await writeFile(out+'/checks.json',JSON.stringify({...run,errors},null,2));assert.deepEqual(errors,[]);
}finally{await browser.close();}

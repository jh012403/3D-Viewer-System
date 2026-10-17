import {chromium} from '@playwright/test';import {writeFile,mkdir} from 'node:fs/promises';import assert from 'node:assert/strict';
const b=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});const errors=[],rows=[];await mkdir('../docs/twin-output-samples',{recursive:true});
try{const p=await b.newPage({viewport:{width:1800,height:1100}});p.on('pageerror',e=>errors.push(e.message));
for(const scene of ['twin-logistics','twin-laboratory','twin-workbench','twin-factory']){
 await p.goto('http://127.0.0.1:5173/scene.html?scene='+scene);await p.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});await p.locator('#tabEdit').click();
 await p.locator('#demoProp').click();await p.locator('[data-spot="spot-0"]').click();
 if(['twin-laboratory','twin-workbench'].includes(scene)){await p.locator('#clearance').fill('0.1');await p.locator('#clearance').dispatchEvent('change');}
 await p.locator('#findSafe').click();await p.locator('#confirmAsset').click();await p.waitForTimeout(800);await p.evaluate(()=>window.sceneWorkspace.placement.controls.detach());
 const files=[];
 for(const id of ['exportRegister','exportRelations','exportGltf']){const wait=p.waitForEvent('download');await p.locator('#'+id).click();const d=await wait;await d.saveAs(`../docs/twin-output-samples/${scene}-${d.suggestedFilename()}`);files.push(d.suggestedFilename());}
 const pop=p.waitForEvent('popup');await p.locator('#exportReport').click();const report=await pop;await report.waitForSelector('.sheet');await report.locator('.hero').evaluate(im=>im.decode());
 const html=await report.content();await writeFile(`../docs/twin-output-samples/${scene}-report.html`,html);
 const pdf=await report.pdf({format:'A4',printBackground:true,preferCSSPageSize:true});await writeFile(`../docs/twin-output-samples/${scene}-report.pdf`,pdf);
 const pages=(pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length;assert.equal(pages,1);
 await report.screenshot({path:`../docs/screenshots/twin-stage5-${scene}-report.png`,fullPage:true});await report.close();
 const result=await p.evaluate(async()=>{const v=window.sceneWorkspace,gltf=await v.exports.gltf();const {GLTFLoader}=await import('/node_modules/three/examples/jsm/loaders/GLTFLoader.js');const parsed=await new GLTFLoader().parseAsync(JSON.stringify(gltf),'');return {count:parsed.scene.children.length,assets:v.placement.graph.nodes.filter(n=>n.asset_id).length,background:gltf.scenes[0].extras.background_excluded};});assert.equal(result.count,result.assets);assert(result.background);rows.push({scene,files,pages,...result});
 await p.locator('#tabGraph').click();await p.screenshot({path:`../docs/screenshots/twin-stage5-${scene}-placed.png`});
}
assert.deepEqual(errors,[]);await writeFile('../docs/twin-stage5-exports.json',JSON.stringify({rows,errors},null,2));console.log(JSON.stringify({rows,errors}));
}finally{await b.close();}

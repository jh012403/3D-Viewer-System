import {chromium} from '@playwright/test';import {writeFile} from 'node:fs/promises';import assert from 'node:assert/strict';
const b=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});const rows=[],errors=[];
try{const p=await b.newPage({viewport:{width:1800,height:1100}});p.on('pageerror',e=>errors.push(e.message));
for(const scene of ['twin-logistics','twin-laboratory','twin-workbench','twin-factory']){
 await p.goto('http://127.0.0.1:5173/scene.html?scene='+scene);await p.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,{},{timeout:120000});
 const before=await p.evaluate(()=>window.sceneWorkspace.placement.graph.nodes.length);
 await p.locator('#demoProp').click();await p.locator('[data-spot="spot-0"]').click();
 const initial=await p.evaluate(()=>window.sceneWorkspace.simulation.result);console.log(scene,JSON.stringify(initial));
 await p.evaluate(()=>{const v=window.sceneWorkspace,s=v.simulation,d=s.draft,n=v.placement.baseNodes.find(n=>n.classification!=='구조물');d.object.position.set(...n.center_m);s.inspect();});
 assert.equal(await p.evaluate(()=>window.sceneWorkspace.simulation.result.state),'collision');assert(await p.locator('#confirmAsset').isDisabled());
 await p.screenshot({path:`../docs/screenshots/twin-stage4-${scene}-collision.png`});
 if(['twin-laboratory','twin-workbench'].includes(scene)){await p.locator('#clearance').fill('0.1');await p.locator('#clearance').dispatchEvent('change');}
 await p.locator('#findSafe').click();
 const safe=await p.evaluate(()=>window.sceneWorkspace.simulation.result);console.log('SAFE',scene,JSON.stringify(safe));
 await p.screenshot({path:`../docs/screenshots/twin-stage4-${scene}-safe.png`});
 if(safe.state==='clear'){await p.locator('#confirmAsset').click();await p.waitForTimeout(800);assert.equal(await p.evaluate(()=>window.sceneWorkspace.placement.graph.nodes.filter(n=>n.asset_id).length),before+1);}
 rows.push({scene,initial,safe});
}
await writeFile('../docs/twin-stage4-placement.json',JSON.stringify({rows,errors},null,2));assert.deepEqual(errors,[]);assert(rows.every(r=>r.safe.state==='clear'));
}finally{await b.close();}

import {chromium} from '@playwright/test';
import {readFile,writeFile,stat,readdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const path='../docs/twin-real-mesh-run.json',run=JSON.parse(await readFile(path,'utf8'));
const b=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const c=await b.newContext({viewport:{width:1800,height:1100},recordVideo:{dir:'../storage/twin_recordings',size:{width:1800,height:1100}}}),p=await c.newPage(),external=[],errors=[];
p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(/^https?:/.test(r.url())&&!/localhost|127\.0\.0\.1/.test(r.url()))external.push(r.url());});
try{
 await p.goto(`http://127.0.0.1:5173/prismscan-v2.html?page=viewer&jobId=${run.job}`);
 await p.waitForFunction(()=>document.querySelector('model-viewer.result-model')?.loaded,{},{timeout:120000});
 await p.evaluate(()=>{setViewerMaterialControl('environment','neutral');document.querySelector('model-viewer.result-model').cameraOrbit='160deg 55deg 105%';});
 await p.waitForTimeout(2000);await p.screenshot({path:'../docs/screenshots/twin-real-mesh-download.png'});
 const downloaded=p.waitForEvent('download');await p.locator('[onclick="downloadSelectedFormat()"]').click();const d=await downloaded;
 const file=`../storage/twin_recordings/${run.job}-download.glb`;await d.saveAs(file);const bytes=await readFile(file);assert.equal(bytes.toString('ascii',0,4),'glTF');assert(bytes.length>100000);
 await p.waitForTimeout(2500);assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 const selection=await stat('../docs/screenshots/twin-real-mesh-selection.png');
 const files=await Promise.all((await readdir('../storage/twin_recordings')).filter(n=>n.startsWith('page@')&&n.endsWith('.webm')).map(async name=>({name,...await stat('../storage/twin_recordings/'+name)})));
 const recording=await stat('../storage/twin_recordings/real-mesh-validation.webm');
 const original=files.find(f=>f.size===recording.size&&f.birthtimeMs<selection.mtimeMs);assert(original);
 Object.assign(run,{standalone_download:{bytes:bytes.length,glb_header:true,errors,external},selection_video_seconds:(selection.mtimeMs-original.birthtimeMs)/1000,source_recording:original.name});
 await writeFile(path,JSON.stringify(run,null,2));console.log(JSON.stringify(run));
}finally{const video=p.video();await c.close();await video.saveAs('../storage/twin_recordings/mesh-download.webm');await b.close();}

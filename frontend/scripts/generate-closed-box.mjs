import {chromium} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const api='http://127.0.0.1:8000';
async function request(path,options){const r=await fetch(api+path,options);if(!r.ok)throw Error(await r.text());return r.json();}
const post=body=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
let job=process.argv[2];
if(!job){
 const form=new FormData();form.append('type','image_to_3d');form.append('file',new Blob([await readFile('../storage/box-correction/box-three-quarter.jpg')]),'closed-box.jpg');
 const upload=await request('/api/upload',{method:'POST',body:form});job=upload.job_id;
 const mask=await request(`/api/jobs/${job}/segmentation-text-prompt`,post({prompt:'cardboard box',confidence_threshold:.5,merge_mode:'best'}));
 await request('/api/jobs',post({job_id:job,type:'image_to_3d',options:{sam2_candidate_id:mask.selected_candidate_id}}));
}
let result;
for(let i=0;i<180;i++){
 result=await request('/api/jobs/'+job);console.log(job,result.status,result.stage);
 if(result.status==='failed')throw Error(result.error);
 if(result.status==='completed')break;
 await new Promise(r=>setTimeout(r,10000));
}
assert.equal(result.status,'completed');
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(`http://127.0.0.1:5173/prismscan-v2.html?page=viewer&jobId=${job}`);
 await page.waitForFunction(()=>document.querySelector('model-viewer.result-model')?.loaded,null,{timeout:120000});
 await page.evaluate(()=>{setViewerMaterialControl('environment','neutral');document.querySelector('model-viewer.result-model').cameraOrbit='160deg 55deg 105%';});
 await page.waitForTimeout(1200);await page.screenshot({path:'../docs/placement-correction/mesh-result.png'});
 const pending=page.waitForEvent('download');await page.locator('[onclick="downloadSelectedFormat()"]').click();const download=await pending;
 await download.saveAs('../storage/box-correction/standalone-download.glb');
 const bytes=await readFile('../storage/box-correction/standalone-download.glb');assert.equal(bytes.toString('ascii',0,4),'glTF');assert(bytes.length>100000);
 await writeFile('../docs/placement-correction/mesh-run.json',JSON.stringify({job,status:result.status,standalone_download_bytes:bytes.length,errors},null,2));
 assert.deepEqual(errors,[]);
}finally{await browser.close();}

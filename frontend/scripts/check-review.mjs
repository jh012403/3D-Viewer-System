import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {readFile,writeFile} from 'node:fs/promises';
import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
const phase=process.argv[2]||'revision5';
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
 await page.goto(pathToFileURL(resolve('../docs/scene-review/index.html')).href);
 assert.equal(await page.locator('#nav button').count(),5);
 for(const id of ['dav2-01','dav2-10','dav2-13','dav2-14','dav2-15']){
  await page.getByRole('button',{name:id,exact:true}).click();
  assert.ok(await page.locator('#nodes tr').count());assert.ok(await page.locator('#edges tr').count());
  await page.screenshot({path:`../docs/screenshots/${phase}-review-${id}.png`});
 }
 await page.getByRole('button',{name:'dav2-10',exact:true}).click();
 await page.locator('#nodes tr').first().click();assert.equal(await page.locator('#overlay rect').count(),1);
 await page.locator('#confirm').click();assert.match(await page.locator('#message').textContent(),/5장 모두/);
 const download=page.waitForEvent('download');await page.locator('#draft').click();
 const draft=JSON.parse(await readFile(await (await download).path(),'utf8'));
 assert.equal(draft.confirmed,false);assert.ok(draft.photos.every(p=>Object.values(p.nodes).every(n=>n.decision==='')));
 await page.screenshot({path:`../docs/screenshots/${phase}-review.png`});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 await writeFile('../docs/scene-review-browser-check.json',JSON.stringify({photos:5,errors,external,premature_confirmation_blocked:true,draft_confirmed:false},null,2));
 console.log('Five-photo review pack: local-only, premature confirmation blocked, no synthetic human labels saved.');
}finally{await browser.close();}

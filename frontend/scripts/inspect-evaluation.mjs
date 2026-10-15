import {chromium} from '@playwright/test';import {pathToFileURL,fileURLToPath} from 'node:url';import {resolve} from 'node:path';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
const browser=await chromium.launch();try{const page=await browser.newPage({viewport:{width:1600,height:1400}});
await page.goto(pathToFileURL(resolve('../docs/scene-stage0.html')).href);
await page.setContent('<style>body{margin:0;background:#222;display:grid;grid-template-columns:repeat(4,1fr);font:16px sans-serif;color:white}figure{margin:6px}img{width:100%;height:230px;object-fit:contain}figcaption{text-align:center}</style>'+Array.from({length:20},(_,i)=>{const name='demo'+String(i+1).padStart(2,'0')+'.jpg';return '<figure><img src="'+pathToFileURL(resolve('../.runtime/Depth-Anything-V2/assets/examples/'+name)).href+'"><figcaption>'+name+'</figcaption></figure>';}).join(''));
await page.waitForFunction(()=>[...document.images].every(x=>x.complete));await page.screenshot({path:'../storage/tmp/evaluation-contact-sheet.png',fullPage:true});}finally{await browser.close();}

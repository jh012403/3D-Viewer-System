"""Finish one recording; stage failures never abort the remaining tour.

Reuses run.py browser interaction, configuration, overlays and OBS control.
Does not inspect recording quality or change OBS settings.
"""
import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from playwright.async_api import async_playwright
import imageio_ffmpeg
from run import Demo, ROOT, save
from desktop import monitor
from warmup import fresh_background


class FinishOnce(Demo):
    async def guarded(self, name, action):
        started=time.monotonic()
        try:
            await asyncio.wait_for(self.stage(name), 10)
            await asyncio.wait_for(action(), 290)
            self.report.setdefault('stage_results', []).append({'stage': name, 'status': 'completed', 'elapsed_seconds':round(time.monotonic()-started,3)})
        except Exception as exc:
            reason = str(exc) or 'Stage exceeded the 5-minute limit'
            self.report.setdefault('stage_results', []).append({'stage': name, 'status': 'skipped_or_failed', 'reason': reason, 'elapsed_seconds':round(time.monotonic()-started,3)})
            print('CONTINUING:', name, reason, flush=True)
        finally:
            save(self.out/'run.json', self.report)

    async def move(self, x, y, seconds=.7):
        sx, sy = self.xy
        started = time.monotonic()
        duration = max(.01, seconds*self.speed)
        while True:
            f = min(1., (time.monotonic()-started)/duration)
            eased = f*f*(3-2*f)
            await self.p.mouse.move(sx+(x-sx)*eased, sy+(y-sy)*eased)
            if f >= 1: break
            await asyncio.sleep(1/60)
        self.xy = (x, y)

    async def upload_background(self):
        await self.p.locator('#cacheOnly').uncheck()
        photo = fresh_background(ROOT/self.c['background_image'], self.out)
        async with self.p.expect_response(lambda r: r.url.endswith('/scene-api/build') and r.request.method == 'POST') as pending:
            await self.p.locator('#photo').set_input_files(str(photo))
        response = await pending.value
        if not response.ok: raise RuntimeError(await response.text())
        self.report['scene_job'] = (await response.json())['id']
        await self.p.evaluate('''async()=>{const im=new Image();im.id='demo-source-preview';im.src=URL.createObjectURL(document.querySelector('#photo').files[0]);im.style.cssText='position:fixed;inset:8%;width:84%;height:80%;object-fit:contain;background:#091721;z-index:99999';document.body.append(im);await im.decode()}''')
        try: await self.pause(3)
        finally: await self.p.evaluate('document.querySelector("#demo-source-preview")?.remove()')

    async def initial_graph(self):
        jid = self.report.get('scene_job')
        if not jid: raise RuntimeError('Background upload did not return a job')
        while True:
            response = await self.p.request.get(self.c['base_url']+'/scene-api/jobs/'+jid, timeout=15000)
            job = await response.json()
            if job['status'] == 'failed': raise RuntimeError(job.get('message', 'Scene generation failed'))
            if job['status'] == 'ready': break
            await asyncio.sleep(2)
        scene_id = job['url'].split('/')[-2]
        await self.wait_state('!document.querySelector("#photo").disabled', 60)
        if await self.p.evaluate('sceneWorkspace.manifest?.id') != scene_id:
            await self.click('[data-scene="'+scene_id+'"]')
        await self.wait_state('sceneWorkspace.placement?.graph?.nodes?.length>0 && !sceneWorkspace.loading', 60)
        self.report['graph_before']=await self.p.evaluate('({nodes:sceneWorkspace.placement.graph.nodes.length,edges:sceneWorkspace.placement.graph.edges.length})')
        await self.click('#tabGraph'); await self.pause(5)
        for i in range(min(3, await self.p.locator('#graph svg g[role="button"]').count())):
            node = self.p.locator('#graph svg g[role="button"]').nth(i)
            await node.hover(); await node.click(); await self.pause(2)

    async def select_object(self):
        self.scene_page = self.p
        self.p = await self.context.new_page()
        await self.fullscreen()
        await self.p.goto(self.c['base_url']+'/prismscan-v2.html?page=upload')
        await self.p.locator('#fi').set_input_files(str(ROOT/self.c['object_image']))
        await self.p.locator('.dz-preview-img').wait_for(); await self.pause(3)
        await self.p.locator('.seg-text-input').fill(self.c['object_prompt'])
        await self.click('[onclick="startProc()"]')
        await self.wait_state('S.seg?.selectedId || S.seg?.text?.error || S.seg?.error', 240)
        await self.p.locator('#seg-picked-preview img').first.wait_for()
        await self.scroll_to(self.p.locator('.seg-map-work')); await self.pause(3)

    async def generate_mesh(self):
        await self.click('#seg-start-selected')
        await self.wait_state('S.job?.status === "completed" || S.job?.status === "failed"', 260)
        state = await self.p.evaluate('({status:S.job.status, job:S.sid, error:S.job.error})')
        if state['status'] != 'completed': raise RuntimeError(str(state['error']))
        self.report['mesh_job'] = state['job']
        await self.wait_state('S.result?.hydrated && document.querySelector("model-viewer.result-model")?.loaded', 30)
        await self.click('[data-env="neutral"]')
        model = self.p.locator('model-viewer.result-model')
        await self.scroll_to(model)
        for _ in range(4):
            b = await model.bounding_box()
            dx = min(b['width']*.5, b['height']/4)
            x, y = b['x']+b['width']/2+dx/2, b['y']+b['height']/2
            await self.move(x,y,.1); await self.p.mouse.down()
            try: await self.move(x-dx,y,2)
            finally: await self.p.mouse.up()
        for sign in (-1,1):
            for _ in range(12):
                await self.p.mouse.wheel(0,sign*18); await self.pause(.07)
            await self.pause(1)

    async def place(self):
        self.p = self.scene_page
        await self.fullscreen()
        scene = self.c['placement_scene']
        await self.click('[data-scene="'+scene+'"]')
        await self.wait_state('sceneWorkspace.manifest?.id === '+json.dumps(scene)+' && !sceneWorkspace.loading', 90)
        await self.click('#tabEdit'); await self.click('#refreshGenerated')
        job = self.report.get('mesh_job')
        if not job:
            if self.c.get('prepared_demo'):raise RuntimeError('Prepared mesh did not complete; fallback is disabled in demo-mode validation')
            # The live job continues on the server; show a previously generated
            # asset explicitly, rather than claiming the timed-out job completed.
            options = await self.p.locator('#generatedAsset option').evaluate_all('(es)=>es.map(e=>({value:e.value,label:e.textContent})).filter(e=>e.value)')
            if not options: raise RuntimeError('No completed generated asset available')
            job = options[0]['value']
            self.report['placement_fallback'] = {'job': job, 'reason': 'Live mesh step did not complete within its time limit'}
            await self.p.evaluate('(t)=>window.__demoCaption?.(t)', 'Step 6. 이전에 생성한 자산으로 배치 시연')
            print('Previously completed asset for placement:', job, flush=True)
        await self.p.locator('#generatedAsset').select_option(job)
        await self.click('#placeGenerated'); await self.wait_state('!!sceneWorkspace.placement.pending', 60)
        await self.click('[data-spot="spot-0"]'); await self.wait_state('!!sceneWorkspace.simulation.draft', 30)
        await self.p.locator('#assetHeight').fill(str(self.c['placement_height_m']))
        await self.p.locator('#assetHeight').dispatch_event('change')
        await self.click('#findSafe'); await self.pause(4)
        await self.click('#confirmAsset'); await self.pause(4)
        await self.wait_state('sceneWorkspace.placement.items.length===1',20)
        if self.c.get('prepared_demo'):
            graph=await self.p.evaluate('sceneWorkspace.placement.graph')
            save(ROOT/'demo_assets/graph-updated.json',graph)
            save(ROOT/'demo_assets/asset-list-updated.json',graph['nodes'])
            await self.p.locator('#viewport').screenshot(path=str(ROOT/'demo_assets/composite-result.png'))

    async def updated_graph(self):
        self.p = self.scene_page; await self.fullscreen()
        await self.click('#tabGraph'); await self.pause(5)
        items=await self.p.evaluate('sceneWorkspace.placement.items.length')
        if not items:raise RuntimeError('No new asset registered')
        asset_id=await self.p.evaluate('(()=>{const p=sceneWorkspace.placement;return p.graph.nodes.find(n=>n.id===p.items[0].id).asset_id})()')
        node = self.p.locator('#graph svg g[role="button"]').filter(has=self.p.locator('text',has_text=asset_id)).first
        await node.hover(); await node.click(); await self.pause(3)
        self.report['graph_after']=await self.p.evaluate('({nodes:sceneWorkspace.placement.graph.nodes.length,edges:sceneWorkspace.placement.graph.edges.length})')
        self.report['new_asset_id']=asset_id
        if self.c.get('prepared_demo'):
            assert self.report['graph_after']['nodes']==self.report['graph_before']['nodes']+1
            assert self.report['graph_after']['edges']>self.report['graph_before']['edges']

    async def assets(self):
        self.p = self.scene_page; await self.fullscreen()
        await self.click('#tabAssets')
        rows = self.p.locator('#assetLedger tbody tr')
        for i in range(min(12, await rows.count())):
            row = rows.nth(i)
            await self.scroll_to(row); await row.hover(); await row.click(); await self.pause(2)

    async def start_recorder(self):
        if self.args.rehearsal:
            self.report['recording_mode']='none'
            return
        try:
            # Existing control only: no encoder/profile/source changes.
            await asyncio.wait_for(super().setup_obs(), 30)
            if self.owns_record: return
        except Exception as exc:
            self.report['obs_error'] = str(exc)
        await self.p.evaluate('(t)=>window.__demoCaption?.(t)', 'PRISM SCENE · 준비된 결과 시연' if self.c.get('prepared_demo') else 'PRISM SCENE')
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        self.capture = None
        for codec in (['-c:v','h264_nvenc','-cq','20'], ['-c:v','libx264','-preset','veryfast','-crf','20']):
            path = self.out/('capture-'+codec[1]+'.mkv')
            log = open(self.out/('capture-'+codec[1]+'.log'), 'wb')
            proc = await asyncio.create_subprocess_exec(ffmpeg,'-y','-f','gdigrab','-framerate','30','-video_size','1920x1080','-i','desktop',*codec,str(path),stdin=asyncio.subprocess.PIPE,stdout=log,stderr=log)
            await asyncio.sleep(3)
            if proc.returncode is None:
                self.capture=proc; self.capture_log=log; self.report['mkv']=str(path)
                self.report['recording_mode']='ffmpeg-'+codec[1]; return
            log.close()
        # Last resort: recreate the still-empty browser context with video enabled.
        await self.context.close()
        self.context = await self.browser.new_context(viewport={'width':1920,'height':1080},record_video_dir=str(self.out/'video'),record_video_size={'width':1920,'height':1080})
        await self.context.add_init_script(path=str(ROOT/'demo/overlay.js'))
        self.p=await self.context.new_page(); await self.p.goto(self.c['base_url']+'/scene.html'); await self.fullscreen()
        self.report['recording_mode']='playwright'; self.video_page=self.p

    async def run(self):
        if self.c.get('prepared_demo') and os.environ.get('DEMO_MODE')!='1':
            raise RuntimeError('Prepared demo requires DEMO_MODE=1')
        metrics = monitor()
        self.capture = None
        async with async_playwright() as pw:
            self.browser = await pw.chromium.launch(channel='chrome',headless=False,args=['--kiosk','--window-position=0,0',f'--window-size={metrics["width"]},{metrics["height"]}','--enable-gpu','--use-angle=d3d11'])
            self.context=await self.browser.new_context(viewport={'width':metrics['css_width'],'height':metrics['css_height']},device_scale_factor=metrics['scale'])
            self.context.set_default_timeout(20000)
            await self.context.add_init_script(path=str(ROOT/'demo/overlay.js'))
            self.p=await self.context.new_page()
            self.context.on('page',lambda p:p.on('pageerror',lambda e:self.report['errors'].append(str(e))))
            self.p.on('pageerror',lambda e:self.report['errors'].append(str(e)))
            self.scene_page=self.p
            try:
                await self.p.goto(self.c['base_url']+'/scene.html'); await self.fullscreen()
                await self.start_recorder(); self.t0=time.monotonic()
                for name, action in [
                    ('Step 1. PRISM SCENE',lambda:self.pause(3)),
                    ('Step 2. 배경 사진 업로드',self.upload_background),
                    ('Step 3. 최초 관계 그래프 생성',self.initial_graph),
                    ('Step 4. 물체 선택과 분리 마스크',self.select_object),
                    ('Step 5. 3D 메시 생성',self.generate_mesh),
                    ('Step 6. 씬 배치',self.place),
                    ('Step 7. 갱신된 관계 그래프',self.updated_graph),
                    ('Step 8. 자산 목록',self.assets),
                    ('Step 9. PRISM SCENE · 시연 종료',lambda:self.pause(3)),
                ]: await self.guarded(name,action)
                failures=[s for s in self.report['stage_results'] if s['status']!='completed']
                self.report['status']='finished' if failures or self.report['errors'] else 'passed'
            finally:
                self.report['scenario_seconds']=time.monotonic()-self.t0 if self.t0 else None
                try:
                    if self.owns_record:
                        # Stop first, even if optional metadata requests would fail.
                        stopped=await asyncio.to_thread(self.obs.stop_record)
                        self.owns_record=False; self.report['mkv']=stopped.output_path
                    if self.capture:
                        self.capture.stdin.write(b'q\n'); await self.capture.stdin.drain()
                        await asyncio.wait_for(self.capture.wait(),60); self.capture_log.close()
                except Exception as exc:
                    self.report['stop_error']=str(exc)
                    if self.owns_record:
                        try:
                            stopped=await asyncio.to_thread(self.obs.stop_record)
                            self.report['mkv']=stopped.output_path; self.owns_record=False
                        except Exception as retry:self.report['stop_retry_error']=str(retry)
                finally:
                    await self.context.close()
                    if hasattr(self,'video_page'):self.report['video']=str(await self.video_page.video.path())
                    await self.browser.close()
                    save(self.out/'run.json',self.report)
                if self.report.get('mkv'):
                    await asyncio.sleep(3)
                    src=Path(self.report['mkv']); dest=src.with_suffix('.mp4')
                    proc=await asyncio.create_subprocess_exec(imageio_ffmpeg.get_ffmpeg_exe(),'-n','-i',str(src),'-c','copy',str(dest),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
                    _,err=await proc.communicate()
                    if proc.returncode==0:self.report['mp4']=str(dest)
                    else:self.report['remux_error']=err.decode(errors='replace')[-1000:]
                save(self.out/'run.json',self.report)
                print('REPORT',self.out/'run.json',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--rehearsal',action='store_true')
    parser.add_argument('--config',default=str(ROOT/'demo/config.json'))
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    config['timeout_seconds']=290
    asyncio.run(FinishOnce(config,argparse.Namespace(speed=1.,rehearsal=args.rehearsal)).run())

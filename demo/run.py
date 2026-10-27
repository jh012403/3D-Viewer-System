"""Uncut UI demonstration. OBS is the sole recorder; Playwright only drives UI."""
import argparse
import asyncio
import datetime as dt
import json
import logging
import math
import os
import re
import subprocess
import time
from pathlib import Path

import obsws_python as obs
import imageio_ffmpeg
from playwright.async_api import async_playwright
from desktop import monitor
from warmup import fresh_background

ROOT=Path(__file__).resolve().parents[1]
SPEED=1.0  # Multiplies presentation pauses/motion only, never inference timeouts.

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def response_dict(r):
    return {k:getattr(r,k) for k in r.attrs()}

class Demo:
    def __init__(self,config,args):
        self.c=config;self.args=args;self.speed=args.speed or config.get('speed',SPEED)
        stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y%m%d-%H%M%S')
        self.out=ROOT/'storage/obs-demo'/('rehearsal-' if args.rehearsal else 'record-')/stamp
        self.out.mkdir(parents=True,exist_ok=True)
        self.report={'started_kst':stamp,'speed':self.speed,'mode':'rehearsal' if args.rehearsal else 'record','steps':[],'errors':[],'obs_samples':[],'status':'running'}
        self.obs=None;self.owns_record=False;self.t0=None;self.xy=(400,300);self.caption='';self.stop_stats=False;self.scene_session=None

    async def pause(self,seconds):await asyncio.sleep(seconds*self.speed)

    async def move(self,x,y,seconds=.7):
        sx,sy=self.xy;n=max(12,round(seconds*self.speed*60))
        for i in range(1,n+1):
            f=i/n;f=f*f*(3-2*f)
            await self.p.mouse.move(sx+(x-sx)*f,sy+(y-sy)*f)
            await asyncio.sleep(seconds*self.speed/n)
        self.xy=(x,y)

    async def scroll_to(self,locator):
        await locator.evaluate('(e)=>e.scrollIntoView({behavior:"smooth",block:"center"})')
        await self.pause(.9)

    async def click(self,selector):
        el=self.p.locator(selector).first
        await el.wait_for(state='visible');await self.scroll_to(el)
        b=await el.bounding_box()
        if not b:raise RuntimeError('No visible bounds: '+selector)
        await self.move(b['x']+b['width']/2,b['y']+b['height']/2)
        await el.click();await self.pause(.35)

    async def stage(self,name):
        now=time.monotonic();elapsed=now-self.t0 if self.t0 else 0
        row={'name':name,'seconds':round(elapsed,3),'timecode':f'{int(elapsed)//60:02}:{int(elapsed)%60:02}'}
        self.report['steps'].append(row);self.caption=name
        await self.p.evaluate('(t)=>window.__demoCaption?.(t)',name if self.c['captions'] else '')
        save(self.out/'run.json',self.report);print(row,flush=True)

    async def shot(self,name):await self.p.screenshot(path=str(self.out/(name+'.png')))

    async def wait_state(self,js,timeout=None):
        await self.p.wait_for_function(js,timeout=(timeout or self.c['timeout_seconds'])*1000,polling=750)

    async def fullscreen(self):
        session=await self.context.new_cdp_session(self.p)
        window=await session.send('Browser.getWindowForTarget')
        await session.send('Browser.setWindowBounds',{'windowId':window['windowId'],'bounds':{'windowState':'fullscreen'}})
        await session.detach();await self.p.bring_to_front()

    async def setup_obs(self):
        if self.args.rehearsal:return
        info=self.c['obs'];secret=os.environ.get(info['password_env'],'')
        local=ROOT/'demo/obs.local.json'
        if not secret and local.exists():secret=json.loads(local.read_text(encoding='utf-8'))['password']
        logging.getLogger('obsws_python').setLevel(logging.CRITICAL)
        try:
            self.obs=await asyncio.to_thread(obs.ReqClient,host=info['host'],port=info['port'],password=secret,timeout=5)
            state=await asyncio.to_thread(self.obs.get_record_status)
        except Exception as e:
            self.obs=None;self.report['recording_mode']='manual';self.report['obs_connect_error']=str(e)
            for i in range(5,0,-1):
                await self.p.evaluate('(t)=>window.__demoCaption?.(t)',f'OBS 수동 녹화 · {i}초 후 시작')
                print(f'OBS unavailable: manual recording starts in {i}s',flush=True)
                await asyncio.sleep(1)  # Always five real seconds, independent of SPEED.
            return
        if state.output_active:raise RuntimeError('OBS is already recording; refusing to stop or take ownership of that recording.')
        self.report['obs_before']=response_dict(await asyncio.to_thread(self.obs.get_stats))
        self.report['obs_video']=response_dict(await asyncio.to_thread(self.obs.get_video_settings))
        await asyncio.to_thread(self.obs.start_record);self.owns_record=True
        for _ in range(30):
            if (await asyncio.to_thread(self.obs.get_record_status)).output_active:break
            await asyncio.sleep(.2)
        else:
            self.owns_record=False
            raise RuntimeError('OBS StartRecord did not activate recording. Close the initial configuration wizard and inspect OBS logs.')
        self.report['recording_mode']='obs-websocket'
        self.report['obs_before']=response_dict(await asyncio.to_thread(self.obs.get_stats))

    async def sample_stats(self):
        while not self.stop_stats:
            if self.obs and self.owns_record:
                try:
                    sample=response_dict(await asyncio.to_thread(self.obs.get_stats))
                    sample['seconds']=round(time.monotonic()-self.t0,2);sample['step']=self.caption
                    self.report['obs_samples'].append(sample)
                except Exception as e:self.report.setdefault('stats_errors',[]).append(str(e))
            save(self.out/'run.json',self.report)
            await asyncio.sleep(2)

    async def gpu_check(self):
        await self.p.goto('chrome://gpu');await self.p.wait_for_timeout(3000)
        text=await self.p.evaluate('''()=>{const walk=r=>Array.from(r.children||[]).filter(e=>e.tagName!=='STYLE'&&e.tagName!=='SCRIPT').map(e=>e.shadowRoot?walk(e.shadowRoot):e.children.length?walk(e):e.textContent).join('\\n');return walk(document.body)}''');(self.out/'chrome-gpu.txt').write_text(text,encoding='utf-8')
        await self.shot('gpu')
        good=bool(re.search(r'WebGL:\s*Hardware accelerated',text))
        self.report['hardware_webgl']=good
        if not good:raise RuntimeError('chrome://gpu does not report hardware-accelerated WebGL; see chrome-gpu.txt.')

    async def graph_tour(self):
        await self.click('#tabGraph');await self.pause(5);await self.shot('initial-graph')
        nodes=self.p.locator('#graph svg g[role="button"]')
        count=min(4,await nodes.count())
        if count<1:raise RuntimeError('No graph node buttons rendered')
        # Clicking re-renders the graph; reacquire nodes each time.
        for i in range(count):
            el=self.p.locator('#graph svg g[role="button"]').nth(i)
            await self.scroll_to(el);b=await el.bounding_box();await self.move(b['x']+b['width']/2,b['y']+b['height']/2)
            await self.pause(2);await el.click();await self.pause(2)
        summary=self.p.locator('#graph .graph-summary')
        if await summary.count():
            await self.scroll_to(summary);await self.pause(3)
        if await self.p.locator('#assetSpec').count():
            await self.scroll_to(self.p.locator('#assetSpec'));await self.pause(3)
        await self.scroll_to(self.p.locator('#tabGraph'))

    async def rotate_model(self):
        await self.wait_state('S.result?.hydrated === true && document.querySelector("model-viewer.result-model")?.loaded',180)
        model=self.p.locator('model-viewer.result-model');await self.scroll_to(model)
        b=await model.bounding_box();start_theta=await model.evaluate('(e)=>e.getCameraOrbit().theta')
        # Local model-viewer SmoothControls.pixelLengthToSphericalAngle uses
        # 2*pi*dx/scene.height: total horizontal drag = component height.
        angle=0.;last=start_theta;motions=[]
        for _ in range(12):
            remaining=2*math.pi-angle
            if remaining<math.radians(2):break
            b=await model.bounding_box()
            requested=min(math.pi/2,remaining)
            distance=min(b['width']*.5,b['height']*requested/(2*math.pi))
            x=b['x']+b['width']/2+distance/2;y=b['y']+b['height']*.5
            await self.move(x,y,.12);await self.p.mouse.down()
            await self.move(x-distance,y,max(.4,8*requested/(2*math.pi)));await self.p.mouse.up()
            await asyncio.sleep(.35)
            theta=await model.evaluate('(e)=>e.getCameraOrbit().theta')
            measured=abs(math.atan2(math.sin(theta-last),math.cos(theta-last)))
            motions.append({'requested_degrees':math.degrees(requested),'measured_degrees':math.degrees(measured)})
            angle+=measured;last=theta
        self.report['rotation_degrees']=math.degrees(angle)
        self.report['rotation_motions']=motions
        if angle<math.radians(358):raise RuntimeError('Mouse rotation did not complete the expected full turn')
        for sign in (-1,1):
            for _ in range(16):await self.p.mouse.wheel(0,sign*18);await self.pause(.07)
            await self.pause(2)

    async def scenario(self):
        await self.stage('Step 1. PRISM SCENE · 현장과 자산');await self.pause(3)
        await self.stage('Step 2. 배경 사진 업로드')
        await self.p.locator('#cacheOnly').uncheck()
        photo=fresh_background(ROOT/self.c['background_image'],self.out)
        async with self.p.expect_response(lambda r:r.url.endswith('/scene-api/build') and r.request.method=='POST') as response:
            await self.p.locator('#photo').set_input_files(str(photo))
        res=await response.value
        if not res.ok:raise RuntimeError(await res.text())
        jid=(await res.json())['id'];self.report['scene_job']=jid
        # Existing scene uploader does not preview before build. Show the actual
        # uploaded local photo in a temporary presentation lightbox (not fake UI).
        await self.p.evaluate('''async()=>{const f=document.querySelector('#photo').files[0];const d=document.createElement('div');d.id='demo-source-preview';d.style.cssText='position:fixed;inset:70px 160px 100px;z-index:99999;background:#091721f5;display:flex;align-items:center;justify-content:center;border:1px solid #4d7c89;border-radius:16px';const im=new Image();im.src=URL.createObjectURL(f);im.style.cssText='max-width:95%;max-height:95%;object-fit:contain';d.append(im);document.body.append(d);await im.decode();}''')
        await self.pause(3);await self.shot('uploaded-source')
        await self.p.evaluate('document.querySelector("#demo-source-preview").remove()')
        await self.stage('Step 3. 현장 복원 · 자산 인식 · 관계 분석')
        start=time.monotonic()
        while time.monotonic()-start<self.c['timeout_seconds']:
            r=await self.p.request.get(self.c['base_url']+'/scene-api/jobs/'+jid);job=await r.json()
            if job['status']=='failed':raise RuntimeError('Scene build: '+job['message'])
            if job['status']=='ready':break
            await asyncio.sleep(2)
        else:raise TimeoutError('Scene build timeout')
        scene_id=job['url'].split('/')[-2]
        await self.wait_state('!document.querySelector("#photo").disabled',180)
        if await self.p.evaluate('sceneWorkspace.manifest?.id')!=scene_id:
            self.report['scene_load_retry']=await self.p.locator('#status').inner_text()
            await self.click('[data-scene="'+scene_id+'"]')
        await self.wait_state('window.sceneWorkspace?.placement?.graph?.nodes?.length>0 && !window.sceneWorkspace.loading',180)
        self.report['automatic_scene']=await self.p.evaluate('window.sceneWorkspace.manifest.id')
        await self.graph_tour()
        # Current app lacks authored zones/recommendations for newly uploaded
        # scenes. Explicitly transition to the reviewed SAME-PHOTO operations cache.
        await self.stage('검토된 운영 장면 · 배치 전 자산과 관계 확인')
        scene=self.c['placement_scene']
        await self.click('[data-scene="'+scene+'"]')
        await self.wait_state('window.sceneWorkspace?.manifest?.id==='+json.dumps(scene)+' && !window.sceneWorkspace.loading')
        await self.click('#tabGraph');await self.pause(5)
        self.report['before']=await self.p.evaluate('({nodes:sceneWorkspace.placement.graph.nodes.length,edges:sceneWorkspace.placement.graph.edges.length})')
        await self.shot('operations-before')
        # Keep the scene tab alive, preserving the graph and GLB placement state.
        self.scene_page=self.p
        self.p=await self.context.new_page();self.p.on('pageerror',lambda e:self.report['errors'].append(str(e)))
        await self.fullscreen()
        if self.c.get('freeze_hidden_scene',True):
            self.scene_session=await self.context.new_cdp_session(self.scene_page)
            await self.scene_session.send('Page.setWebLifecycleState',{'state':'frozen'})
        await self.p.goto(self.c['base_url']+'/prismscan-v2.html?page=upload')
        await self.stage('Step 4. 물체 사진 · 이름으로 분리할 대상 선택')
        await self.p.locator('#fi').set_input_files(str(ROOT/self.c['object_image']))
        await self.p.locator('.dz-preview-img').wait_for();await self.pause(3)
        await self.p.locator('.seg-text-input').fill(self.c['object_prompt'])
        await self.click('[onclick="startProc()"]')
        await self.wait_state('S.seg?.selectedId || S.seg?.text?.error || S.seg?.error',600)
        err=await self.p.evaluate('S.seg?.text?.error || S.seg?.error')
        if err:raise RuntimeError('Segmentation: '+err)
        await self.p.locator('#seg-picked-preview img').first.wait_for()
        await self.scroll_to(self.p.locator('.seg-map-work'));await self.pause(3);await self.shot('mask')
        await self.stage('Step 5. 선택한 물체의 3D 메시 생성')
        await self.click('#seg-start-selected')
        await self.wait_state('S.job?.status==="completed" || S.job?.status==="failed"')
        state=await self.p.evaluate('({status:S.job.status,error:S.job.error,job:S.sid})')
        if state['status']!='completed':raise RuntimeError('Mesh: '+str(state['error']))
        self.report['mesh_job']=state['job']
        await self.wait_state('S.result?.hydrated === true',180)
        await self.wait_state('document.querySelector("model-viewer.result-model")?.loaded',180)
        await self.click('[data-env="neutral"]')
        await self.pause(4);await self.shot('mesh')
        await self.stage('3D 메시 · 360° 회전과 확대')
        await self.rotate_model()
        await self.placement_sequence()

    async def placement_sequence(self):
        if self.scene_session:
            await self.scene_session.send('Page.setWebLifecycleState',{'state':'active'})
            await self.scene_session.detach();self.scene_session=None
        self.p=self.scene_page;await self.fullscreen()
        await self.stage('Step 6. 생성 자산 반입 · 지지면에 배치')
        await self.click('#tabEdit');await self.click('#refreshGenerated')
        job=self.report['mesh_job']
        await self.wait_state('Array.from(document.querySelector("#generatedAsset").options).some(o=>o.value==='+json.dumps(job)+')',60)
        await self.p.locator('#generatedAsset').select_option(job);await self.pause(2)
        await self.click('#placeGenerated');await self.wait_state('!!sceneWorkspace.placement.pending',120)
        await self.click('[data-spot="spot-0"]')
        await self.wait_state('!!sceneWorkspace.simulation.draft',30)
        await self.p.locator('#assetHeight').fill(str(self.c['placement_height_m']))
        await self.p.locator('#assetHeight').dispatch_event('change')
        await self.click('#findSafe')
        await self.wait_state('sceneWorkspace.simulation.result?.state==="clear"',20)
        await self.pause(4);await self.shot('placement')
        await self.click('#confirmAsset');await self.wait_state('sceneWorkspace.placement.items.length===1',30)
        await self.pause(4)
        await self.stage('Step 7. 신규 노드 · 지지 관계 자동 갱신')
        await self.click('#tabGraph');await self.pause(5)
        self.report['after']=await self.p.evaluate('({nodes:sceneWorkspace.placement.graph.nodes.length,edges:sceneWorkspace.placement.graph.edges.length})')
        if self.report['after']['nodes']<=self.report['before']['nodes']:raise RuntimeError('Asset registration did not add a graph node')
        asset_id=await self.p.evaluate('(()=>{const p=sceneWorkspace.placement,n=p.graph.nodes.find(n=>n.id===p.items[0].id);return n.asset_id;})()')
        self.report['new_asset_id']=asset_id
        node=self.p.locator('#graph svg g[role="button"]').filter(has=self.p.locator('text',has_text=asset_id))
        if await node.count():
            await self.scroll_to(node.first);await node.first.hover();await self.pause(2);await node.first.click()
        else:raise RuntimeError('New graph asset '+asset_id+' is not visible')
        await self.pause(3);await self.shot('updated-graph')
        await self.stage('Step 8. 자산 대장 · 등록 정보 확인')
        await self.click('#tabAssets')
        rows=self.p.locator('#assetLedger tbody tr');count=await rows.count()
        for i in range(count):
            row=rows.nth(i);await self.scroll_to(row);b=await row.bounding_box();await self.move(b['x']+b['width']/2,b['y']+b['height']/2);await row.click();await self.pause(2)
        await self.shot('asset-register')
        await self.scroll_to(self.p.locator('#tabAssets'))
        await self.stage('Step 9. PRISM · 사진에서 현장 운영까지');await self.pause(3);await self.shot('final')

    async def finish_obs(self):
        if not self.owns_record:return
        self.report['obs_after']=response_dict(await asyncio.to_thread(self.obs.get_stats))
        self.report['obs_record_status']=response_dict(await asyncio.to_thread(self.obs.get_record_status))
        stopped=await asyncio.to_thread(self.obs.stop_record);self.owns_record=False
        path=Path(stopped.output_path);self.report['mkv']=str(path)
        previous_size=-1;stable=0
        for _ in range(30):
            size=path.stat().st_size if path.exists() else 0
            stable=stable+1 if size>0 and size==previous_size else 0
            previous_size=size
            if stable>=3 and not (await asyncio.to_thread(self.obs.get_record_status)).output_active:break
            await asyncio.sleep(.5)
        else:raise RuntimeError('OBS output did not settle after StopRecord; MKV preserved.')
        if not path.exists():raise FileNotFoundError(path)
        dest=path.with_suffix('.mp4');ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        proc=await asyncio.create_subprocess_exec(ffmpeg,'-hide_banner','-nostdin','-n','-i',str(path),'-map','0','-c','copy','-movflags','+faststart',str(dest),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        _,stderr=await proc.communicate();(self.out/'remux.log').write_bytes(stderr)
        if proc.returncode:raise RuntimeError('Remux failed; original MKV preserved. See remux.log')
        self.report['mp4']=str(dest)
        logs=ROOT/'.runtime/obs-portable-32/config/obs-studio/logs'
        if logs.exists():
            latest=max(logs.glob('*.txt'),key=lambda p:p.stat().st_mtime,default=None)
            if latest:(self.out/'obs.log').write_bytes(latest.read_bytes())
        for key in ('render_skipped_frames','render_total_frames','output_skipped_frames','output_total_frames'):
            self.report.setdefault('obs_delta',{})[key]=self.report['obs_after'].get(key,0)-self.report['obs_before'].get(key,0)

    async def run(self):
        metrics=monitor();self.report['monitor']=metrics
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(channel='chrome',headless=False,args=['--kiosk','--window-position=0,0',f'--window-size={metrics["width"]},{metrics["height"]}','--enable-gpu','--use-angle=d3d11','--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding'])
            self.context=await browser.new_context(viewport={'width':metrics['css_width'],'height':metrics['css_height']},device_scale_factor=metrics['scale'],accept_downloads=True)
            await self.context.add_init_script(path=str(ROOT/'demo/overlay.js'))
            self.p=await self.context.new_page();self.p.on('pageerror',lambda e:self.report['errors'].append(str(e)))
            stats=None
            try:
                await self.gpu_check()
                await self.p.goto(self.c['base_url']+'/scene.html')
                await self.p.locator('#scenes .scene-card').first.wait_for(timeout=60000)
                await self.fullscreen()
                self.report['browser_size']=await self.p.evaluate('({width:innerWidth,height:innerHeight,outerWidth,outerHeight,dpr:devicePixelRatio})')
                await self.setup_obs();self.t0=time.monotonic();stats=asyncio.create_task(self.sample_stats())
                await self.scenario()
                if self.report['errors']:raise RuntimeError('Browser script errors: '+str(self.report['errors']))
                self.report['status']='passed'
            except BaseException as e:
                self.report['status']='failed';self.report['failure']={'step':self.caption,'error':str(e),'type':type(e).__name__}
                try:await self.shot('failure');(self.out/'failure.html').write_text(await self.p.content(),encoding='utf-8')
                except Exception:pass
                raise
            finally:
                self.stop_stats=True
                if stats:await stats
                self.report['scenario_seconds']=time.monotonic()-self.t0 if self.t0 else None
                try:await self.finish_obs()
                except Exception as e:self.report['recording_error']=str(e);self.report['status']='failed';print('Recording finalization:',e,flush=True)
                save(self.out/'run.json',self.report)
                (self.out/'timestamps.md').write_text('\n'.join(f'- {s["timecode"]} {s["name"]}' for s in self.report['steps']),encoding='utf-8')
                print('REPORT',str(self.out/'run.json'),flush=True)
                await browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default=str(Path(__file__).with_name('config.json')));parser.add_argument('--speed',type=float);parser.add_argument('--rehearsal',action='store_true');parser.add_argument('--no-captions',action='store_true');args=parser.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    if args.no_captions:config['captions']=False
    if args.speed is not None and args.speed<=0:parser.error('speed must be positive')
    asyncio.run(Demo(config,args).run())

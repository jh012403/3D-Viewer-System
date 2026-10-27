"""Configure only the dedicated portable instance, never an existing user profile."""
import json
import logging
import secrets
import subprocess
import time
from pathlib import Path
import obsws_python as obs
from desktop import monitor

ROOT=Path(__file__).resolve().parents[1]
PORTABLE=ROOT/'.runtime/obs-portable-32'
CONFIG=PORTABLE/'config/obs-studio'

def setup():
    # Never rewrite a running OBS profile.
    running=subprocess.run(['tasklist','/FI','IMAGENAME eq obs64.exe'],capture_output=True,text=True).stdout
    if 'obs64.exe' in running:
        raise RuntimeError('OBS is already running. Close the portable instance before setup.')
    m=monitor();password=secrets.token_urlsafe(32)
    local=ROOT/'demo/obs.local.json'
    local.write_text(json.dumps({'host':'127.0.0.1','port':4455,'password':password}),encoding='utf-8')
    plugin=CONFIG/'plugin_config/obs-websocket';plugin.mkdir(parents=True,exist_ok=True)
    (plugin/'config.json').write_text(json.dumps({'server_enabled':True,'server_port':4455,'auth_required':True,'server_password':password,'alerts_enabled':False,'first_load':False}),encoding='utf-8')
    profile=CONFIG/'basic/profiles/PRISM';profile.mkdir(parents=True,exist_ok=True)
    recordings=ROOT/'storage/obs-demo/recordings';recordings.mkdir(parents=True,exist_ok=True)
    (CONFIG/'global.ini').write_text('[General]\nEnableAutoUpdates=false\n',encoding='utf-8')
    (CONFIG/'user.ini').write_text('[General]\nFirstRun=true\n[Basic]\nProfile=PRISM\nProfileDir=PRISM\n[BasicWindow]\nPreviewEnabled=true\n',encoding='utf-8')
    (profile/'basic.ini').write_text(f'[General]\nName=PRISM\n[Output]\nMode=Advanced\n[AdvOut]\nRecType=Standard\nRecFilePath={recordings.as_posix()}\nRecFormat2=mkv\nRecEncoder=obs_nvenc_h264_tex\nRecTracks=1\nRecRescale=false\n[Video]\nBaseCX={m["width"]}\nBaseCY={m["height"]}\nOutputCX={m["width"]}\nOutputCY={m["height"]}\nFPSType=0\nFPSCommon=60\n[Audio]\nSampleRate=48000\nChannelSetup=Stereo\n',encoding='utf-8')
    (profile/'recordEncoder.json').write_text(json.dumps({'rate_control':'CQP','cqp':18,'preset':'p5','tune':'hq','multipass':'qres','profile':'high','lookahead':True,'psycho_aq':True,'bf':2}),encoding='utf-8')
    exe=PORTABLE/'bin/64bit/obs64.exe'
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    proc=subprocess.Popen([str(exe),'--portable','--profile','PRISM','--collection','PRISM','--disable-shutdown-check','--minimize-to-tray','--websocketipv4only'],cwd=exe.parent,startupinfo=startup)
    logging.getLogger('obsws_python').setLevel(logging.CRITICAL)
    client=None
    for _ in range(60):
        try: client=obs.ReqClient(host='127.0.0.1',port=4455,password=password,timeout=30);break
        except Exception:time.sleep(1)
    if client is None:raise RuntimeError('Portable OBS WebSocket not ready; inspect its log.')
    scenes=client.get_scene_list().scenes
    scene=scenes[0]['sceneName']
    client.set_current_program_scene(scene)
    inputs=client.get_input_list().inputs
    if not any(i['inputName']=='PRISM Display' for i in inputs):
        client.create_input(scene,'PRISM Display','monitor_capture',{'monitor':0,'capture_cursor':False},True)
    else:client.set_input_settings('PRISM Display',{'monitor':0,'capture_cursor':False},True)
    monitors=client.get_input_properties_list_property_items('PRISM Display','monitor_id').property_items
    primary=next((x for x in monitors if x['itemEnabled'] and '@ 0,0' in x['itemName']),None)
    if not primary:raise RuntimeError('Primary monitor at 0,0 was not enumerated by OBS.')
    client.set_input_settings('PRISM Display',{'monitor_id':primary['itemValue'],'capture_cursor':False,'method':2},True)
    # Video demonstration is intentionally silent; avoid recording desktop/mic audio.
    for item in client.get_input_list().inputs:
        if item['inputKind'] in ('wasapi_input_capture','wasapi_output_capture'):
            client.set_input_mute(item['inputName'],True)
    video=client.get_video_settings()
    print(json.dumps({'obs_pid':proc.pid,'monitor':m,'video':{k:getattr(video,k) for k in video.attrs()}},default=str),flush=True)

if __name__=='__main__':setup()

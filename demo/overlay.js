(() => {
  // Chrome's internal GPU diagnostics enforces Trusted Types. Presentation
  // overlays belong only to the local application, never chrome:// pages.
  if(!/^https?:$/.test(location.protocol)||!['127.0.0.1','localhost'].includes(location.hostname))return;
  const boot=()=>{
    if(document.getElementById('prism-demo-overlay'))return;
    const host=document.createElement('div');host.id='prism-demo-overlay';
    host.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:2147483647';
    const root=host.attachShadow({mode:'open'});
    root.innerHTML=`<style>
    #cursor{position:fixed;width:24px;height:24px;border:3px solid #fff;border-radius:50%;background:#17cbdc88;box-shadow:0 0 0 2px #08303e,0 0 16px #36dfff;transform:translate(-50%,-50%);left:50%;top:50%}
    .pulse{position:fixed;width:22px;height:22px;border:3px solid #ffda68;border-radius:50%;animation:ripple .7s ease-out forwards;transform:translate(-50%,-50%)}
    @keyframes ripple{to{width:80px;height:80px;opacity:0}}
    #caption{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);font:600 21px 'Malgun Gothic',sans-serif;letter-spacing:.3px;background:#071723ed;color:#e8fbff;border:1px solid #56bacb;border-radius:14px;padding:13px 26px;box-shadow:0 8px 32px #0008;white-space:nowrap}
    </style><div id='cursor'></div><div id='caption' hidden></div>`;
    document.documentElement.append(host);
    document.addEventListener('pointermove',e=>{const c=root.querySelector('#cursor');c.style.left=e.clientX+'px';c.style.top=e.clientY+'px';},true);
    document.addEventListener('pointerdown',e=>{const r=document.createElement('div');r.className='pulse';r.style.left=e.clientX+'px';r.style.top=e.clientY+'px';root.append(r);setTimeout(()=>r.remove(),750);},true);
    window.__demoCaption=text=>{const c=root.querySelector('#caption');c.textContent=text;c.hidden=!text;};
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();

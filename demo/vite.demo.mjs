// Separate opt-in server; existing frontend files and normal Vite config stay intact.
import base from '../frontend/vite.config.js';
if(process.env.DEMO_MODE!=='1')throw new Error('Set DEMO_MODE=1 to enable prepared demo services');
export default {
  ...base,
  root:new URL('../frontend/',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'),
  plugins:[...base.plugins,{
    name:'prepared-demo-api-setting',
    transformIndexHtml(){return [{tag:'script',children:'window.__AI3D_API_BASE_URL="http://127.0.0.1:8020";',injectTo:'head-prepend'}];}
  }],
  server:{host:'127.0.0.1',port:5174,strictPort:true,proxy:Object.fromEntries(['/scene-api','/scene-cache','/api','/storage','/demo-api'].map(prefix=>[prefix,'http://127.0.0.1:8020']))}
};

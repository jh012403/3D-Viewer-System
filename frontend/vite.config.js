import { resolve } from "node:path";
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";

// Serve Spark's embedded raycast WASM as a normal local asset. Some Chromium
// builds return an empty body when fetching its long data URL.
function sparkWasm(){
  const modulePath=resolve(__dirname,"node_modules/@sparkjsdev/spark/dist/spark.module.js");
  const text=readFileSync(modulePath,"utf8");
  const match=text.match(/new URL\("data:application\/wasm;base64,([^"]+)", import.meta.url\)/);
  if(!match)throw new Error("Spark WASM not found; review pinned Spark version");
  const bytes=Buffer.from(match[1],"base64");
  return {
    name:"spark-local-wasm",
    enforce:"pre",
    configureServer(server){server.middlewares.use("/spark-raycast.wasm",(_req,res)=>{res.setHeader("Content-Type","application/wasm");res.end(bytes);});},
    generateBundle(){this.emitFile({type:"asset",fileName:"spark-raycast.wasm",source:bytes});},
    transform(code,id){if(id.includes("@sparkjsdev/spark")&&code.includes(match[0]))return code.replace(match[0],'new URL("/spark-raycast.wasm", globalThis.location.href)');}
  };
}
export default defineConfig({
  plugins:[sparkWasm()],
  optimizeDeps:{exclude:["@sparkjsdev/spark"]},
  build:{rollupOptions:{input:{
    index:resolve(__dirname,"index.html"),
    scene:resolve(__dirname,"scene.html"),
    prismscan:resolve(__dirname,"prismscan-v2.html")
  }}},
  server:{host:"127.0.0.1",port:5173,proxy:{
    "/scene-api":"http://127.0.0.1:8001",
    "/scene-cache":"http://127.0.0.1:8001",
    "/api":"http://localhost:8000",
    "/storage":"http://localhost:8000"
  }}
});

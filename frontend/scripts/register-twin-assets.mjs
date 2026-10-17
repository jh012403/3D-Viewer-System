import {readFile,writeFile} from 'node:fs/promises';
import {enrichAssets,assetRegister} from '../src/scene/asset-model.js';
for(const scene of ['twin-logistics','twin-laboratory','twin-workbench','twin-factory']){
 const path=`../storage/scene_cache/${scene}/graph.json`,graph=JSON.parse(await readFile(path,'utf8'));graph.scene_id=scene;
 enrichAssets(graph,{ids:new Map(),next:1});
 await writeFile(path,JSON.stringify(graph));await writeFile(`../assets/twin-demo/${scene}/graph.json`,JSON.stringify(graph));
 await writeFile(`../assets/twin-demo/${scene}/asset-register.json`,JSON.stringify(assetRegister(graph),null,2));
 console.log(scene,graph.nodes.length,'assets');
}

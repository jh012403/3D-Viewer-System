import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {SplatMesh, SparkRenderer} from '@sparkjsdev/spark';

export class SceneViewer {
  constructor(container){
    this.container=container;
    this.scene=new THREE.Scene();
    this.scene.background=new THREE.Color('#080c0a');
    this.camera=new THREE.PerspectiveCamera(50,1,.02,200);
    this.renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
    // SHARP's exported coefficients already contain sRGB values.
    this.renderer.outputColorSpace=THREE.LinearSRGBColorSpace;
    this.renderer.toneMapping=THREE.NoToneMapping;
    container.append(this.renderer.domElement);
    this.spark=new SparkRenderer({renderer:this.renderer});
    this.scene.add(this.spark);
    this.controls=new OrbitControls(this.camera,this.renderer.domElement);
    this.controls.enablePan=false;this.controls.enableZoom=false;this.controls.enableDamping=true;
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x75816b,2));
    const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(-2,5,2);this.scene.add(light);
    this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(container);
    this.renderer.setAnimationLoop(()=>{this.controls.update();this.updateEdgeMask();this.renderer.render(this.scene,this.camera);this.afterRender?.();});
  }
  updateEdgeMask(){
    const turn=this.controls.getAzimuthalAngle(),amount=Math.min(1,Math.abs(turn)/THREE.MathUtils.degToRad(this.maxOrbitDegrees||3))*6.5;
    this.renderer.domElement.style.maskImage=amount<.1?'none':`linear-gradient(to ${turn>0?'right':'left'},transparent 0%,black ${amount.toFixed(2)}%,black 100%)`;
  }
  resize(){
    const w=this.container.clientWidth,h=this.container.clientHeight;
    const aspect=this.manifest?this.manifest.camera.width/this.manifest.camera.height:w/h;
    const rw=Math.min(w,h*aspect),rh=rw/aspect;
    this.renderer.setSize(rw,rh);this.camera.aspect=aspect;this.updateProjection();
  }
  updateProjection(){
    if(!this.manifest){this.camera.updateProjectionMatrix();return;}
    const c=this.manifest.camera,n=this.camera.near;
    // Preserve the exact SHARP input K, including a non-central principal point.
    this.camera.projectionMatrix.makePerspective(-c.cx*n/c.fx,(c.width-c.cx)*n/c.fx,c.cy*n/c.fy,-(c.height-c.cy)*n/c.fy,n,this.camera.far);
    this.camera.projectionMatrixInverse.copy(this.camera.projectionMatrix).invert();
  }
  async load(url){
    const response=await fetch(url);if(!response.ok)throw new Error('씬 캐시를 불러올 수 없습니다.');
    const m=await response.json(); const base=new URL(url,location.href);
    const abs=(p)=>new URL(p,base).href;
    const mesh=new SplatMesh({url:abs(m.splat)});
    try{await mesh.initialized;}catch(e){mesh.dispose();throw e;}
    this.onLoadProgress?.(1);
    if(this.splat){this.scene.remove(this.splat);this.splat.dispose();}
    if(this.surface){this.scene.remove(this.surface);this.surface.geometry.dispose();this.surface.material.dispose();}
    this.manifest=m;this.base=base;this.splat=mesh;mesh.rotation.x=Math.PI;this.scene.add(mesh);
    const res=await fetch(abs(m.surface));if(!res.ok)throw new Error('표면 캐시 없음');
    const surface=await res.json();const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(surface.positions,3));
    geometry.setIndex(surface.indices);geometry.computeVertexNormals();
    this.surface=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color:0xb8dfa4,wireframe:true,transparent:true,opacity:.16,side:THREE.DoubleSide,depthWrite:false}));
    this.surface.visible=false;this.scene.add(this.surface);
    this.reset(false);this.resize();this.container.querySelector('.empty').hidden=true;
    this.container.dataset.loaded='true';return m;
  }
  reset(original=true){
    if(!this.manifest)return;
    const {camera:c,orbit_degrees:deg}=this.manifest;
    this.camera.fov=THREE.MathUtils.radToDeg(2*Math.atan(c.height/(2*c.fy)));
    this.camera.zoom=1;
    this.camera.position.fromArray(c.position);this.camera.up.fromArray(c.up);
    this.controls.target.fromArray(c.target);
    if(this.manifest.presentation?.orbit_radius_m){
      this.controls.target.sub(this.camera.position).normalize().multiplyScalar(this.manifest.presentation.orbit_radius_m).add(this.camera.position);
    }
    this.maxOrbitDegrees=Math.min(3,deg||3);
    const angle=THREE.MathUtils.degToRad(this.maxOrbitDegrees);
    this.controls.minAzimuthAngle=-angle;this.controls.maxAzimuthAngle=angle;
    const vertical=THREE.MathUtils.degToRad(this.manifest.presentation?.vertical_degrees??deg*.3);
    this.controls.minPolarAngle=Math.PI/2-vertical;this.controls.maxPolarAngle=Math.PI/2+vertical;
    this.controls.update();this.updateProjection();
  }
}

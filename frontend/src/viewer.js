import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";

class ViewerLoadError extends Error {
  constructor(type, message, diagnostics = {}) {
    super(message);
    this.name = "ViewerLoadError";
    this.type = type;
    this.diagnostics = diagnostics;
  }
}

export class ResultViewer {
  constructor(container) {
    this.container = container;
    this.container.dataset.viewerReady = "true";
    this.container.dataset.viewerMode = "image_to_3d";
    this.container.dataset.meshLoaded = "false";

    this.clock = new THREE.Clock();
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x08111d);

    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
    this.camera.position.set(3.5, 2.4, 4.8);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.container.appendChild(this.renderer.domElement);

    this.overlay = this.createOverlay();
    this.container.appendChild(this.overlay.root);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.target.set(0, 0.8, 0);
    this.controls.maxDistance = 18;

    this.group = new THREE.Group();
    this.scene.add(this.group);

    this.floorGrid = new THREE.GridHelper(14, 14, 0x8cd6d1, 0x214052);
    this.floorGrid.position.y = -0.02;
    this.scene.add(this.floorGrid);

    this.ambientLight = new THREE.AmbientLight(0xffffff, 1.15);
    this.scene.add(this.ambientLight);

    this.hemiLight = new THREE.HemisphereLight(0xf4f8ff, 0x0d141b, 1.1);
    this.scene.add(this.hemiLight);

    this.keyLight = new THREE.DirectionalLight(0xfbf6ef, 1.95);
    this.keyLight.position.set(5.5, 7, 6.5);
    this.scene.add(this.keyLight);

    this.fillLight = new THREE.DirectionalLight(0xdbe7ee, 0.85);
    this.fillLight.position.set(-4.5, 3.6, -3.5);
    this.scene.add(this.fillLight);

    this.rayKeys = new Set();
    this.isSceneMode = false;
    this.status = "idle";
    this.message = "Choose a completed job to inspect the generated mesh.";
    this.diagnostics = {};
    this.viewerLoaded = false;
    this.viewerFailed = false;

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);

    this.onKeyDown = (event) => {
      this.rayKeys.add(event.key.toLowerCase());
    };
    this.onKeyUp = (event) => {
      this.rayKeys.delete(event.key.toLowerCase());
    };
    window.addEventListener("keydown", this.onKeyDown);
    window.addEventListener("keyup", this.onKeyUp);

    this.resize();
    this.setState("idle", {
      message: "Choose a completed job to inspect the generated mesh."
    });
    this.animate();
  }

  createOverlay() {
    const root = document.createElement("div");
    root.className = "viewer-overlay";

    const badge = document.createElement("span");
    badge.className = "viewer-overlay-badge";

    const title = document.createElement("strong");
    title.className = "viewer-overlay-title";

    const text = document.createElement("p");
    text.className = "viewer-overlay-text";

    root.append(badge, title, text);
    return { root, badge, title, text };
  }

  resize() {
    const width = this.container.clientWidth || 1;
    const height = this.container.clientHeight || 1;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  clearGroup() {
    while (this.group.children.length > 0) {
      const child = this.group.children[0];
      this.group.remove(child);
      child.traverse?.((node) => {
        if (node.geometry) {
          node.geometry.dispose();
        }
        if (node.material) {
          if (Array.isArray(node.material)) {
            node.material.forEach((material) => material.dispose());
          } else {
            node.material.dispose();
          }
        }
      });
    }
  }

  applyKeyboardMovement(delta) {
    if (!this.isSceneMode) {
      return;
    }

    const speed = 2.4 * delta;
    const forward = new THREE.Vector3();
    this.camera.getWorldDirection(forward);
    forward.y = 0;
    forward.normalize();

    const right = new THREE.Vector3().crossVectors(forward, this.camera.up).normalize();
    const move = new THREE.Vector3();

    if (this.rayKeys.has("w")) move.add(forward);
    if (this.rayKeys.has("s")) move.sub(forward);
    if (this.rayKeys.has("a")) move.sub(right);
    if (this.rayKeys.has("d")) move.add(right);

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(speed);
      this.camera.position.add(move);
      this.controls.target.add(move);
    }
  }

  prepare(jobType, options = {}) {
    this.clearGroup();
    this.isSceneMode = false;
    this.container.dataset.viewerMode = jobType;
    this.container.dataset.meshLoaded = "false";
    this.container.dataset.meshUrl = "";

    this.floorGrid.visible = false;
    this.controls.enablePan = false;
    this.controls.autoRotate = false;
    this.controls.autoRotateSpeed = 0;
    this.configureLighting(jobType);
    this.resetCamera(jobType);

    if (!options.preserveStatus) {
      this.setState("idle", {
        message: "The object viewer is ready. Load a mesh to inspect the generated object."
      });
    }
  }

  resetCamera() {
    this.scene.background = new THREE.Color(0x0b131b);
    this.camera.position.set(3.5, 2.4, 4.8);
    this.controls.target.set(0, 0.8, 0);
    this.controls.maxDistance = 24;
    this.controls.minDistance = 0.2;
    this.camera.near = 0.01;
    this.camera.far = 1000;
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }

  configureLighting() {
    this.ambientLight.intensity = 1.42;
    this.hemiLight.intensity = 1.35;
    this.keyLight.intensity = 1.72;
    this.keyLight.position.set(4.5, 6.4, 5.5);
    this.fillLight.intensity = 0.72;
    this.fillLight.position.set(-3.2, 3.4, -2.8);
  }

  setState(status, details = {}) {
    this.status = status;
    this.viewerLoaded = status === "loaded";
    this.viewerFailed = status === "failed";
    this.message = details.message ?? this.message;
    this.diagnostics = details.diagnostics ?? this.diagnostics ?? {};

    this.container.dataset.viewerState = status;
    this.container.dataset.viewerLoaded = String(this.viewerLoaded);
    this.container.dataset.viewerFailed = String(this.viewerFailed);

    if (details.meshUrl) {
      this.container.dataset.meshUrl = details.meshUrl;
    }
    if (details.meshLoaded !== undefined) {
      this.container.dataset.meshLoaded = String(details.meshLoaded);
    }

    const overlayCopy = this.describeOverlay(status, this.message);
    this.overlay.badge.textContent = overlayCopy.badge;
    this.overlay.title.textContent = overlayCopy.title;
    this.overlay.text.textContent = overlayCopy.text;
    this.overlay.root.dataset.state = status;
    this.overlay.root.hidden = status === "loaded";
    this.overlay.root.style.display = status === "loaded" ? "none" : "grid";

    this.container.dispatchEvent(
      new CustomEvent("viewer-statechange", {
        detail: {
          status: this.status,
          viewerLoaded: this.viewerLoaded,
          viewerFailed: this.viewerFailed,
          message: this.message,
          diagnostics: this.diagnostics
        }
      })
    );
  }

  describeOverlay(status, message) {
    if (status === "loaded") {
      return {
        badge: "Viewer loaded",
        title: "Mesh ready",
        text: message || "The mesh rendered successfully in the browser viewer."
      };
    }

    if (status === "loading") {
      return {
        badge: "Loading",
        title: "Fetching mesh",
        text: message || "Downloading and parsing the mesh file."
      };
    }

    if (status === "failed") {
      return {
        badge: "Viewer failed",
        title: "Mesh render error",
        text: message || "The browser viewer could not render the mesh file."
      };
    }

    return {
      badge: "Viewer ready",
      title: "Awaiting mesh",
      text: message || "Choose a completed job to inspect the generated mesh."
    };
  }

  async load(jobType, meshUrl) {
    this.prepare(jobType, { preserveStatus: true });

    if (!meshUrl) {
      const error = new ViewerLoadError(
        "mesh_unavailable",
        "No mesh URL was provided for the viewer.",
        { meshUrl: null }
      );
      this.setState("failed", {
        message: error.message,
        diagnostics: { errorType: error.type, ...error.diagnostics },
        meshLoaded: false
      });
      throw error;
    }

    const normalizedMeshUrl = meshUrl.split("?")[0].toLowerCase();
    let loaderType = "gltf";
    if (normalizedMeshUrl.endsWith(".ply")) {
      loaderType = "ply";
    } else if (normalizedMeshUrl.endsWith(".obj")) {
      loaderType = "obj";
    } else if (normalizedMeshUrl.endsWith(".glb") || normalizedMeshUrl.endsWith(".gltf")) {
      loaderType = "gltf";
    }
    const diagnostics = {
      meshUrl,
      loaderType,
      fetchStatus: null,
      parseStatus: "pending"
    };

    this.setState("loading", {
      message: `Loading ${loaderType.toUpperCase()} mesh from ${meshUrl}.`,
      diagnostics,
      meshUrl,
      meshLoaded: false
    });

    try {
      const response = await fetch(meshUrl, { cache: "no-store" });
      diagnostics.fetchStatus = response.status;

      if (!response.ok) {
        throw new ViewerLoadError(
          "network_error",
          `Viewer failed to fetch the mesh file (${response.status}).`,
          diagnostics
        );
      }

      const loaded =
        loaderType === "gltf"
          ? await this.parseGltf(await response.arrayBuffer(), meshUrl, diagnostics)
          : loaderType === "ply"
            ? this.parsePly(await response.arrayBuffer(), diagnostics)
            : this.parseObj(await response.text(), diagnostics);

      const renderableCount = this.countRenderables(loaded);
      diagnostics.renderableCount = renderableCount;
      diagnostics.parseStatus = "success";

      if (renderableCount === 0) {
        throw new ViewerLoadError(
          "empty_scene",
          "Viewer loaded the file, but it did not contain any renderable geometry.",
          diagnostics
        );
      }

      this.group.add(loaded);
      Object.assign(diagnostics, this.fitCameraToObject(loaded));

      this.setState("loaded", {
        message: "Mesh rendered successfully in the browser viewer.",
        diagnostics,
        meshUrl,
        meshLoaded: true
      });

      return loaded;
    } catch (error) {
      const normalized = this.normalizeError(error, diagnostics);
      this.setState("failed", {
        message: normalized.message,
        diagnostics: {
          errorType: normalized.type,
          ...normalized.diagnostics
        },
        meshUrl,
        meshLoaded: false
      });
      throw normalized;
    }
  }

  normalizeError(error, diagnostics) {
    if (error instanceof ViewerLoadError) {
      return error;
    }

    return new ViewerLoadError(
      "loader_parse_error",
      error?.message || "Viewer failed while parsing the mesh file.",
      diagnostics
    );
  }

  parseGltf(buffer, meshUrl, diagnostics) {
    return new Promise((resolve, reject) => {
      const loader = new GLTFLoader();
      const basePath = meshUrl.slice(0, meshUrl.lastIndexOf("/") + 1);

      loader.parse(
        buffer,
        basePath,
        (gltf) => {
          this.prepareLoadedMaterials(gltf.scene);
          resolve(gltf.scene);
        },
        (error) => {
          diagnostics.parseStatus = "failed";
          reject(
            new ViewerLoadError(
              "loader_parse_error",
              "Viewer failed to parse the GLB asset.",
              diagnostics
            )
          );
        }
      );
    });
  }

  parseObj(text, diagnostics) {
    try {
      const loader = new OBJLoader();
      const obj = loader.parse(text);
      obj.traverse((node) => {
        if (node.isMesh) {
          node.material = new THREE.MeshStandardMaterial({
            color: 0xd79f76,
            roughness: 0.9,
            metalness: 0.03
          });
          node.castShadow = true;
          node.receiveShadow = true;
        }
      });
      return obj;
    } catch (error) {
      diagnostics.parseStatus = "failed";
      throw new ViewerLoadError(
        "loader_parse_error",
        "Viewer failed to parse the OBJ asset.",
        diagnostics
      );
    }
  }

  parsePly(buffer, diagnostics) {
    try {
      const loader = new PLYLoader();
      const geometry = loader.parse(buffer);
      const position = geometry.getAttribute("position");
      if (!position || position.count === 0) {
        throw new ViewerLoadError(
          "empty_scene",
          "Viewer loaded the PLY file, but no vertex positions were found.",
          diagnostics
        );
      }

      const hasFaces = Boolean(geometry.index && geometry.index.count > 0);
      const hasColor = Boolean(geometry.getAttribute("color"));
      diagnostics.plyHasFaces = hasFaces;
      diagnostics.plyHasColor = hasColor;

      let object;
      if (hasFaces) {
        if (!geometry.getAttribute("normal")) {
          geometry.computeVertexNormals();
        }
        object = new THREE.Mesh(
          geometry,
          new THREE.MeshStandardMaterial({
            color: 0xd4d9df,
            roughness: 0.9,
            metalness: 0.03,
            flatShading: false,
            vertexColors: hasColor
          })
        );
      } else {
        object = new THREE.Points(
          geometry,
          new THREE.PointsMaterial({
            size: 0.009,
            sizeAttenuation: true,
            vertexColors: hasColor,
            color: hasColor ? 0xffffff : 0x9fe8ff
          })
        );
      }
      object.castShadow = false;
      object.receiveShadow = false;
      return object;
    } catch (error) {
      diagnostics.parseStatus = "failed";
      if (error instanceof ViewerLoadError) {
        throw error;
      }
      throw new ViewerLoadError(
        "loader_parse_error",
        "Viewer failed to parse the PLY asset.",
        diagnostics
      );
    }
  }

  countRenderables(object) {
    let count = 0;
    object.traverse?.((node) => {
      if (node.isMesh || node.isPoints || node.isLineSegments || node.isLine) {
        count += 1;
      }
    });
    return count;
  }

  prepareLoadedMaterials(object) {
    object.traverse((node) => {
      if (!node.isMesh) {
        return;
      }

      if (node.geometry && !node.geometry.attributes.normal) {
        node.geometry.computeVertexNormals();
      }

      if (Array.isArray(node.material)) {
        node.material.forEach((material) => {
          material.side = THREE.DoubleSide;
          material.needsUpdate = true;
        });
      } else if (node.material) {
        node.material.side = THREE.DoubleSide;
        node.material.needsUpdate = true;
      }
      node.castShadow = true;
      node.receiveShadow = true;
    });
  }

  fitCameraToObject(object) {
    const box = new THREE.Box3().setFromObject(object);

    if (box.isEmpty()) {
      throw new ViewerLoadError(
        "invalid_bbox",
        "Viewer could not compute a valid bounding box for the mesh.",
        { bboxValid: false }
      );
    }

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = size.length() * 0.5;

    if (!Number.isFinite(radius) || radius <= 0) {
      throw new ViewerLoadError(
        "invalid_bbox",
        "Viewer detected an invalid mesh size while framing the camera.",
        {
          bboxValid: false,
          bboxSize: { x: size.x, y: size.y, z: size.z }
        }
      );
    }

    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    const distance = (radius / Math.sin(fov / 2)) * 1.35;
    const direction = new THREE.Vector3(1, 0.58, 1).normalize();
    const cameraPosition = center.clone().add(direction.multiplyScalar(distance));

    this.controls.target.copy(center);
    this.camera.position.copy(cameraPosition);
    this.camera.near = Math.max(radius / 100, 0.01);
    this.camera.far = Math.max(radius * 60, 50);
    this.camera.updateProjectionMatrix();

    this.floorGrid.position.set(0, -0.02, 0);
    this.floorGrid.scale.set(1, 1, 1);
    this.controls.maxDistance = Math.max(distance * 4, 8);
    this.controls.minDistance = Math.max(radius / 20, 0.05);

    this.camera.lookAt(center);
    this.controls.update();

    return {
      bboxValid: true,
      bboxCenter: {
        x: Number(center.x.toFixed(4)),
        y: Number(center.y.toFixed(4)),
        z: Number(center.z.toFixed(4))
      },
      bboxSize: {
        x: Number(size.x.toFixed(4)),
        y: Number(size.y.toFixed(4)),
        z: Number(size.z.toFixed(4))
      },
      cameraPosition: {
        x: Number(this.camera.position.x.toFixed(4)),
        y: Number(this.camera.position.y.toFixed(4)),
        z: Number(this.camera.position.z.toFixed(4))
      },
      framingStatus: "success"
    };
  }

  showFailure(jobType, message, diagnostics = {}) {
    this.prepare(jobType, { preserveStatus: true });
    this.setState("failed", {
      message,
      diagnostics,
      meshLoaded: false
    });
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    const delta = this.clock.getDelta();
    this.applyKeyboardMovement(delta);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.resizeObserver.disconnect();
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
    this.controls.dispose();
    this.renderer.dispose();
  }
}

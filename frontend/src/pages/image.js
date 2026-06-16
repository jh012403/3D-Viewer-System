const steps = [
  { id: "uploading", label: "Uploading" },
  { id: "segmenting", label: "Selecting Object" },
  { id: "metadata", label: "Reading Metadata" },
  { id: "preprocess", label: "Preparing Image" },
  { id: "processing", label: "Building 3D Geometry" },
  { id: "cleanup", label: "DCC Cleanup" },
  { id: "rendering", label: "Rendering Viewer" },
  { id: "completed", label: "Completed" }
];

export const imageReconstructionHead = "trellis";
export const imageQualityMode = "high_quality";

function progressFromState({ localPhase, job, viewerState }) {
  if (localPhase === "restoring") {
    return {
      percent: 12,
      step: "uploading",
      label: "Loading job",
      description: "Restoring an existing image generation run.",
      tone: "neutral"
    };
  }

  if (localPhase === "uploading") {
    return {
      percent: 16,
      step: "uploading",
      label: "Uploading",
      description: "Saving your image and creating a generation job.",
      tone: "neutral"
    };
  }

  if (localPhase === "segmenting") {
    return {
      percent: 26,
      step: "segmenting",
      label: "Detecting Objects",
      description: "Running SAM3 with your text prompt to cut out the target object.",
      tone: "neutral"
    };
  }

  if (localPhase === "segment_select") {
    return {
      percent: 32,
      step: "segmenting",
      label: "Select Target Object",
      description: "Pick the object you want to model, then continue generation.",
      tone: "neutral"
    };
  }

  if (!job) {
    return {
      percent: 0,
      step: "uploading",
      label: "Ready",
      description: "Upload a single image to generate a polished 3D object with the high-quality path.",
      tone: "neutral"
    };
  }

  if (job.status === "queued") {
    return {
      percent: 24,
      step: "uploading",
      label: "Uploading",
      description: "Your upload is stored. Waiting for the image worker to start.",
      tone: "neutral"
    };
  }

  if (job.status === "running") {
    if (job.stage === "image_preprocess_running") {
      return {
        percent: 34,
        step: "preprocess",
        label: "Preparing Image",
        description: "Extracting the foreground, centering the subject, and normalizing the image for 3D generation.",
        tone: "neutral"
      };
    }

    if (job.stage === "multiview_prior_running") {
      return {
        percent: 52,
        step: "preprocess",
        label: "Generating Multi-View Prior",
        description: "Synthesizing supporting views so the geometry stage can build a more convincing 3D object.",
        tone: "neutral"
      };
    }

    if (job.stage === "mesh_cleanup_running") {
      return {
        percent: 86,
        step: "cleanup",
        label: "DCC Cleanup",
        description: "Cleaning fragments, aligning the object to the ground, and normalizing scale and pivot.",
        tone: "neutral"
      };
    }

    if (job.stage === "asset_metadata_running") {
      return {
        percent: 40,
        step: "metadata",
        label: "Reading Metadata",
        description: "Extracting semantic metadata and choosing category-aware DCC policies.",
        tone: "neutral"
      };
    }

    if (job.stage === "material_package_running") {
      return {
        percent: 90,
        step: "cleanup",
        label: "Building Materials",
        description: "Parsing GLB PBR data, validating texture maps, and generating fallback maps.",
        tone: "neutral"
      };
    }

    return {
      percent: 72,
      step: "processing",
      label: "Building 3D Geometry",
      description: "Running the TRELLIS.2 high-quality generation path.",
      tone: "neutral"
    };
  }

  if (job.status === "failed") {
    return {
      percent: 100,
      step: job.stage === "image_preprocess_running" ? "preprocess" : "processing",
      label: "Generation failed",
      description: job.error || "The image pipeline failed before a mesh was produced.",
      tone: "failed"
    };
  }

  if (viewerState?.status === "failed") {
    return {
      percent: 100,
      step: "completed",
      label: "Completed",
      description: "The mesh is ready, but the browser viewer could not render it.",
      tone: "warning"
    };
  }

  if (viewerState?.status === "loaded") {
    return {
      percent: 100,
      step: "completed",
      label: "Completed",
      description: "Your 3D object is ready to inspect and download.",
      tone: "success"
    };
  }

  return {
    percent: 92,
    step: "rendering",
    label: "Rendering Viewer",
    description: "The mesh is ready. Loading it into the browser viewer.",
    tone: "neutral"
  };
}

export const imagePage = {
  route: "/image",
  jobType: "image_to_3d",
  title: "Image to 3D Object",
  description: "Generate a 3D object from a single image.",
  uploadLabel: "Upload image",
  promptLabel: "Target object",
  promptPlaceholder: "dinosaur, chair, sneaker, snack package",
  uploadHint:
    "Use one clear subject, keep the full object visible, minimize occlusion, and describe the object you want SAM3 to cut out.",
  accept: "image/*",
  generateLabel: "Generate",
  viewerTitle: "Generated Object",
  viewerToolbarPrimary: "Mouse: orbit / zoom",
  viewerToolbarSecondary: "Object viewer",
  viewerIdleSummary: "The generated object will appear here once the job is complete.",
  viewerLoadedSummary: "Inspect the generated mesh in the viewer or download the GLB below.",
  viewerFailedSummary: "The mesh is ready, but the browser viewer could not render it. Download it to inspect offline.",
  idleEmptyBadge: "Image Generation",
  idleEmptyTitle: "Create a 3D object from one image",
  idleEmptyCopy: "Upload an image and the finished mesh will replace this placeholder.",
  downloadLabel: "Download object_mesh.glb",
  downloadFilename: "object_mesh.glb",
  downloadIdleCopy: "A download link will appear here once the mesh is ready.",
  requestedReconstructionHead: imageReconstructionHead,
  requestedImageQualityMode: imageQualityMode,
  steps,
  resolveProgress: progressFromState
};

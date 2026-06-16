import "./style.css";

import {
  createJob,
  createJobExport,
  createSegmentationTextPrompt,
  getJob,
  getJobResult,
  listJobExports,
  uploadAsset
} from "./api.js";
import { imagePage } from "./pages/image.js";
import { renderHomePage } from "./pages/home.js";
import { currentPath, initRouter, navigate, readQueryParam } from "./router.js";
import { ResultViewer } from "./viewer.js";

const app = document.querySelector("#app");

const generationPages = {
  [imagePage.route]: imagePage
};

let currentCleanup = null;

function renderShell(activePath, content) {
  const navItems = [
    { path: "/", label: "Home" },
    { path: "/image", label: "Image to 3D" }
  ];

  const navMarkup = navItems
    .map((item) => {
      const active = item.path === activePath;
      return `
        <a
          class="nav-link${active ? " is-active" : ""}"
          href="${item.path}"
          data-nav="${item.path}"
          ${active ? 'aria-current="page"' : ""}
        >${item.label}</a>
      `;
    })
    .join("");

  return `
    <div class="app-shell">
      <header class="topbar">
        <a class="brand" href="/" data-nav="/">
          <span class="brand-mark">AI</span>
          <span class="brand-copy">
            <strong>AI 3D Service</strong>
            <span>Generate usable 3D objects from images</span>
          </span>
        </a>
        <nav class="topbar-nav">${navMarkup}</nav>
      </header>
      <main class="app-main">${content}</main>
    </div>
  `;
}

  function renderGenerationPage(page) {

  const stepsMarkup = page.steps
    .map(
      (step) => `
        <li class="progress-step" data-step-id="${step.id}">
          <span class="step-dot"></span>
          <span>${step.label}</span>
        </li>
      `
    )
    .join("");

  const segmentationPickerMarkup =
    page.jobType === "image_to_3d"
      ? `
        <section id="segment-picker" class="segment-picker panel-surface is-hidden">
          <p class="page-eyebrow">Object Selection</p>
          <h2 class="segment-title">Choose the target object</h2>
          <p id="segment-copy" class="field-hint">
            Select the object to model in 3D, then continue generation.
          </p>
          <div id="segment-candidates" class="segment-candidates"></div>
          <div class="segment-actions">
            <button id="confirm-segment-button" class="primary-button" type="button" disabled>Use selected object</button>
            <span id="segment-selection-copy" class="field-hint">No object selected yet.</span>
          </div>
        </section>
      `
      : "";

  return `
    <section class="generator-layout" data-job-type="${page.jobType}">
      <aside class="control-panel panel-surface">
        <p class="page-eyebrow">${page.title}</p>
        <h1 class="generator-title">${page.title}</h1>
        <p class="page-copy">${page.description}</p>

        <form id="job-form" class="generator-form">
          <label class="upload-field">
            <span class="field-label">${page.uploadLabel}</span>
            <input id="asset-file" type="file" accept="${page.accept}" required />
            <span id="selected-file-name" class="selected-file">No file selected yet</span>
          </label>
          <label class="upload-field">
            <span class="field-label">${page.promptLabel || "Target object"}</span>
            <input
              id="object-prompt"
              class="text-input"
              type="text"
              placeholder="${page.promptPlaceholder || "chair, sneaker, dinosaur"}"
              autocomplete="off"
              required
            />
          </label>
          <p class="field-hint">${page.uploadHint}</p>
          <button id="generate-button" class="primary-button" type="submit">${page.generateLabel}</button>
        </form>
        ${segmentationPickerMarkup}

        <section id="progress-card" class="progress-card panel-surface" data-tone="neutral">
          <div class="progress-head">
            <span id="progress-kicker" class="progress-kicker">Ready</span>
            <span id="progress-percent" class="progress-percent">0%</span>
          </div>
          <div class="progress-bar">
            <div id="progress-bar-fill" class="progress-bar-fill"></div>
          </div>
          <strong id="progress-label" class="progress-label">Upload a file to begin</strong>
          <p id="progress-message" class="progress-message">${page.resolveProgress({ localPhase: "idle", job: null, viewerState: null }).description}</p>
          <ul id="progress-step-list" class="progress-steps">${stepsMarkup}</ul>
          <p id="active-job" class="active-job">No active job yet.</p>
        </section>

        <div id="status-banner" class="notice-card is-hidden"></div>

        <section class="download-card panel-surface">
          <a id="download-link" class="secondary-button is-hidden" href="#" download>${page.downloadLabel}</a>
          <p id="download-copy" class="field-hint">${page.downloadIdleCopy}</p>
        </section>
      </aside>

      <section class="viewer-column">
        <div id="viewer-empty" class="viewer-empty-state panel-surface">
          <span id="empty-badge" class="empty-badge">${page.idleEmptyBadge}</span>
          <h2 id="empty-title">${page.idleEmptyTitle}</h2>
          <p id="empty-copy">${page.idleEmptyCopy}</p>
        </div>

        <div id="viewer-panel" class="viewer-panel is-hidden">
          <div class="viewer-shell panel-surface">
            <div class="viewer-toolbar">
              <span>${page.viewerToolbarPrimary}</span>
              <span>${page.viewerToolbarSecondary}</span>
            </div>
            <div id="viewer-root" class="viewer-root"></div>
          </div>
          <div class="viewer-footer panel-surface">
            <h2>${page.viewerTitle}</h2>
            <p id="viewer-summary">${page.viewerIdleSummary}</p>
          </div>
          <div id="asset-inspector" class="asset-inspector is-hidden">
            <section class="inspector-panel panel-surface">
              <div class="inspector-head">
                <p class="page-eyebrow">PBR Material</p>
                <strong>Material Package</strong>
              </div>
              <dl id="material-list" class="inspector-list"></dl>
            </section>
            <section class="inspector-panel panel-surface">
              <div class="inspector-head">
                <p class="page-eyebrow">Semantic Metadata</p>
                <strong>Asset Metadata</strong>
              </div>
              <dl id="metadata-list" class="inspector-list"></dl>
            </section>
          </div>
        </div>
      </section>
    </section>
  `;
}

function decorateFailureMessage(job) {
  return job?.error || "Generation failed.";
}

function buildHomeView() {
  document.title = "AI 3D Service";
  app.innerHTML = renderShell("/", renderHomePage());
}

function buildGenerationView(page) {
  document.title = `${page.title} | AI 3D Service`;
  app.innerHTML = renderShell(page.route, renderGenerationPage(page));
  return mountGenerationPage(page);
}

function mountRoute(path) {
  if (currentCleanup) {
    currentCleanup();
    currentCleanup = null;
  }

  if (path === "/") {
    buildHomeView();
    return;
  }

  const page = generationPages[path];
  if (!page) {
    buildHomeView();
    return;
  }

  currentCleanup = buildGenerationView(page);
}

function mountGenerationPage(page) {
  const form = document.querySelector("#job-form");
  const fileInput = document.querySelector("#asset-file");
  const objectPromptInput = document.querySelector("#object-prompt");
  const generateButton = document.querySelector("#generate-button");
  const segmentPicker = document.querySelector("#segment-picker");
  const segmentCopy = document.querySelector("#segment-copy");
  const segmentCandidates = document.querySelector("#segment-candidates");
  const confirmSegmentButton = document.querySelector("#confirm-segment-button");
  const segmentSelectionCopy = document.querySelector("#segment-selection-copy");
  const selectedFileName = document.querySelector("#selected-file-name");
  const progressCard = document.querySelector("#progress-card");
  const progressKicker = document.querySelector("#progress-kicker");
  const progressPercent = document.querySelector("#progress-percent");
  const progressBarFill = document.querySelector("#progress-bar-fill");
  const progressLabel = document.querySelector("#progress-label");
  const progressMessage = document.querySelector("#progress-message");
  const progressSteps = Array.from(document.querySelectorAll(".progress-step"));
  const activeJob = document.querySelector("#active-job");
  const statusBanner = document.querySelector("#status-banner");
  const downloadLink = document.querySelector("#download-link");
  const downloadCopy = document.querySelector("#download-copy");
  const viewerPanel = document.querySelector("#viewer-panel");
  const viewerEmpty = document.querySelector("#viewer-empty");
  const emptyBadge = document.querySelector("#empty-badge");
  const emptyTitle = document.querySelector("#empty-title");
  const emptyCopy = document.querySelector("#empty-copy");
  const viewerRoot = document.querySelector("#viewer-root");
  const viewerSummary = document.querySelector("#viewer-summary");
  const assetInspector = document.querySelector("#asset-inspector");
  const materialList = document.querySelector("#material-list");
  const metadataList = document.querySelector("#metadata-list");
  const viewer = new ResultViewer(viewerRoot);
  viewer.prepare(page.jobType);

  let poller = null;
  const state = {
    localPhase: "idle",
    job: null,
    result: null,
    exports: [],
    exportLoadingFormat: null,
    exportError: null,
    pendingUpload: null,
    segmentation: {
      enabled: page.jobType === "image_to_3d",
      loading: false,
      candidates: [],
      selectedCandidateId: null,
      error: null
    },
    viewerState: {
      status: "idle",
      message: page.viewerIdleSummary
    }
  };

  function clearPoller() {
    if (poller) {
      clearInterval(poller);
      poller = null;
    }
  }

  function stepIndex(stepId) {
    return page.steps.findIndex((step) => step.id === stepId);
  }

  function setBusy(isBusy) {
    fileInput.disabled = isBusy;
    if (objectPromptInput) {
      objectPromptInput.disabled = isBusy;
    }
    generateButton.disabled = isBusy || !fileInput.files?.length || !objectPromptInput?.value.trim();
  }

  function currentProgress() {
    return page.resolveProgress({
      localPhase: state.localPhase,
      job: state.job,
      result: state.result,
      viewerState: state.viewerState
    });
  }

  function updateProgressUI() {
    const progress = currentProgress();
    progressCard.dataset.tone = progress.tone || "neutral";
    progressKicker.textContent = progress.label;
    progressPercent.textContent = `${progress.percent}%`;
    progressBarFill.style.width = `${progress.percent}%`;
    progressLabel.textContent = progress.label;
    progressMessage.textContent = progress.description;
    activeJob.textContent = state.job ? `Active job: ${state.job.job_id}` : "No active job yet.";

    const currentIndex = stepIndex(progress.step);
    progressSteps.forEach((node) => {
      const index = stepIndex(node.dataset.stepId);
      let nextState = "upcoming";

      if (currentIndex >= 0 && index < currentIndex) {
        nextState = "complete";
      } else if (currentIndex >= 0 && index === currentIndex) {
        nextState = progress.tone === "failed" ? "failed" : "current";
      } else if (progress.step === "completed" && progress.percent === 100) {
        nextState = "complete";
      }

      node.dataset.state = nextState;
    });
  }

  function renderSegmentationCandidates() {
    if (!segmentCandidates || !state.segmentation.enabled) {
      return;
    }

    const candidates = state.segmentation.candidates || [];
    if (!candidates.length) {
      segmentCandidates.innerHTML = "";
      return;
    }

    segmentCandidates.innerHTML = candidates
      .map((candidate) => {
        const selected = candidate.candidate_id === state.segmentation.selectedCandidateId;
        const score = Number(candidate.score || 0).toFixed(3);
        const area = `${Math.round(Number(candidate.area_ratio || 0) * 100)}%`;
        const areaRatio = Number(candidate.area_ratio || 0);
        const borderTouch = Number(candidate.border_touch_count || 0);
        const previewUrl = candidate.overlay_url || candidate.segmented_url || candidate.mask_url;
        const sizeHint = areaRatio >= 0.12 ? "Large target" : areaRatio >= 0.04 ? "Medium target" : "Small target";
        return `
          <button
            type="button"
            class="segment-card${selected ? " is-selected" : ""}"
            data-segment-candidate-id="${candidate.candidate_id}"
            aria-pressed="${selected ? "true" : "false"}"
          >
            <img src="${previewUrl}" alt="Segmentation candidate ${candidate.candidate_id}" loading="lazy" />
            <span class="segment-meta">
              <strong>${candidate.candidate_id}</strong>
              <span>Score ${score} · Area ${area} · Border ${borderTouch}</span>
              <span class="segment-size-hint">${sizeHint}</span>
            </span>
          </button>
        `;
      })
      .join("");

    const optionButtons = Array.from(segmentCandidates.querySelectorAll("[data-segment-candidate-id]"));
    optionButtons.forEach((node) => {
      node.addEventListener("click", () => {
        state.segmentation.selectedCandidateId = node.dataset.segmentCandidateId;
        renderSegmentationCandidates();
        updateUI();
      });
    });
  }

  function updateSegmentationUI() {
    if (!segmentPicker || !state.segmentation.enabled) {
      return;
    }

    const hasCandidates = (state.segmentation.candidates || []).length > 0;
    const selecting = state.localPhase === "segment_select";
    const loading = state.localPhase === "segmenting" || state.segmentation.loading;
    segmentPicker.classList.toggle("is-hidden", !loading && !selecting && !hasCandidates);

    if (segmentCopy) {
      if (loading) {
        segmentCopy.textContent = "Detecting the prompted object with SAM3. This usually takes a few seconds.";
      } else if (state.segmentation.error) {
        segmentCopy.textContent = state.segmentation.error;
      } else {
        segmentCopy.textContent = "Select the object to model in 3D, then continue generation.";
      }
    }

    if (confirmSegmentButton) {
      const ready = Boolean(state.pendingUpload?.job_id && state.segmentation.selectedCandidateId);
      confirmSegmentButton.disabled = !ready || loading || state.job?.status === "running";
    }

    if (segmentSelectionCopy) {
      segmentSelectionCopy.textContent = state.segmentation.selectedCandidateId
        ? `Selected: ${state.segmentation.selectedCandidateId}`
        : "No object selected yet.";
    }

    renderSegmentationCandidates();
  }

  function updateStatusBanner() {
    let message = "";
    let tone = "neutral";

    if (state.job?.status === "failed") {
      message = decorateFailureMessage(state.job);
      tone = "failed";
    } else if (state.result?.mesh_url && state.viewerState.status === "failed") {
      message = "The pipeline completed successfully, but the browser viewer could not render the mesh. You can still download the file.";
      tone = "warning";
    }

    statusBanner.textContent = message;
    statusBanner.dataset.tone = tone;
    statusBanner.classList.toggle("is-hidden", !message);
  }

  function updateDownloadUI() {
    if (state.result?.mesh_url) {
      const meshFilename = state.result.mesh_url.split("?")[0].split("/").pop() || page.downloadFilename;
      downloadLink.href = state.result.mesh_url;
      downloadLink.download = meshFilename;
      downloadLink.textContent = `Download ${meshFilename}`;
      downloadLink.classList.remove("is-hidden");
      downloadCopy.textContent =
        state.viewerState.status === "failed"
          ? "The mesh is still available as a direct download."
          : "Download the canonical GLB or generate a DCC-ready package below.";
      renderExportPresets();
      return;
    }

    downloadLink.classList.add("is-hidden");
    downloadLink.textContent = page.downloadLabel;
    downloadCopy.textContent =
      state.job?.status === "failed"
        ? "No mesh is available for download because the pipeline did not finish successfully."
        : page.downloadIdleCopy;
    renderExportPresets();
  }

  function describeValue(value) {
    if (value === null || value === undefined || value === "") {
      return "not available";
    }
    if (Array.isArray(value)) {
      return value.length ? value.join(", ") : "none";
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    return String(value);
  }

  function renderDefinitionList(node, rows) {
    if (!node) {
      return;
    }
    node.innerHTML = rows
      .map(
        ([term, value]) => `
          <div class="inspector-row">
            <dt>${term}</dt>
            <dd>${describeValue(value)}</dd>
          </div>
        `
      )
      .join("");
  }

  function renderAssetInspector() {
    const material = state.result?.material || {};
    const assetMetadata = state.result?.asset_metadata || {};
    const hasMaterial = Object.keys(material).length > 0;
    const hasMetadata = Object.keys(assetMetadata).length > 0;

    if (!assetInspector) {
      return;
    }

    assetInspector.classList.toggle("is-hidden", !hasMaterial && !hasMetadata);
    renderDefinitionList(materialList, [
      ["Base Color", material.baseColorTexture || material.baseColorValue],
      ["Roughness", material.roughnessTexture || material.roughnessValue],
      ["Roughness Source", material.roughnessSource],
      ["Metallic", material.metallicTexture || material.metallicValue],
      ["Metallic Source", material.metallicSource],
      ["Normal", material.normalTexture || material.normalSource],
      ["Opacity", material.opacityTexture || material.opacityValue],
      ["Alpha Mode", material.alphaMode],
      ["Scale Policy", material.scaleNormalization],
      ["Pivot Policy", material.pivotPolicy],
      ["Ground Aligned", material.groundAligned]
    ]);

    renderDefinitionList(metadataList, [
      ["Asset Name", assetMetadata.asset_name],
      ["Category", assetMetadata.normalized_category_id || assetMetadata.category],
      ["Subcategory", assetMetadata.subcategory],
      ["Specific Type", assetMetadata.specific_type],
      ["Color Hints", assetMetadata.color_hints],
      ["Material Hints", assetMetadata.material_hints],
      ["Recommended Usage", assetMetadata.recommended_usage],
      ["DCC Tags", assetMetadata.dcc_tags],
      ["Source Prompt", assetMetadata.source_prompt]
    ]);
  }

  function renderExportPresets() {
    const existing = document.querySelector("#export-presets");
    if (!state.result?.mesh_url) {
      existing?.remove();
      return;
    }

    let panel = existing;
    if (!panel) {
      panel = document.createElement("section");
      panel.id = "export-presets";
      panel.className = "export-presets";
      downloadCopy.insertAdjacentElement("afterend", panel);
    }

    const items = state.exports || [];
    if (!items.length) {
      panel.innerHTML = `<p class="field-hint">Export presets will appear after the completed result is inspected.</p>`;
      return;
    }

    const errorCopy = state.exportError ? `<p class="export-error">${state.exportError}</p>` : "";
    panel.innerHTML = `
      <div class="export-grid">
        ${items
          .map((item) => {
            const busy = state.exportLoadingFormat === item.format;
            const disabled = !item.available || busy;
            const label = item.generated ? `Open ${item.label}` : busy ? "Generating..." : `Generate ${item.label}`;
            return `
              <button
                class="export-button"
                type="button"
                data-export-format="${item.format}"
                ${disabled ? "disabled" : ""}
              >
                <strong>${label}</strong>
                <span>${item.tool_hint}</span>
              </button>
            `;
          })
          .join("")}
      </div>
      ${errorCopy}
    `;

    Array.from(panel.querySelectorAll("[data-export-format]")).forEach((button) => {
      button.addEventListener("click", async () => {
        const format = button.dataset.exportFormat;
        const item = state.exports.find((candidate) => candidate.format === format);
        if (!format || !item?.available) {
          return;
        }
        if (item.generated && item.url) {
          window.open(item.url, "_blank", "noopener");
          return;
        }
        state.exportLoadingFormat = format;
        state.exportError = null;
        updateUI();
        try {
          const exported = await createJobExport(state.job.job_id, format);
          state.exports = state.exports.map((candidate) =>
            candidate.format === format ? { ...candidate, ...exported, available: true, generated: true } : candidate
          );
          if (exported.url) {
            window.open(exported.url, "_blank", "noopener");
          }
        } catch (error) {
          state.exportError = error.message;
        } finally {
          state.exportLoadingFormat = null;
          updateUI();
        }
      });
    });
  }

  function updateViewerShell() {
    const hasMesh = Boolean(state.result?.mesh_url);
    viewerPanel.classList.toggle("is-hidden", !hasMesh);
    viewerEmpty.classList.toggle("is-hidden", hasMesh);

    if (hasMesh) {
      renderAssetInspector();
      if (state.viewerState.status === "loaded") {
        viewerSummary.textContent = page.viewerLoadedSummary;
      } else if (state.viewerState.status === "failed") {
        viewerSummary.textContent = page.viewerFailedSummary;
      } else {
        viewerSummary.textContent = state.viewerState.message || page.viewerIdleSummary;
      }
      return;
    }

    renderAssetInspector();

    if (state.job?.status === "failed") {
      emptyBadge.textContent = "Generation Failed";
      emptyTitle.textContent = "The mesh could not be produced";
      emptyCopy.textContent = decorateFailureMessage(state.job);
      return;
    }

    if (state.localPhase === "uploading" || state.job?.status === "queued" || state.job?.status === "running") {
      const progress = currentProgress();
      emptyBadge.textContent = progress.label;
      emptyTitle.textContent = progress.label;
      emptyCopy.textContent = progress.description;
      return;
    }

    emptyBadge.textContent = page.idleEmptyBadge;
    emptyTitle.textContent = page.idleEmptyTitle;
    emptyCopy.textContent = page.idleEmptyCopy;
  }

  function updateUI() {
    selectedFileName.textContent =
      fileInput.files?.[0]?.name ||
      state.pendingUpload?.filename ||
      (state.job?.job_id ? `Loaded job: ${state.job.job_id}` : "No file selected yet");
    updateProgressUI();
    updateStatusBanner();
    updateDownloadUI();
    updateViewerShell();
    updateSegmentationUI();

    const busy =
      state.localPhase === "uploading" ||
      state.localPhase === "segmenting" ||
      state.localPhase === "segment_select" ||
      state.job?.status === "queued" ||
      state.job?.status === "running";
    setBusy(Boolean(busy));
  }

  async function renderCompletedResult(result) {
    state.result = result;
    state.localPhase = "rendering";
    try {
      const exportsPayload = await listJobExports(result.job_id);
      state.exports = exportsPayload.exports || [];
      state.exportError = null;
    } catch (error) {
      state.exports = [];
      state.exportError = error.message;
    }
    updateUI();

    if (!result.mesh_url) {
      state.viewerState = {
        status: "failed",
        message: "The pipeline completed, but there is no browser-renderable mesh file for this job."
      };
      updateUI();
      return;
    }

    try {
      await viewer.load(page.jobType, result.mesh_url);
    } catch {
      updateUI();
    }
  }

  async function handleJobSnapshot(job) {
    if (job.type !== page.jobType) {
      navigate(imagePage.route, {
        replace: true,
        query: { jobId: job.job_id }
      });
      return;
    }

    state.job = job;
    updateUI();

    if (job.status === "completed") {
      clearPoller();
      const result = await getJobResult(job.job_id);
      await renderCompletedResult(result);
      return;
    }

    if (job.status === "failed") {
      clearPoller();
      state.localPhase = "idle";
      updateUI();
    }
  }

  function startPolling(jobId) {
    clearPoller();
    poller = setInterval(async () => {
      try {
        const job = await getJob(jobId);
        await handleJobSnapshot(job);
      } catch (error) {
        clearPoller();
        state.job = {
          job_id: jobId,
          type: page.jobType,
          status: "failed",
          error: error.message
        };
        state.localPhase = "idle";
        updateUI();
      }
    }, 2000);
  }

  async function createAndStartJob(upload, sam2CandidateId = null, sourcePrompt = "") {
    const jobOptions = page.jobType === "image_to_3d"
      ? {
          requested_reconstruction_head: page.requestedReconstructionHead || "trellis",
          image_quality_mode: page.requestedImageQualityMode || "high_quality",
          source_prompt: sourcePrompt.trim(),
          ...(sam2CandidateId ? { sam2_candidate_id: sam2CandidateId } : {})
        }
      : {};
    const job = await createJob(upload.job_id, upload.type, jobOptions);
    state.job = job;
    state.localPhase = "idle";
    state.pendingUpload = null;
    state.exports = [];
    state.exportLoadingFormat = null;
    state.exportError = null;
    state.segmentation.candidates = [];
    state.segmentation.selectedCandidateId = null;
    state.segmentation.error = null;
    navigate(page.route, { replace: true, query: { jobId: job.job_id } });
    updateUI();
    startPolling(job.job_id);
  }

  async function restoreExistingJob(jobId) {
    state.localPhase = "restoring";
    state.pendingUpload = null;
    state.exports = [];
    state.exportLoadingFormat = null;
    state.exportError = null;
    state.segmentation.candidates = [];
    state.segmentation.selectedCandidateId = null;
    state.segmentation.error = null;
    updateUI();

    try {
      const job = await getJob(jobId);
      await handleJobSnapshot(job);

      if (job.status === "queued" || job.status === "running") {
        startPolling(jobId);
      } else {
        state.localPhase = "idle";
        updateUI();
      }
    } catch (error) {
      state.job = {
        job_id: jobId,
        type: page.jobType,
        status: "failed",
        error: error.message
      };
      state.localPhase = "idle";
      updateUI();
    }
  }

  viewerRoot.addEventListener("viewer-statechange", (event) => {
    state.viewerState = event.detail;
    updateUI();
  });

  fileInput.addEventListener("change", () => {
    updateUI();
  });

  objectPromptInput?.addEventListener("input", () => {
    updateUI();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files?.[0];
    const sourcePrompt = objectPromptInput?.value.trim() || "";
    if (!file || !sourcePrompt) {
      return;
    }

    clearPoller();
    state.localPhase = "uploading";
    state.job = null;
    state.result = null;
    state.exports = [];
    state.exportLoadingFormat = null;
    state.exportError = null;
    state.pendingUpload = null;
    state.segmentation.candidates = [];
    state.segmentation.selectedCandidateId = null;
    state.segmentation.error = null;
    state.viewerState = {
      status: "idle",
      message: page.viewerIdleSummary
    };
    updateUI();

    try {
      const upload = await uploadAsset(page.jobType, file);

      if (page.jobType === "image_to_3d") {
        state.localPhase = "segmenting";
        state.pendingUpload = upload;
        updateUI();
        const candidatesPayload = await createSegmentationTextPrompt(upload.job_id, sourcePrompt);
        const candidates = candidatesPayload?.candidates || [];
        if (candidates.length) {
          state.segmentation.candidates = candidates;
          state.segmentation.selectedCandidateId =
            candidatesPayload.selected_candidate_id || candidates[0]?.candidate_id || null;
          state.localPhase = "segment_select";
          updateUI();
          return;
        }
      }

      await createAndStartJob(upload, null, sourcePrompt);
    } catch (error) {
      state.job = {
        job_id: null,
        type: page.jobType,
        status: "failed",
        error: error.message
      };
      state.localPhase = "idle";
      state.pendingUpload = null;
      state.segmentation.error = error.message;
      updateUI();
    }
  });

  if (confirmSegmentButton) {
    confirmSegmentButton.addEventListener("click", async () => {
      if (!state.pendingUpload?.job_id || !state.segmentation.selectedCandidateId) {
        return;
      }
      state.localPhase = "uploading";
      state.segmentation.error = null;
      updateUI();
      try {
        await createAndStartJob(
          state.pendingUpload,
          state.segmentation.selectedCandidateId,
          objectPromptInput?.value.trim() || ""
        );
      } catch (error) {
        state.job = {
          job_id: state.pendingUpload?.job_id || null,
          type: page.jobType,
          status: "failed",
          error: error.message
        };
        state.localPhase = "segment_select";
        state.segmentation.error = error.message;
        updateUI();
      }
    });
  }

  updateUI();

  const existingJobId = readQueryParam("jobId");
  if (existingJobId) {
    restoreExistingJob(existingJobId);
  }

  return () => {
    clearPoller();
    viewer.dispose();
  };
}

initRouter(mountRoute);

document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-nav]");
  if (!link) {
    return;
  }

  const path = link.getAttribute("data-nav");
  if (!path || path === currentPath()) {
    return;
  }

  event.preventDefault();
  navigate(path);
});

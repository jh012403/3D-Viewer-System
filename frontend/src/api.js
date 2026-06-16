const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim() || "";

function buildUrl(path) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  if (!API_BASE_URL) {
    return path;
  }
  return new URL(path, API_BASE_URL).toString();
}

async function request(path, options = {}) {
  const response = await fetch(buildUrl(path), options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function uploadAsset(type, file) {
  const form = new FormData();
  form.append("type", type);
  form.append("file", file);
  return request("/api/upload", {
    method: "POST",
    body: form
  });
}

export async function createJob(jobId, type, options = {}) {
  return request("/api/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ job_id: jobId, type, options })
  });
}

export async function getJob(jobId) {
  return request(`/api/jobs/${jobId}`);
}

export async function getSegmentationCandidates(jobId) {
  const payload = await request(`/api/jobs/${jobId}/segmentation-candidates`);
  if (payload?.input_url) {
    payload.input_url = buildUrl(payload.input_url);
  }
  payload.candidates = (payload?.candidates || []).map((candidate) => ({
    ...candidate,
    segmented_url: candidate.segmented_url ? buildUrl(candidate.segmented_url) : "",
    mask_url: candidate.mask_url ? buildUrl(candidate.mask_url) : "",
    overlay_url: candidate.overlay_url ? buildUrl(candidate.overlay_url) : ""
  }));
  return payload;
}

export async function createSegmentationTextPrompt(jobId, prompt, options = {}) {
  const payload = await request(`/api/jobs/${jobId}/segmentation-text-prompt`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      prompt,
      confidence_threshold: options.confidenceThreshold ?? null,
      merge_mode: options.mergeMode || "best"
    })
  });
  if (payload?.input_url) {
    payload.input_url = buildUrl(payload.input_url);
  }
  payload.candidates = (payload?.candidates || []).map((candidate) => ({
    ...candidate,
    segmented_url: candidate.segmented_url ? buildUrl(candidate.segmented_url) : "",
    segmented_preview_url: candidate.segmented_preview_url ? buildUrl(candidate.segmented_preview_url) : "",
    mask_url: candidate.mask_url ? buildUrl(candidate.mask_url) : "",
    overlay_url: candidate.overlay_url ? buildUrl(candidate.overlay_url) : ""
  }));
  return payload;
}

export async function getJobResult(jobId) {
  const payload = await request(`/api/jobs/${jobId}/result`);
  if (payload?.mesh_url) payload.mesh_url = buildUrl(payload.mesh_url);
  if (payload?.thumbnail_url) payload.thumbnail_url = buildUrl(payload.thumbnail_url);
  if (payload?.material_url) payload.material_url = buildUrl(payload.material_url);
  if (payload?.asset_metadata_url) payload.asset_metadata_url = buildUrl(payload.asset_metadata_url);
  if (payload?.job?.result) {
    if (payload.job.result.mesh_url) payload.job.result.mesh_url = buildUrl(payload.job.result.mesh_url);
    if (payload.job.result.thumbnail_url) payload.job.result.thumbnail_url = buildUrl(payload.job.result.thumbnail_url);
    if (payload.job.result.metadata_url) payload.job.result.metadata_url = buildUrl(payload.job.result.metadata_url);
    if (payload.job.result.material_url) payload.job.result.material_url = buildUrl(payload.job.result.material_url);
    if (payload.job.result.asset_metadata_url) {
      payload.job.result.asset_metadata_url = buildUrl(payload.job.result.asset_metadata_url);
    }
  }
  return payload;
}

export async function listJobExports(jobId) {
  const payload = await request(`/api/jobs/${jobId}/exports`);
  payload.exports = (payload?.exports || []).map((item) => ({
    ...item,
    url: item.url ? buildUrl(item.url) : null
  }));
  return payload;
}

export async function createJobExport(jobId, format) {
  const payload = await request(`/api/jobs/${jobId}/exports/${format}`, {
    method: "POST"
  });
  if (payload?.url) payload.url = buildUrl(payload.url);
  return payload;
}

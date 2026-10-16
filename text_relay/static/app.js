import { initializeImageUpload } from "./image-upload.js";

const form = document.querySelector("#upload-form");
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const queue = document.querySelector("#queue");
const submitted = document.querySelector("#submitted");
const profileSelect = document.querySelector("#ocr-profile");
const RESULTS_REQUEST_TIMEOUT_MS = 40_000;
let lastResults = "";
let cursor = null;
let activeProfile = null;
const profileLabels = new Map();
const { imageInput, submitButton, updateSelectedFile } = initializeImageUpload(setStatus);

function setStatus(message, state = "") {
  status.textContent = message;
  status.className = state;
}
function displayTime(value) { return new Date(value).toLocaleString(); }
function applyProfiles(payload) {
  if (payload.profiles) {
    profileLabels.clear();
    profileSelect.replaceChildren(...payload.profiles.map((profile) => {
      profileLabels.set(profile.id, profile.label);
      return Object.assign(document.createElement("option"), { value: profile.id, textContent: profile.label });
    }));
    profileSelect.disabled = false;
  }
  if (payload.active_profile) {
    activeProfile = payload.active_profile;
    profileSelect.value = activeProfile;
  }
}
async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
    window.setTimeout(() => { button.textContent = "Copy"; }, 1200);
  } catch (_) {
    setStatus("Copy is unavailable here; select the text and copy it manually.", "error");
  }
}
function resultCard(result) {
  const card = document.createElement("article");
  card.className = "result";
  const header = document.createElement("div");
  header.className = "result-header";
  const timestamp = document.createElement("time");
  timestamp.dateTime = result.created_at;
  timestamp.textContent = displayTime(result.created_at);
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "copy-button";
  copy.textContent = "Copy";
  copy.addEventListener("click", () => copyText(result.text, copy));
  header.append(timestamp, copy);
  const text = document.createElement("pre");
  text.textContent = result.text;
  card.append(header, text);
  return card;
}
function renderResults(items) {
  const serialized = JSON.stringify(items);
  if (serialized === lastResults) return;
  lastResults = serialized;
  results.replaceChildren(...(items.length ? items.map(resultCard) : [Object.assign(document.createElement("div"), { className: "empty-state", textContent: "Your extracted text will appear here." })]));
}
function jobCard(job) {
  const card = document.createElement("article");
  card.className = "job";
  const details = document.createElement("span");
  details.textContent = `Submitted ${displayTime(job.created_at)} · ${profileLabels.get(job.profile_id) || job.profile_id}`;
  const label = document.createElement("span");
  label.className = `job-status ${job.status}`;
  label.textContent = job.status;
  const state = document.createElement("span");
  state.style.display = "inline-flex";
  state.style.alignItems = "center";
  state.style.gap = ".6rem";
  state.append(label);
  if (job.status === "failed") {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "retry-button";
    retry.textContent = "Retry";
    retry.setAttribute("aria-label", `Retry extraction submitted ${displayTime(job.created_at)}`);
    retry.addEventListener("click", () => retryJob(job.id, retry));
    state.append(retry);
  }
  card.append(details, state);
  return card;
}
async function retryJob(jobId, button) {
  button.disabled = true;
  button.textContent = "Retrying…";
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Could not retry this extraction.");
    setStatus("Extraction queued again.", "success");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Retry";
    setStatus(error.message || "Could not retry this extraction.", "error");
  }
}
function renderQueue(items) {
  queue.replaceChildren(...(items.length ? items.map(jobCard) : [Object.assign(document.createElement("div"), { className: "empty-state", textContent: "No images have been submitted yet." })]));
}
profileSelect.addEventListener("change", async () => {
  const previous = activeProfile;
  profileSelect.disabled = true;
  try {
    const response = await fetch("/api/ocr-profiles/active", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_id: profileSelect.value }) });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Could not change the OCR profile.");
    applyProfiles(body);
    setStatus("OCR profile changed for everyone on this server.", "success");
  } catch (error) {
    profileSelect.value = previous;
    setStatus(error.message || "Could not change the OCR profile.", "error");
  } finally { profileSelect.disabled = false; }
});
async function loadProfiles() {
  try {
    const response = await fetch("/api/ocr-profiles");
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Could not load OCR profiles.");
    applyProfiles(body);
  } catch (error) { setStatus(error.message || "Could not load OCR profiles.", "error"); }
}
function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
async function fetchResults(url) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), RESULTS_REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
  }
}
function showServerStopped() {
  imageInput.disabled = true;
  submitButton.disabled = true;
  setStatus("The server is shutting down. Reload this page after it restarts.", "error");
}
async function pollResults() {
  while (true) {
    try {
      const url = new URL("/api/results", window.location.origin);
      url.searchParams.set("wait", "true");
      if (cursor) url.searchParams.set("after", cursor);
      const response = await fetchResults(url);
      if (!response.ok) throw new Error();
      const payload = await response.json();
      if (payload.server_status === "stopping") {
        showServerStopped();
        return;
      }
      const items = payload.results;
      applyProfiles(payload);
      cursor = payload.cursor;
      renderResults(items);
      renderQueue(payload.jobs);
    } catch (_) {
      setStatus("The server is not responding. Check that it is running; retrying soon.", "error");
      await wait(1000);
    }
  }
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!imageInput.files.length) return;
  submitButton.disabled = true;
  setStatus("Adding image to the extraction queue…");
  try {
    const response = await fetch("/api/ocr", { method: "POST", body: new FormData(form) });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Could not process the image.");
    const heading = document.createElement("h2");
    heading.textContent = "Latest submission";
    submitted.replaceChildren(heading, jobCard(body));
    submitted.hidden = false;
    setStatus("Image queued for text extraction.", "success");
  } catch (error) {
    setStatus(error.message || "Could not process the image.", "error");
  } finally {
    submitButton.disabled = false;
    updateSelectedFile();
  }
});
loadProfiles();
pollResults();

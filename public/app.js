'use strict';

/* Snap2Skill studio — single-screen client.
   The browser owns all session state; every backend call is one stateless
   JSON request (Vercel Functions). State machine: idle → uploading →
   compiling → success. */

const state = {
  bootstrap: null,
  samples: {},
  images: [],        // [{name, mime_type, data_base64, previewUrl, size}]
  extraction: null,
  built: null,       // {folder, skill_md, validation, zip_base64, ...}
  phase: 'idle',
  chatBusy: false,
};

const $ = (id) => document.getElementById(id);

let toastTimer = null;
function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text }; }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function downloadBytes(bytes, filename, type) {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function downloadText(text, filename) {
  downloadBytes(new TextEncoder().encode(text), filename, 'text/markdown;charset=utf-8');
}

/* ------------------------------------------------------------------ state machine */

const PHASE_ORDER = ['idle', 'uploading', 'compiling', 'success'];
function setPhase(phase, statusText, isError = false) {
  state.phase = phase;
  const status = $('compileStatus');
  status.textContent = statusText;
  status.classList.toggle('error', isError);
  $('compileBtn').disabled = phase === 'uploading' || phase === 'compiling';
  $('compileBtn').classList.toggle('busy', phase === 'compiling');
  $('compileBtn').textContent = phase === 'compiling' ? 'Compiling…' : 'Compile to Skill';
  $('sampleBtn').disabled = phase === 'uploading' || phase === 'compiling';
  const activeIndex = PHASE_ORDER.indexOf(phase);
  document.querySelectorAll('#stateSteps li').forEach((li) => {
    const idx = PHASE_ORDER.indexOf(li.dataset.state);
    li.classList.toggle('active', li.dataset.state === phase);
    li.classList.toggle('done', idx < activeIndex);
  });
}

/* ------------------------------------------------------------------ tabs */

function activateTab(panelId) {
  document.querySelectorAll('[data-tab-target]').forEach((tab) => {
    const active = tab.dataset.tabTarget === panelId;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
  });
  document.querySelectorAll('.tab-panel').forEach((panel) => {
    panel.classList.toggle('active', panel.id === panelId);
  });
}
document.querySelectorAll('[data-tab-target]').forEach((tab) => {
  tab.addEventListener('click', () => activateTab(tab.dataset.tabTarget));
});

/* ------------------------------------------------------------------ bootstrap */

async function loadBootstrap() {
  try {
    const data = await api('/api/bootstrap');
    state.bootstrap = data;
    state.samples = data.samples || {};
    const badge = $('gemmaBadge');
    if (data.gemma.mode === 'live') {
      badge.innerHTML = '<span class="badge-dot"></span>⚡ Gemma 4 Active';
    } else {
      badge.innerHTML = '<span class="badge-dot"></span>⚡ Gemma 4 · Demo Mode';
    }
    const select = $('sampleSelect');
    select.innerHTML = '';
    Object.keys(state.samples).forEach((name) => {
      const option = document.createElement('option');
      option.value = name; option.textContent = name;
      select.appendChild(option);
    });
  } catch (error) {
    console.error(error);
    $('gemmaBadge').innerHTML = '<span class="badge-dot"></span>API unavailable';
    setPhase('idle', 'The API is unreachable right now. Check the Vercel deployment.', true);
  }
}

/* ------------------------------------------------------------------ images */

async function prepareImage(file) {
  const bitmap = await createImageBitmap(file);
  const maxDimension = 1600;
  const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  canvas.getContext('2d').drawImage(bitmap, 0, 0, width, height);
  bitmap.close?.();

  const keepPng = file.type === 'image/png' && scale === 1 && file.size <= 1_100_000;
  let blob = await new Promise((resolve) => canvas.toBlob(resolve, keepPng ? 'image/png' : 'image/jpeg', 0.88));
  if (!keepPng && blob && blob.size > 1_250_000) {
    blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.72));
  }
  if (!blob) throw new Error(`Could not process ${file.name}.`);
  return {
    name: file.name.replace(/\.[^.]+$/, '') + (blob.type === 'image/png' ? '.png' : '.jpg'),
    mime_type: blob.type,
    data_base64: await blobToBase64(blob),
    previewUrl: URL.createObjectURL(blob),
    size: blob.size,
  };
}

function renderImages() {
  const grid = $('imagePreviewGrid');
  grid.innerHTML = '';
  state.images.forEach((image, index) => {
    const cell = document.createElement('div');
    cell.className = 'thumb';
    cell.innerHTML = `<img alt="Snap ${index + 1}" src="${image.previewUrl}"><button type="button" aria-label="Remove snap ${index + 1}">×</button>`;
    cell.querySelector('button').addEventListener('click', () => {
      URL.revokeObjectURL(image.previewUrl);
      state.images.splice(index, 1);
      renderImages();
    });
    grid.appendChild(cell);
  });
  const total = state.images.reduce((sum, image) => sum + image.size, 0);
  $('imageMeta').textContent = state.images.length
    ? `${state.images.length} snap${state.images.length === 1 ? '' : 's'} ready · ${formatBytes(total)} after optimization.`
    : 'No snaps yet — or load the sample sketch below.';
  if (state.phase === 'success') setPhase('idle', 'Inputs changed — compile again to rebuild the skill.');
}

async function addImages(fileList) {
  const files = [...(fileList || [])].filter((file) => file.type.startsWith('image/'));
  if (!files.length) return;
  if (state.images.length + files.length > 5) {
    toast('Snap2Skill takes at most 5 snaps at once.');
    files.splice(0, Math.max(0, 5 - state.images.length));
  }
  setPhase('uploading', `Optimizing ${files.length} snap${files.length === 1 ? '' : 's'} in your browser…`);
  try {
    for (const file of files) state.images.push(await prepareImage(file));
    renderImages();
    setPhase('idle', 'Snaps ready. Hit Compile to Skill.');
  } catch (error) {
    console.error(error);
    setPhase('idle', error.message, true);
  }
}

const dropZone = $('imageDropZone');
dropZone.addEventListener('click', () => $('imageInput').click());
dropZone.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('imageInput').click(); }
});
$('imageInput').addEventListener('change', (event) => { addImages(event.target.files); event.target.value = ''; });
['dragenter', 'dragover'].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault(); dropZone.classList.add('dragging');
}));
['dragleave', 'drop'].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault(); dropZone.classList.remove('dragging');
}));
dropZone.addEventListener('drop', (event) => addImages(event.dataTransfer.files));

/* ------------------------------------------------------------------ compile */

async function runCompile(sampleName = '') {
  const payload = { images: state.images.map(({ name, mime_type, data_base64 }) => ({ name, mime_type, data_base64 })) };
  const text = $('sourceText').value.trim();
  const notes = $('extraNotes').value.trim();
  if (text) payload.text = text;
  if (notes) payload.notes = notes;
  if (sampleName) payload.sample_name = sampleName;

  if (!sampleName && !payload.images.length && !text && !notes) {
    setPhase('idle', 'Add a snap, paste steps, or load the sample sketch first.', true);
    toast('Nothing to compile yet.');
    return;
  }

  setPhase('compiling', sampleName
    ? 'Compiling the sample sketch — Gemma structure → deterministic builder → 13-point validator…'
    : 'Compiling — Gemma is reading the snap, then deterministic code builds and validates the skill…');
  try {
    const extracted = await api('/api/extract', { method: 'POST', body: JSON.stringify(payload) });
    state.extraction = extracted.extraction;
    const built = await api('/api/build', {
      method: 'POST',
      body: JSON.stringify({ extraction: state.extraction }),
    });
    state.built = built;
    renderStudio();
    const v = built.validation;
    setPhase('success', `Compiled “${state.extraction.title}” — validator ${v.score}/${v.total} ${v.passed ? 'passed' : 'needs review'}. Test it in the Live Sandbox.`);
    toast('Skill compiled and validated.');
    activateTab('flowPanel');
  } catch (error) {
    console.error(error);
    setPhase('idle', error.message, true);
  }
}

$('compileBtn').addEventListener('click', () => runCompile());
$('sampleBtn').addEventListener('click', () => {
  const name = $('sampleSelect').value;
  if (!name) { toast('No sample available.'); return; }
  runCompile(name);
});

/* ------------------------------------------------------------------ studio rendering */

function chip(text, accent = false) {
  return `<span class="chip${accent ? ' accent' : ''}">${escapeHtml(text)}</span>`;
}

function listHtml(items, fallback) {
  const list = (items || []).filter(Boolean);
  return list.length ? list.map((item) => `<li>${escapeHtml(item)}</li>`).join('') : `<li>${escapeHtml(fallback)}</li>`;
}

function renderStudio() {
  const x = state.extraction;
  const built = state.built;
  if (!x || !built) return;

  /* Flowchart tab */
  $('flowEmpty').classList.add('hidden');
  $('flowContent').classList.remove('hidden');
  $('flowTitle').textContent = x.title || 'Untitled skill';
  $('flowEvidence').textContent = x.evidence || '';
  $('flowChips').innerHTML = [
    chip(`folder: ${built.folder}`, true),
    chip(`source: ${x._mode || 'gemma'}`),
    chip(`model: ${x._model || 'gemma'}`),
    chip(`validator: ${built.validation.score}/${built.validation.total}`, built.validation.passed),
  ].join('');

  const unclear = x.unclear_items || [];
  $('unclearBox').classList.toggle('hidden', !unclear.length);
  $('unclearList').innerHTML = unclear.map((item) => `<li>${escapeHtml(item)}</li>`).join('');

  const nodes = [];
  const trigger = (x.when_to_use || [])[0] || 'When this task comes up';
  nodes.push(`<div class="flow-node start"><div class="node-text">▶ ${escapeHtml(x.title || 'Skill')}<small>${escapeHtml(trigger)}</small></div></div>`);
  (x.steps || []).forEach((step, i) => {
    nodes.push('<div class="flow-arrow" aria-hidden="true">↓</div>');
    nodes.push(`<div class="flow-node" style="animation-delay:${Math.min(i * 40, 400)}ms"><span class="node-num">${i + 1}</span><div class="node-text">${escapeHtml(step)}</div></div>`);
  });
  nodes.push('<div class="flow-arrow" aria-hidden="true">↓</div>');
  nodes.push(`<div class="flow-node end"><div class="node-text">✓ Validated SKILL.md<small>${escapeHtml(built.folder)}/SKILL.md · ${built.validation.score}/${built.validation.total} checks passed</small></div></div>`);
  $('flowNodes').innerHTML = nodes.join('');

  $('flowPrereq').innerHTML = listHtml(x.prerequisites, 'None stated in the source.');
  $('flowInputs').innerHTML = listHtml(x.inputs, 'None stated in the source.');
  $('flowConstraints').innerHTML = listHtml(x.constraints, 'None stated in the source.');
  $('flowTools').innerHTML = listHtml(x.tools, 'None visible in the source.');

  /* Spec tab */
  $('skillPreview').textContent = built.skill_md;
  const v = built.validation;
  const specChip = $('specValidation');
  specChip.textContent = v.passed ? `✓ Valid Agent Skill — ${v.score}/${v.total} checks` : `Validator: ${v.score}/${v.total} checks`;
  specChip.classList.toggle('accent', v.passed);
  $('validationChecks').innerHTML = `<table class="checks-table"><tbody>${v.checks.map((check) => `
    <tr><td class="${check.passed ? 'check-pass' : 'check-fail'}">${check.passed ? '✓' : '✗'}</td>
    <td>${escapeHtml(check.name)}</td><td class="detail">${escapeHtml(check.detail || '')}</td></tr>`).join('')}</tbody></table>`;
  $('copyMdBtn').disabled = false;
  $('downloadMdBtn').disabled = false;
  $('downloadZipBtn').disabled = !built.zip_included;

  /* Sandbox tab */
  const quick = $('quickRow');
  quick.innerHTML = '';
  const example = (x.examples || [])[0];
  const prompts = [example && example.input, 'Walk me through this step by step', 'What do you need from me before starting?'].filter(Boolean);
  [...new Set(prompts)].forEach((prompt) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'quick-chip';
    button.textContent = prompt;
    button.addEventListener('click', () => { $('chatInput').value = prompt; $('chatForm').requestSubmit(); });
    quick.appendChild(button);
  });
}

$('copyMdBtn').addEventListener('click', async () => {
  if (!state.built) return;
  await navigator.clipboard.writeText(state.built.skill_md);
  toast('SKILL.md copied to clipboard.');
});
$('downloadMdBtn').addEventListener('click', () => {
  if (state.built) downloadText(state.built.skill_md, 'SKILL.md');
});
$('downloadZipBtn').addEventListener('click', () => {
  if (!state.built || !state.built.zip_base64) return;
  downloadBytes(base64ToBytes(state.built.zip_base64), `${state.built.folder}.zip`, 'application/zip');
});

/* ------------------------------------------------------------------ sandbox */

function appendMessage(role, text) {
  const log = $('chatLog');
  const msg = document.createElement('div');
  msg.className = `chat-msg ${role}`;
  msg.innerHTML = `<span class="chat-role">${role === 'user' ? 'You' : 'Skill agent'}</span><p>${escapeHtml(text)}</p>`;
  log.appendChild(msg);
  log.scrollTop = log.scrollHeight;
  return msg;
}

$('chatForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = $('chatInput').value.trim();
  if (!question || state.chatBusy) return;
  if (!state.extraction || !state.built) {
    appendMessage('agent', 'Compile a skill first — then I will answer strictly by following it.');
    return;
  }
  appendMessage('user', question);
  $('chatInput').value = '';
  state.chatBusy = true;
  $('chatSendBtn').disabled = true;
  const typing = appendMessage('agent', 'Following the skill…');
  $('chatStatus').textContent = 'Sandbox: the agent is working through the compiled SKILL.md…';
  try {
    const data = await api('/api/sandbox', {
      method: 'POST',
      body: JSON.stringify({ extraction: state.extraction, skill_md: state.built.skill_md, question }),
    });
    typing.querySelector('p').textContent = data.answer;
    $('chatStatus').textContent = data.mode === 'gemma'
      ? `Sandbox answered by Gemma (${data.model}) acting as the skill.`
      : 'Sandbox answered by the deterministic walkthrough (demo mode — add GOOGLE_API_KEY for live Gemma answers).';
  } catch (error) {
    console.error(error);
    typing.querySelector('p').textContent = `Sandbox error: ${error.message}`;
    $('chatStatus').textContent = 'Sandbox request failed.';
  } finally {
    state.chatBusy = false;
    $('chatSendBtn').disabled = false;
    $('chatLog').scrollTop = $('chatLog').scrollHeight;
  }
});

/* ------------------------------------------------------------------ init */

renderImages();
loadBootstrap();

'use strict';

/* Snap2Skill browser application.
   The browser owns all editable session state. Every backend operation is a
   complete stateless HTTP request, which is the correct shape for Vercel. */

const $ = (id) => document.getElementById(id);

const state = {
  bootstrap: null,
  samples: {},
  images: [],
  voiceNote: null,
  extraction: null,
  transcript: '',
  built: null,
  narrationAudio: '',
  narrationScript: '',
  walkIndex: 0,
  repaired: '',
  recorder: null,
  recorderStream: null,
  recorderChunks: [],
  recording: false,
  buildTimer: null,
  buildSequence: 0,
};

const languageCodes = {
  English: 'en-US', Urdu: 'ur-PK', Hindi: 'hi-IN', Arabic: 'ar-SA',
  Spanish: 'es-ES', French: 'fr-FR', German: 'de-DE',
};

function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.classList.add('show');
  window.clearTimeout(toast._timer);
  toast._timer = window.setTimeout(() => el.classList.remove('show'), 3400);
}

function setOperation(el, message, kind = '') {
  el.textContent = message || '';
  el.classList.toggle('is-error', kind === 'error');
  el.classList.toggle('is-success', kind === 'success');
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  let data = null;
  try { data = await response.json(); } catch (_) { /* handled below */ }
  if (!response.ok) {
    throw new Error((data && data.error) || `Request failed with HTTP ${response.status}`);
  }
  if (!data) throw new Error('The service returned an empty response.');
  return data;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read that file in the browser.'));
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.readAsDataURL(blob);
  });
}

function base64ToBytes(base64) {
  const binary = atob(base64 || '');
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function downloadBytes(bytes, filename, type) {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function downloadText(text, filename, type = 'text/markdown') {
  downloadBytes(new TextEncoder().encode(text), filename, type);
}

function slugify(value) {
  const slug = String(value || 'my-skill').toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  return slug || 'my-skill';
}

function linesToArray(value) {
  return String(value || '').split('\n').map((line) => line.trim().replace(/^[-•\d.)\s]+/, '').trim()).filter(Boolean);
}

function arrayToLines(value) {
  return Array.isArray(value) ? value.join('\n') : String(value || '');
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function activateTab(panelId) {
  document.querySelectorAll('[data-tab-target]').forEach((button) => {
    const active = button.dataset.tabTarget === panelId;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  document.querySelectorAll('.tab-panel').forEach((panel) => {
    panel.classList.toggle('is-active', panel.id === panelId);
  });
  if (panelId === 'walkthroughPanel') updateWalkthrough();
}

document.querySelectorAll('[data-tab-target]').forEach((button) => {
  button.addEventListener('click', () => activateTab(button.dataset.tabTarget));
});

/* ------------------------------------------------------------------ bootstrap */

async function loadBootstrap() {
  try {
    const data = await api('/api/bootstrap');
    state.bootstrap = data;
    state.samples = data.samples || {};

    const sampleSelect = $('sampleSelect');
    Object.keys(state.samples).forEach((name) => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      sampleSelect.appendChild(option);
    });

    $('apiStatus').textContent = 'API ready · Vercel architecture';
    $('apiStatus').classList.add('is-ready');

    const gemmaReady = Boolean(data.gemma && data.gemma.configured);
    $('gemmaDot').className = `dot ${gemmaReady ? 'dot-green' : 'dot-amber'}`;
    $('gemmaStatus').textContent = gemmaReady
      ? `${data.gemma.model} configured`
      : 'Demo mode — add GOOGLE_API_KEY in Vercel to enable live vision';

    const voiceReady = Boolean(data.elevenlabs && data.elevenlabs.configured);
    $('voiceDot').className = `dot ${voiceReady ? 'dot-green' : 'dot-muted'}`;
    $('voiceStatus').textContent = voiceReady
      ? 'Scribe, narration and cloning configured'
      : 'Optional — add ELEVENLABS_API_KEY in Vercel';
  } catch (error) {
    $('apiStatus').textContent = 'API unavailable';
    $('apiStatus').classList.add('is-error');
    $('gemmaStatus').textContent = 'The API could not be reached from this page.';
    $('voiceStatus').textContent = 'The API could not be reached from this page.';
    console.error(error);
  }
}

/* ------------------------------------------------------------------ images */

function canvasBlob(canvas, type, quality) {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}

async function prepareImage(file) {
  const bitmap = await createImageBitmap(file);
  const maxDimension = 1600;
  const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { alpha: false });
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, width, height);
  context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();

  const preservePng = file.type === 'image/png' && file.size <= 1_100_000 && scale === 1;
  let blob = await canvasBlob(canvas, preservePng ? 'image/png' : 'image/jpeg', 0.88);
  if (!blob) blob = file;
  if (blob.size > 1_250_000 && blob.type !== 'image/jpeg') {
    blob = await canvasBlob(canvas, 'image/jpeg', 0.82) || blob;
  }
  if (blob.size > 1_250_000) {
    blob = await canvasBlob(canvas, 'image/jpeg', 0.72) || blob;
  }
  return {
    name: file.name,
    mime_type: blob.type || file.type || 'image/jpeg',
    data_base64: await blobToBase64(blob),
    previewUrl: URL.createObjectURL(blob),
    size: blob.size,
    originalSize: file.size,
    width,
    height,
  };
}

function renderImages() {
  const grid = $('imagePreviewGrid');
  grid.innerHTML = state.images.map((image, index) => `
    <figure class="image-thumb">
      <img src="${image.previewUrl}" alt="Snap ${index + 1}: ${escapeHtml(image.name)}">
      <button type="button" data-remove-image="${index}" aria-label="Remove snap ${index + 1}">×</button>
      <small>${index + 1}. ${escapeHtml(image.name)}</small>
    </figure>`).join('');
  grid.querySelectorAll('[data-remove-image]').forEach((button) => {
    button.addEventListener('click', () => {
      const index = Number(button.dataset.removeImage);
      const [removed] = state.images.splice(index, 1);
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      renderImages();
    });
  });
  const total = state.images.reduce((sum, image) => sum + image.size, 0);
  $('imageMeta').textContent = state.images.length
    ? `${state.images.length} snap${state.images.length === 1 ? '' : 's'} ready · ${formatBytes(total)} after browser optimisation.`
    : 'No snaps selected.';
}

async function addImages(fileList) {
  const files = [...(fileList || [])].filter((file) => file.type.startsWith('image/'));
  if (!files.length) return;
  const remaining = 5 - state.images.length;
  if (remaining <= 0) {
    toast('Snap2Skill merges at most five snaps.');
    return;
  }
  $('imageMeta').textContent = 'Optimising snaps in your browser…';
  for (const file of files.slice(0, remaining)) {
    try {
      state.images.push(await prepareImage(file));
    } catch (error) {
      console.error(error);
      toast(`Could not read ${file.name}. Try a JPG or PNG screenshot.`);
    }
  }
  renderImages();
}

$('imageInput').addEventListener('change', async (event) => {
  await addImages(event.target.files);
  event.target.value = '';
});

const dropZone = $('imageDropZone');
['dragenter', 'dragover'].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.add('is-dragging');
}));
['dragleave', 'drop'].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.remove('is-dragging');
}));
dropZone.addEventListener('drop', (event) => addImages(event.dataTransfer.files));

/* ------------------------------------------------------------------ voice note */

async function filePayload(blob, fallbackName) {
  return {
    name: fallbackName || 'recording.webm',
    mime_type: blob.type || 'application/octet-stream',
    data_base64: await blobToBase64(blob),
  };
}

function setVoiceNote(blob, name) {
  if (blob.size > 3_500_000) {
    setOperation($('extractStatus'), 'That voice note is over 3.5 MB. Record a shorter note or choose a smaller file for Vercel.', 'error');
    return;
  }
  if (state.voiceNote && state.voiceNote.previewUrl) URL.revokeObjectURL(state.voiceNote.previewUrl);
  const previewUrl = URL.createObjectURL(blob);
  state.voiceNote = { blob, name: name || 'voice-note', previewUrl };
  $('voiceNoteMeta').textContent = `${name || 'Voice note'} · ${formatBytes(blob.size)}`;
  const preview = $('voiceNotePreview');
  preview.src = previewUrl;
  preview.classList.remove('hidden');
}

$('voiceNoteInput').addEventListener('change', (event) => {
  const file = event.target.files[0];
  if (file) setVoiceNote(file, file.name);
  event.target.value = '';
});

$('clearVoiceNoteBtn').addEventListener('click', () => {
  if (state.voiceNote && state.voiceNote.previewUrl) URL.revokeObjectURL(state.voiceNote.previewUrl);
  state.voiceNote = null;
  $('voiceNoteMeta').textContent = 'No voice note selected.';
  $('voiceNotePreview').removeAttribute('src');
  $('voiceNotePreview').classList.add('hidden');
});

$('recordBtn').addEventListener('click', async () => {
  if (state.recording && state.recorder) {
    state.recorder.stop();
    return;
  }
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    setOperation($('extractStatus'), 'Browser recording is not available here. Upload an audio file instead.', 'error');
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.recorderStream = stream;
    state.recorderChunks = [];
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
      .find((candidate) => MediaRecorder.isTypeSupported(candidate)) || '';
    state.recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    state.recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size) state.recorderChunks.push(event.data);
    });
    state.recorder.addEventListener('stop', () => {
      const type = state.recorder.mimeType || 'audio/webm';
      const blob = new Blob(state.recorderChunks, { type });
      setVoiceNote(blob, `expert-recording.${type.includes('mp4') ? 'm4a' : 'webm'}`);
      state.recorderStream.getTracks().forEach((track) => track.stop());
      state.recording = false;
      $('recordBtn').textContent = 'Record in browser';
      $('recordBtn').classList.remove('is-recording');
    });
    state.recorder.start();
    state.recording = true;
    $('recordBtn').textContent = 'Stop recording';
    $('recordBtn').classList.add('is-recording');
    setOperation($('extractStatus'), 'Recording… speak clearly, then press Stop recording.');
  } catch (error) {
    console.error(error);
    setOperation($('extractStatus'), 'Microphone access was not granted. Upload a voice note instead.', 'error');
  }
});

/* ------------------------------------------------------------------ extraction + editor */

function setExtraction(extraction, transcript = '') {
  state.extraction = structuredClone(extraction || {});
  state.transcript = transcript || '';
  state.narrationAudio = '';
  state.narrationScript = '';
  state.walkIndex = 0;
  $('narrationAudio').removeAttribute('src');
  $('narrationAudio').classList.add('hidden');
  $('narrationScript').textContent = 'No narration generated yet.';

  $('skillTitle').value = state.extraction.title || '';
  $('skillSlug').value = state.extraction.skill_name || slugify(state.extraction.title);
  $('skillDescription').value = state.extraction.description || '';
  $('whenToUse').value = arrayToLines(state.extraction.when_to_use);
  $('prerequisites').value = arrayToLines(state.extraction.prerequisites);
  $('skillInputs').value = arrayToLines(state.extraction.inputs);
  $('skillTools').value = arrayToLines(state.extraction.tools);
  $('skillSteps').value = arrayToLines(state.extraction.steps);
  $('skillConstraints').value = arrayToLines(state.extraction.constraints);
  $('skillEvidence').value = state.extraction.evidence || '';

  const mode = state.extraction._mode || 'draft';
  const model = state.extraction._model || 'Snap2Skill';
  $('extractionMeta').textContent = `Extraction mode: ${mode} · Model/source: ${model}`;

  const unclear = state.extraction.unclear_items || [];
  $('unclearAlerts').innerHTML = unclear.map((item) => `
    <div class="alert-item"><strong>Unclear in the source — not invented:</strong> ${escapeHtml(item)}</div>`).join('');

  $('emptyOutput').classList.add('hidden');
  $('editorWrap').classList.remove('hidden');
  updateWalkthrough();
  performBuild();
}

function readEditor() {
  if (!state.extraction) return null;
  const extraction = structuredClone(state.extraction);
  extraction.title = $('skillTitle').value.trim();
  extraction.skill_name = slugify($('skillSlug').value || extraction.title);
  $('skillSlug').value = extraction.skill_name;
  extraction.description = $('skillDescription').value.trim();
  extraction.when_to_use = linesToArray($('whenToUse').value);
  extraction.prerequisites = linesToArray($('prerequisites').value);
  extraction.inputs = linesToArray($('skillInputs').value);
  extraction.tools = linesToArray($('skillTools').value);
  extraction.steps = linesToArray($('skillSteps').value);
  extraction.constraints = linesToArray($('skillConstraints').value);
  extraction.evidence = $('skillEvidence').value.trim();
  state.extraction = extraction;
  return extraction;
}

['skillTitle', 'skillDescription', 'whenToUse', 'prerequisites', 'skillInputs',
 'skillTools', 'skillSteps', 'skillConstraints', 'skillEvidence'].forEach((id) => {
  $(id).addEventListener('input', () => {
    if (id === 'skillTitle') $('skillSlug').value = slugify($('skillTitle').value);
    readEditor();
    scheduleBuild();
    updateWalkthrough(false);
  });
});

async function runExtraction(sampleName = '') {
  const button = $('extractBtn');
  const text = $('sourceText').value.trim();
  const notes = $('extraNotes').value.trim();
  const selectedSample = sampleName || $('sampleSelect').value;
  const hasCustom = Boolean(state.images.length || state.voiceNote || text || notes);

  button.disabled = true;
  setOperation($('extractStatus'), selectedSample && !hasCustom
    ? 'Loading the labelled sample through the API…'
    : 'Reading the source and preparing a structured draft…');
  try {
    const payload = {
      text,
      notes,
      sample_name: hasCustom ? '' : selectedSample,
      images: state.images.map(({ name, mime_type, data_base64 }) => ({ name, mime_type, data_base64 })),
      audio: state.voiceNote ? await filePayload(state.voiceNote.blob, state.voiceNote.name) : null,
    };
    const data = await api('/api/extract', { method: 'POST', body: JSON.stringify(payload) });
    setExtraction(data.extraction, data.transcript || '');
    const transcriptNote = data.transcript
      ? ` Voice transcript received (${data.transcript_language || 'language auto-detected'}).`
      : (state.voiceNote && data.transcript_mode === 'voice-off'
        ? ' Voice note was noted, but ElevenLabs is not configured for transcription.'
        : '');
    setOperation($('extractStatus'), `Draft ready. Review every step before export.${transcriptNote}`, 'success');
    toast('Skill draft ready — review it before export.');
  } catch (error) {
    console.error(error);
    setOperation($('extractStatus'), error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

$('createForm').addEventListener('submit', (event) => {
  event.preventDefault();
  runExtraction();
});

$('heroSampleBtn').addEventListener('click', async () => {
  document.querySelector('#studio').scrollIntoView({ behavior: 'smooth' });
  activateTab('createPanel');
  const coffeeName = Object.keys(state.samples).find((name) => name.toLowerCase().includes('pour-over'));
  if (coffeeName) {
    $('sampleSelect').value = coffeeName;
    await runExtraction(coffeeName);
  } else {
    toast('Samples are still loading. Try again in a moment.');
  }
});

$('resetCreateBtn').addEventListener('click', () => {
  state.images.forEach((image) => URL.revokeObjectURL(image.previewUrl));
  state.images = [];
  renderImages();
  $('clearVoiceNoteBtn').click();
  $('sampleSelect').value = '';
  $('sourceText').value = '';
  $('extraNotes').value = '';
  state.extraction = null;
  state.built = null;
  state.transcript = '';
  $('editorWrap').classList.add('hidden');
  $('emptyOutput').classList.remove('hidden');
  setOperation($('extractStatus'), 'Create form reset.');
  updateWalkthrough();
});

/* ------------------------------------------------------------------ build + validation */

function validationTable(validation) {
  if (!validation) return '';
  return `<table class="check-table"><thead><tr><th>Check</th><th>Result</th><th>Detail</th></tr></thead><tbody>
    ${validation.checks.map((check) => `<tr>
      <td>${escapeHtml(check.name)}</td>
      <td class="${check.passed ? 'pass' : 'fail'}">${check.passed ? 'Pass' : 'Fail'}</td>
      <td>${escapeHtml(check.detail || '')}</td>
    </tr>`).join('')}
  </tbody></table>`;
}

function renderValidation(validation, folder = '') {
  $('validationSummary').innerHTML = `
    <span class="validation-chip">${validation.passed ? 'Valid Agent Skill' : 'Needs attention'}</span>
    <span class="validation-chip">${validation.score}/${validation.total} checks passed</span>
    ${folder ? `<span class="validation-chip">Folder: ${escapeHtml(folder)}/</span>` : ''}`;
  $('validationChecks').innerHTML = validationTable(validation);
}

function scheduleBuild() {
  if (!state.extraction) return;
  window.clearTimeout(state.buildTimer);
  $('buildStatus').textContent = 'Editing… validation will refresh automatically.';
  $('buildStatus').className = 'build-status';
  state.buildTimer = window.setTimeout(performBuild, 650);
}

async function performBuild() {
  const extraction = readEditor();
  if (!extraction) return;
  const sequence = ++state.buildSequence;
  $('buildStatus').textContent = 'Validating and packaging with the deterministic builder…';
  $('buildStatus').className = 'build-status';
  try {
    const data = await api('/api/build', {
      method: 'POST',
      body: JSON.stringify({
        extraction,
        audio_base64: state.narrationAudio,
        transcript: state.transcript,
        narration_script: state.narrationScript,
      }),
    });
    if (sequence !== state.buildSequence) return;
    state.built = data;
    renderValidation(data.validation, data.folder);
    $('skillPreview').textContent = data.skill_md;
    $('downloadZipBtn').disabled = !data.zip_included;
    $('downloadMdBtn').disabled = false;
    $('copyMdBtn').disabled = false;
    $('buildStatus').textContent = data.validation.passed
      ? `Valid — ${data.validation.score}/${data.validation.total} checks passed. Zip size: ${formatBytes(data.zip_size_bytes)}.`
      : `${data.validation.score}/${data.validation.total} checks passed. Fix the failed checks before shipping.`;
    $('buildStatus').classList.add(data.validation.passed ? 'is-valid' : 'is-invalid');
    if (data.zip_warning) setOperation($('narrationStatus'), data.zip_warning, 'error');
  } catch (error) {
    if (sequence !== state.buildSequence) return;
    console.error(error);
    $('buildStatus').textContent = `Build failed: ${error.message}`;
    $('buildStatus').classList.add('is-invalid');
  }
}

$('downloadZipBtn').addEventListener('click', () => {
  if (!state.built || !state.built.zip_base64) return;
  downloadBytes(base64ToBytes(state.built.zip_base64), `${state.built.folder}.zip`, 'application/zip');
});

$('downloadMdBtn').addEventListener('click', () => {
  if (!state.built) return;
  downloadText(state.built.skill_md, 'SKILL.md');
});

$('copyMdBtn').addEventListener('click', async () => {
  if (!state.built) return;
  try {
    await navigator.clipboard.writeText(state.built.skill_md);
    toast('SKILL.md copied to the clipboard.');
  } catch (_) {
    toast('Clipboard access was blocked by the browser.');
  }
});

/* ------------------------------------------------------------------ narration */

function localNarrationScript(extraction) {
  if (!extraction) return '';
  const parts = [extraction.title, extraction.description];
  (extraction.steps || []).forEach((step, index) => parts.push(`Step ${index + 1}: ${step}`));
  if ((extraction.constraints || []).length) parts.push(`Important warnings: ${extraction.constraints.join(' ')}`);
  return parts.filter(Boolean).join(' ');
}

function speakWithDevice(text, language = 'English', onEnd = null) {
  if (!('speechSynthesis' in window)) {
    toast('This browser does not provide a device voice.');
    return false;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = languageCodes[language] || 'en-US';
  utterance.rate = 0.96;
  if (onEnd) utterance.onend = onEnd;
  window.speechSynthesis.speak(utterance);
  return true;
}

$('narrateBtn').addEventListener('click', async () => {
  const extraction = readEditor();
  if (!extraction) return;
  const language = $('narrationLanguage').value;
  const wantsExpert = $('narrationVoice').value === 'expert';
  const voiceId = wantsExpert ? $('expertVoiceId').value.trim() : '';
  if (wantsExpert && !voiceId) {
    setOperation($('narrationStatus'), 'Save an expert clone voice ID in the system panel first, or choose the library voice.', 'error');
    return;
  }
  const button = $('narrateBtn');
  button.disabled = true;
  setOperation($('narrationStatus'), 'Preparing the script and requesting ElevenLabs audio…');
  try {
    const data = await api('/api/narrate', {
      method: 'POST',
      body: JSON.stringify({ extraction, language, voice_id: voiceId }),
    });
    state.narrationScript = data.script || '';
    $('narrationScript').textContent = state.narrationScript || 'No script returned.';
    if (data.audio_base64) {
      state.narrationAudio = data.audio_base64;
      const bytes = base64ToBytes(data.audio_base64);
      const url = URL.createObjectURL(new Blob([bytes], { type: data.audio_mime || 'audio/mpeg' }));
      const player = $('narrationAudio');
      player.src = url;
      player.classList.remove('hidden');
      setOperation($('narrationStatus'), 'Narration generated. It will be bundled into the skill zip.', 'success');
      await performBuild();
    } else {
      state.narrationAudio = '';
      setOperation($('narrationStatus'), data.warning || 'Narration audio is unavailable, but the script is ready.', 'error');
      await performBuild();
    }
  } catch (error) {
    console.error(error);
    setOperation($('narrationStatus'), error.message, 'error');
  } finally {
    button.disabled = false;
  }
});

$('deviceReadBtn').addEventListener('click', () => {
  const extraction = readEditor();
  if (!extraction) return;
  const script = state.narrationScript || localNarrationScript(extraction);
  state.narrationScript = script;
  $('narrationScript').textContent = script;
  if (speakWithDevice(script, $('narrationLanguage').value)) {
    setOperation($('narrationStatus'), 'Reading with the browser device voice. This free fallback is not bundled as an MP3.', 'success');
  }
});

/* ------------------------------------------------------------------ walkthrough */

function currentSteps() {
  const extraction = state.extraction;
  return extraction && Array.isArray(extraction.steps) ? extraction.steps : [];
}

function updateWalkthrough(reset = true) {
  if (reset && state.extraction) readEditor();
  const steps = currentSteps();
  const hasSteps = steps.length > 0;
  $('walkthroughEmpty').classList.toggle('hidden', hasSteps);
  $('walkthroughContent').classList.toggle('hidden', !hasSteps);
  if (!hasSteps) return;

  state.walkIndex = Math.max(0, Math.min(state.walkIndex, steps.length - 1));
  const index = state.walkIndex;
  $('walkProgressText').textContent = `Step ${index + 1} of ${steps.length}`;
  $('walkSkillTitle').textContent = state.extraction.title || 'Current skill';
  $('walkProgressBar').style.width = `${steps.length === 1 ? 100 : (index / (steps.length - 1)) * 100}%`;
  $('walkStepCard').innerHTML = `<small>Step ${index + 1}</small><div>${escapeHtml(steps[index])}</div>`;
  $('walkPrevBtn').disabled = index === 0;
  $('walkNextBtn').disabled = index >= steps.length - 1;
  if (index === steps.length - 1) {
    setOperation($('walkStatus'), 'That is the final step.', 'success');
  }
}

$('walkPrevBtn').addEventListener('click', () => {
  state.walkIndex = Math.max(0, state.walkIndex - 1);
  updateWalkthrough(false);
});
$('walkNextBtn').addEventListener('click', () => {
  state.walkIndex = Math.min(currentSteps().length - 1, state.walkIndex + 1);
  updateWalkthrough(false);
});

$('walkSpeakBtn').addEventListener('click', async () => {
  const steps = currentSteps();
  if (!steps.length) return;
  const text = `Step ${state.walkIndex + 1}. ${steps[state.walkIndex]}`;
  const button = $('walkSpeakBtn');
  button.disabled = true;
  setOperation($('walkStatus'), 'Requesting ElevenLabs audio for this step…');
  try {
    const data = await api('/api/speak', {
      method: 'POST',
      body: JSON.stringify({ text, voice_id: $('expertVoiceId').value.trim() }),
    });
    if (data.audio_base64) {
      const bytes = base64ToBytes(data.audio_base64);
      const url = URL.createObjectURL(new Blob([bytes], { type: data.audio_mime || 'audio/mpeg' }));
      const player = $('walkAudio');
      player.src = url;
      player.classList.remove('hidden');
      await player.play();
      setOperation($('walkStatus'), 'Playing the ElevenLabs step narration.', 'success');
    } else {
      setOperation($('walkStatus'), data.warning || 'ElevenLabs audio is unavailable for this step.', 'error');
    }
  } catch (error) {
    console.error(error);
    setOperation($('walkStatus'), error.message, 'error');
  } finally {
    button.disabled = false;
  }
});

$('walkDeviceBtn').addEventListener('click', () => {
  const steps = currentSteps();
  if (!steps.length) return;
  const text = `Step ${state.walkIndex + 1}. ${steps[state.walkIndex]}`;
  const advance = () => {
    if ($('autoAdvanceWalk').checked && state.walkIndex < steps.length - 1) {
      state.walkIndex += 1;
      updateWalkthrough(false);
    }
  };
  if (speakWithDevice(text, 'English', advance)) {
    setOperation($('walkStatus'), 'Reading this step with the browser device voice.', 'success');
  }
});

/* ------------------------------------------------------------------ Fix My Skill */

function renderFixValidation(validation) {
  $('fixValidation').innerHTML = `
    <div class="validation-summary">
      <span class="validation-chip">${validation.passed ? 'Valid Agent Skill' : 'Not compliant yet'}</span>
      <span class="validation-chip">${validation.score}/${validation.total} checks passed</span>
    </div>
    ${validationTable(validation)}`;
}

$('validateSkillBtn').addEventListener('click', async () => {
  const markdown = $('brokenSkill').value;
  setOperation($('fixStatus'), 'Running the thirteen compliance checks…');
  try {
    const data = await api('/api/validate', { method: 'POST', body: JSON.stringify({ markdown }) });
    renderFixValidation(data.validation);
    setOperation($('fixStatus'), data.validation.passed ? 'This skill already passes.' : 'Issues found. Auto-repair can rebuild the structure while preserving workflow lines.', data.validation.passed ? 'success' : 'error');
  } catch (error) {
    setOperation($('fixStatus'), error.message, 'error');
  }
});

$('repairSkillBtn').addEventListener('click', async () => {
  const markdown = $('brokenSkill').value;
  setOperation($('fixStatus'), 'Repairing through the same deterministic builder used for new skills…');
  try {
    const data = await api('/api/repair', { method: 'POST', body: JSON.stringify({ markdown }) });
    state.repaired = data.skill_md;
    $('repairedPreview').textContent = data.skill_md;
    $('repairOutput').classList.remove('hidden');
    renderFixValidation(data.validation);
    setOperation($('fixStatus'), `Repair complete — ${data.validation.score}/${data.validation.total} checks now pass.`, 'success');
  } catch (error) {
    setOperation($('fixStatus'), error.message, 'error');
  }
});

$('downloadRepairedBtn').addEventListener('click', () => {
  if (state.repaired) downloadText(state.repaired, 'SKILL.md');
});

/* ------------------------------------------------------------------ voice cloning */

function renderCloneSampleMeta() {
  const files = [...($('cloneSamples').files || [])];
  const total = files.reduce((sum, file) => sum + file.size, 0);
  $('cloneSampleMeta').textContent = files.length
    ? `${files.length} sample${files.length === 1 ? '' : 's'} selected · ${formatBytes(total)} total. Vercel limit: below 4 MB combined.`
    : 'No samples selected.';
}
$('cloneSamples').addEventListener('change', renderCloneSampleMeta);

$('cloneBtn').addEventListener('click', async () => {
  const files = [...($('cloneSamples').files || [])];
  if (!$('cloneConsent').checked) {
    setOperation($('cloneStatus'), 'Consent is required. No consent, no clone.', 'error');
    return;
  }
  if (!files.length) {
    setOperation($('cloneStatus'), 'Upload at least one clean voice sample.', 'error');
    return;
  }
  const total = files.reduce((sum, file) => sum + file.size, 0);
  if (total > 4_000_000) {
    setOperation($('cloneStatus'), 'Those samples are too large for one Vercel request. Trim them below 4 MB combined.', 'error');
    return;
  }
  const button = $('cloneBtn');
  button.disabled = true;
  setOperation($('cloneStatus'), 'Uploading samples securely to the Snap2Skill API and ElevenLabs…');
  try {
    const samples = [];
    for (const file of files) samples.push(await filePayload(file, file.name));
    const data = await api('/api/clone', {
      method: 'POST',
      body: JSON.stringify({ name: $('cloneName').value.trim(), consent: true, samples }),
    });
    if (data.voice_id) {
      $('expertVoiceId').value = data.voice_id;
      localStorage.setItem('snap2skill.expertVoiceId', data.voice_id);
      $('narrationVoice').value = 'expert';
      setOperation($('cloneStatus'), `Clone created and saved in this browser: ${data.voice_id}`, 'success');
      toast('Expert voice clone created.');
    } else {
      setOperation($('cloneStatus'), data.warning || 'Cloning did not complete.', 'error');
    }
  } catch (error) {
    console.error(error);
    setOperation($('cloneStatus'), error.message, 'error');
  } finally {
    button.disabled = false;
  }
});

/* ------------------------------------------------------------------ expert voice ID */

function loadExpertVoiceId() {
  const saved = localStorage.getItem('snap2skill.expertVoiceId') || '';
  $('expertVoiceId').value = saved;
}
$('saveVoiceIdBtn').addEventListener('click', () => {
  const value = $('expertVoiceId').value.trim();
  if (value) localStorage.setItem('snap2skill.expertVoiceId', value);
  else localStorage.removeItem('snap2skill.expertVoiceId');
  toast(value ? 'Expert voice ID saved in this browser.' : 'Expert voice ID cleared.');
});
$('clearVoiceIdBtn').addEventListener('click', () => {
  $('expertVoiceId').value = '';
  localStorage.removeItem('snap2skill.expertVoiceId');
  if ($('narrationVoice')) $('narrationVoice').value = '';
  toast('Expert voice ID removed from this browser.');
});
$('expertVoiceId').addEventListener('input', () => {
  const value = $('expertVoiceId').value.trim();
  if (value) localStorage.setItem('snap2skill.expertVoiceId', value);
});

/* ------------------------------------------------------------------ init */

loadExpertVoiceId();
renderImages();
renderCloneSampleMeta();
loadBootstrap();

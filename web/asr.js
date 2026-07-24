(() => {
  const CHROME_MIC_SETTINGS_URL = "chrome://settings/content/microphone";
  const PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS = 3;
  const PARTIAL_MIN_RMS = 0.006;
  const PARTIAL_MIN_PEAK = 0.025;
  let activeVoiceStop = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function normalizeMicGain(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 1;
    return Math.min(3, Math.max(0.5, Math.round(number * 10) / 10));
  }

  function formatMicGain(value) {
    return `${normalizeMicGain(value).toFixed(1)}x`;
  }

  function normalizePartialIntervalSeconds(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS;
    return [3, 6, 10].includes(number) ? number : PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS;
  }

  function normalizePartialTranscriptionMode(value) {
    const mode = String(value || "browser");
    if (mode === "nemotron") return "local";
    return ["browser", "off", "local"].includes(mode) ? mode : "browser";
  }

  function normalizeAudioInputDevices(devices = []) {
    return Array.from(devices || [])
      .filter((device) => device?.kind === "audioinput" || (!device?.kind && ("deviceId" in device || "label" in device)))
      .map((device, index) => ({
        deviceId: device.deviceId || "",
        groupId: device.groupId || "",
        label: device.label || "",
        index: index + 1,
      }));
  }

  function audioConstraintsForDevice(deviceId = "") {
    const id = String(deviceId || "");
    const audio = {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: true,
    };
    if (id) audio.deviceId = { exact: id };
    return { audio };
  }

  function isVirtualAudioDeviceLabel(label = "") {
    return /\b(virtual|teams|zoom|obs|blackhole|loopback|soundflower|audio device)\b/i.test(String(label || ""));
  }

  function audioDeviceLabel(device, index, t = (key) => key) {
    const label = device?.label || t("settings.asrMicUnnamed", { index: device?.index || index + 1 });
    return isVirtualAudioDeviceLabel(label)
      ? `${label} ${t("settings.asrMicVirtualBadge")}`
      : label;
  }

  function isDefaultAudioInputDevice(device = {}) {
    const id = String(device?.deviceId || "").toLowerCase();
    const label = String(device?.label || "").toLowerCase();
    return id === "default" || /\b(default|既定)\b/.test(label);
  }

  function preferredRealAudioInputDevice(devices = []) {
    const normalized = normalizeAudioInputDevices(devices);
    return normalized.find((device) => {
      const label = audioDeviceLabel(device, device.index - 1);
      return device.deviceId && !isDefaultAudioInputDevice(device) && !isVirtualAudioDeviceLabel(label);
    }) || null;
  }

  function defaultAudioInputLooksVirtual(devices = []) {
    return normalizeAudioInputDevices(devices).some((device) => {
      if (!isDefaultAudioInputDevice(device)) return false;
      return isVirtualAudioDeviceLabel(device.label);
    });
  }

  function concreteAudioInputCount(devices = []) {
    return normalizeAudioInputDevices(devices).filter((device) => (
      device.deviceId && !isDefaultAudioInputDevice(device)
    )).length;
  }

  function shouldRequestAudioDevicePermission(devices = []) {
    const normalized = normalizeAudioInputDevices(devices);
    if (!normalized.length) return true;
    if (normalized.every((device) => !device.label)) return true;
    return concreteAudioInputCount(normalized) === 0;
  }

  function sleep(ms, root = window) {
    return new Promise((resolve) => (root.setTimeout || setTimeout)(resolve, ms));
  }

  async function listAudioInputDevices({
    navigatorImpl = window.navigator,
    root = window,
    retries = 4,
    retryDelayMs = 120,
  } = {}) {
    const mediaDevices = navigatorImpl?.mediaDevices;
    if (!mediaDevices?.enumerateDevices) return [];
    let devices = normalizeAudioInputDevices(await mediaDevices.enumerateDevices());
    if (shouldRequestAudioDevicePermission(devices) && mediaDevices.getUserMedia) {
      const stream = await mediaDevices.getUserMedia({ audio: true });
      try {
        for (let attempt = 0; attempt <= retries; attempt += 1) {
          if (attempt > 0) await sleep(retryDelayMs, root);
          devices = normalizeAudioInputDevices(await mediaDevices.enumerateDevices());
          if (concreteAudioInputCount(devices) > 0) break;
        }
      } finally {
        stream.getTracks?.().forEach((track) => track.stop?.());
      }
    }
    return devices;
  }

  function setMicLevelUi({ root, t = (key) => key, level = 0, message = "", active = false } = {}) {
    const container = root?.querySelector ? root : (typeof document !== "undefined" ? document : null);
    if (!container) return;
    const clamped = Math.max(0, Math.min(100, Math.round(level)));
    const bar = container.querySelector?.("[data-asr-level-bar]");
    const value = container.querySelector?.("[data-asr-level-value]");
    const status = container.querySelector?.("[data-asr-level-status]");
    if (bar) bar.style.width = `${clamped}%`;
    if (value) value.textContent = `${clamped}%`;
    if (status) status.textContent = message || (active ? t("settings.asrMicLevelActive") : t("settings.asrMicLevelIdle"));
  }

  async function startMicLevelMonitor({
    rootElement,
    deviceId = "",
    micGain = 1,
    navigatorImpl = window.navigator,
    root = window,
    t = (key) => key,
  } = {}) {
    const AudioContextCtor = root.AudioContext || root.webkitAudioContext;
    if (!navigatorImpl?.mediaDevices?.getUserMedia || !AudioContextCtor) {
      throw new Error(t("settings.asrMicLevelUnsupported"));
    }
    setMicLevelUi({ root: rootElement, t, level: 0, message: t("settings.asrMicLevelChecking"), active: true });
    const stream = await navigatorImpl.mediaDevices.getUserMedia(audioConstraintsForDevice(deviceId));
    const track = stream.getAudioTracks?.()[0] || null;
    const context = new AudioContextCtor();
    const analyser = context.createAnalyser();
    const source = context.createMediaStreamSource(stream);
    const gainNode = context.createGain?.();
    const sinkGain = context.createGain?.();
    const floatData = typeof analyser.getFloatTimeDomainData === "function" ? new Float32Array(2048) : null;
    const requestFrame = root.requestAnimationFrame || ((callback) => root.setTimeout(callback, 80));
    const cancelFrame = root.cancelAnimationFrame || root.clearTimeout;
    let frameId = null;
    let tickCount = 0;
    let maxLevel = 0;
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.55;
    if (gainNode) {
      gainNode.gain.value = normalizeMicGain(micGain);
      source.connect(gainNode);
      gainNode.connect(analyser);
    } else {
      source.connect(analyser);
    }
    if (sinkGain && context.destination) {
      sinkGain.gain.value = 0;
      analyser.connect(sinkGain);
      sinkGain.connect(context.destination);
    }
    await context.resume?.();
    const data = new Uint8Array(analyser.fftSize || 2048);
    const trackLabel = track?.label || t("settings.asrMicDeviceDefault");
    const trackState = () => track
      ? `${track.readyState || "unknown"} / ${track.muted ? "muted" : "unmuted"} / ${track.enabled ? "enabled" : "disabled"}`
      : "no-track";
    const debugMessage = (key, level = maxLevel) => t(key, {
      device: trackLabel,
      state: trackState(),
      level: Math.round(level),
    });
    const virtualDevice = isVirtualAudioDeviceLabel(trackLabel);
    const activeMessage = virtualDevice
      ? debugMessage("settings.asrMicLevelVirtualDevice")
      : track?.label
        ? debugMessage("settings.asrMicLevelActiveWithDevice")
      : t("settings.asrMicLevelActive");

    track?.addEventListener?.("mute", () => {
      setMicLevelUi({ root: rootElement, t, level: 0, message: t("settings.asrMicLevelMuted"), active: true });
    });
    track?.addEventListener?.("unmute", () => {
      setMicLevelUi({ root: rootElement, t, level: maxLevel, message: activeMessage, active: true });
    });

    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      let peak = 0;
      if (floatData) {
        analyser.getFloatTimeDomainData(floatData);
        for (const value of floatData) {
          const centered = Math.abs(value);
          sum += centered * centered;
          if (centered > peak) peak = centered;
        }
        sum /= floatData.length;
      } else {
        for (const value of data) {
          const centered = Math.abs((value - 128) / 128);
          sum += centered * centered;
          if (centered > peak) peak = centered;
        }
        sum /= data.length;
      }
      const rms = Math.sqrt(sum);
      const level = Math.min(100, Math.round(Math.max(rms * 900, peak * 260)));
      tickCount += 1;
      maxLevel = Math.max(maxLevel, level);
      const message = tickCount > 24 && maxLevel < 2
        ? debugMessage(virtualDevice ? "settings.asrMicLevelVirtualNoSignal" : "settings.asrMicLevelNoSignal")
        : (virtualDevice
          ? debugMessage("settings.asrMicLevelVirtualDevice", maxLevel)
          : track?.label
            ? debugMessage("settings.asrMicLevelActiveWithDevice", maxLevel)
            : activeMessage);
      setMicLevelUi({ root: rootElement, t, level, message, active: true });
      frameId = requestFrame(tick);
    };
    tick();

    return () => {
      if (frameId !== null) cancelFrame(frameId);
      source.disconnect?.();
      gainNode?.disconnect?.();
      analyser.disconnect?.();
      sinkGain?.disconnect?.();
      stream.getTracks?.().forEach((track) => track.stop?.());
      context.close?.();
      setMicLevelUi({ root: rootElement, t, level: 0, active: false });
    };
  }

  function asrSettingsHtml({
    status = {},
    selectedModel = "",
    setupJob = {},
    micGain = 1,
    micDevices = [],
    micDeviceId = "",
    partialIntervalSeconds = PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS,
    partialMode = "browser",
    t = (key) => key,
  } = {}) {
    const candidates = Array.isArray(status.candidates) ? status.candidates : [];
    const requirements = Array.isArray(status.requirements) ? status.requirements : [];
    const runnableModels = new Set(Array.isArray(status.runnableModels) ? status.runnableModels : []);
    const runnableCandidates = candidates.filter((candidate) => candidate.implemented || runnableModels.has(candidate.model));
    const futureCandidates = candidates.filter((candidate) => !(candidate.implemented || runnableModels.has(candidate.model)));
    const activeModel = runnableModels.has(selectedModel) ? selectedModel : (status.recommendedModel || status.model || "");
    const weightLabels = {
      light: t("settings.asrWeightLight"),
      medium: t("settings.asrWeightMedium"),
      heavy: t("settings.asrWeightHeavy"),
    };
    const stateText = status.status === "checking"
      ? t("settings.asrChecking")
      : status.available
        ? t("settings.asrReady")
        : t("settings.asrNotConfigured");
    const message = status.message || stateText;
    const candidateOptions = runnableCandidates.map((candidate) => {
      const model = candidate.model || "";
      const weight = candidate.weight ? ` / ${weightLabels[candidate.weight] || candidate.weight}` : "";
      const label = `${candidate.label || model}${weight}`;
      return `<option value="${escapeHtml(model)}" ${model === activeModel ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }).join("");
    const normalizedDevices = normalizeAudioInputDevices(micDevices);
    const onlyBrowserDefaultDevice = normalizedDevices.length === 0
      || (normalizedDevices.length === 1 && isDefaultAudioInputDevice(normalizedDevices[0]));
    const selectedDeviceKnown = !micDeviceId || normalizedDevices.some((device) => device.deviceId === micDeviceId);
    const deviceOptions = normalizedDevices.map((device, index) => `
      <option value="${escapeHtml(device.deviceId)}" ${device.deviceId === micDeviceId ? "selected" : ""}>
        ${escapeHtml(audioDeviceLabel(device, index, t))}
      </option>
    `).join("");
    const savedDeviceOption = micDeviceId && !selectedDeviceKnown ? `
      <option value="${escapeHtml(micDeviceId)}" selected>${escapeHtml(t("settings.asrMicSavedDevice"))}</option>
    ` : "";
    const activePartialInterval = normalizePartialIntervalSeconds(partialIntervalSeconds);
    const partialIntervalOptions = [3, 6, 10].map((seconds) => `
      <option value="${seconds}" ${seconds === activePartialInterval ? "selected" : ""}>
        ${escapeHtml(t("settings.asrPartialIntervalOption", { seconds }))}
      </option>
    `).join("");
    const activePartialMode = normalizePartialTranscriptionMode(partialMode);
    const partialModeOptions = [
      ["browser", t("settings.asrPartialModeBrowser")],
      ["off", t("settings.asrPartialModeOff")],
      ["local", t("settings.asrPartialModeLocal")],
    ].map(([mode, label]) => `
      <option value="${escapeHtml(mode)}" ${mode === activePartialMode ? "selected" : ""}>${escapeHtml(label)}</option>
    `).join("");
    const candidateRow = (candidate) => {
      const implemented = candidate.implemented || runnableModels.has(candidate.model);
      return `
      <div class="asr-candidate-row">
        <div class="asr-candidate-info">
          <strong>
            ${escapeHtml(candidate.label || candidate.model || "")}
            ${candidate.weight ? `<span class="asr-weight">${escapeHtml(weightLabels[candidate.weight] || candidate.weight)}</span>` : ""}
            <span class="asr-support ${implemented ? "ready" : "future"}">${escapeHtml(implemented ? t("settings.asrCandidateReady") : t("settings.asrCandidateFuture"))}</span>
          </strong>
          <span>${escapeHtml(candidate.purpose || candidate.model || "")}</span>
          <span>${escapeHtml(candidate.note || "")}</span>
        </div>
        ${candidate.source ? `<a class="asr-source" href="${escapeHtml(candidate.source)}" target="_blank" rel="noopener noreferrer">↗</a>` : ""}
      </div>
    `;
    };
    const runnableRows = runnableCandidates.map(candidateRow).join("");
    const futureRows = futureCandidates.map(candidateRow).join("");
    const requirementRows = requirements.map((item) => `
      <div class="asr-requirement ${item.ok ? "ready" : "missing"}">
        <span>${escapeHtml(item.ok ? t("settings.asrRequirementOk") : t("settings.asrRequirementMissing"))}</span>
        <strong>${escapeHtml(item.label || item.id || "")}</strong>
        <small>${escapeHtml(item.detail || item.hint || "")}</small>
      </div>
    `).join("");
    const setupRunning = setupJob?.status === "running" || setupJob?.status === "queued";
    const setupMessage = setupJob?.message ? `
      <div class="asr-status">${escapeHtml(t("settings.asrSetupStatus"))}: ${escapeHtml(setupJob.message)}${setupJob.percent !== null && setupJob.percent !== undefined && Number.isFinite(Number(setupJob.percent)) ? ` (${Math.round(Number(setupJob.percent))}%)` : ""}</div>
    ` : "";
    const setupButton = requirements.length && status.dependenciesOk === false ? `
      <button class="ghost-button model-install-button" type="button" data-asr-setup ${setupRunning ? "disabled" : ""}>
        ${escapeHtml(setupRunning ? t("settings.asrSetupRunning") : t("settings.asrSetup"))}
      </button>
    ` : "";
    const browserMicNotice = onlyBrowserDefaultDevice ? `
      <div class="asr-hint">
        <strong>${escapeHtml(t("settings.asrBrowserMicOnlyTitle"))}</strong>
        <span>${escapeHtml(t("settings.asrBrowserMicOnlyHelp"))}</span>
        <div class="asr-inline-actions">
          <code>${escapeHtml(CHROME_MIC_SETTINGS_URL)}</code>
          <button class="ghost-button" type="button" data-asr-open-mic-settings>${escapeHtml(t("settings.asrOpenChromeMicSettings"))}</button>
          <button class="ghost-button" type="button" data-asr-copy-mic-settings>${escapeHtml(t("settings.asrCopyChromeMicSettings"))}</button>
        </div>
      </div>
    ` : "";
    return `
      <div class="asr-panel-title">
        <strong>${escapeHtml(t("settings.asrTitle"))}</strong>
        <span>${escapeHtml(t("settings.asrHelp"))}</span>
      </div>
      <div class="asr-status">${escapeHtml(stateText)} ${escapeHtml(message)}</div>
      <label class="asr-model-field">
        <span>${escapeHtml(t("settings.asrModelSelect"))}</span>
        <select data-asr-model>
          <option value="">${escapeHtml(t("settings.asrModelAuto"))}</option>
          ${candidateOptions}
        </select>
        <small>${escapeHtml(t("settings.asrModelSelectHelp"))}</small>
      </label>
      <label class="asr-model-field">
        <span>${escapeHtml(t("settings.asrMicGain"))}</span>
        <div class="asr-range-row">
          <input type="range" min="0.5" max="3" step="0.1" value="${escapeHtml(normalizeMicGain(micGain))}" data-asr-mic-gain>
          <output data-asr-mic-gain-value>${escapeHtml(formatMicGain(micGain))}</output>
        </div>
        <small>${escapeHtml(t("settings.asrMicGainHelp"))}</small>
      </label>
      <label class="asr-model-field">
        <span>${escapeHtml(t("settings.asrPartialMode"))}</span>
        <select data-asr-partial-mode>
          ${partialModeOptions}
        </select>
        <small>${escapeHtml(t("settings.asrPartialModeHelp"))}</small>
      </label>
      <label class="asr-model-field ${activePartialMode === "local" ? "" : "asr-nemotron-partial-field"}">
        <span>${escapeHtml(t("settings.asrPartialInterval"))}</span>
        <select data-asr-partial-interval>
          ${partialIntervalOptions}
        </select>
        <small>${escapeHtml(t("settings.asrPartialIntervalHelp"))}</small>
      </label>
      <label class="asr-model-field">
        <span>${escapeHtml(t("settings.asrMicDevice"))}</span>
        <div class="asr-device-row">
          <select data-asr-mic-device>
            <option value="">${escapeHtml(t("settings.asrMicDeviceDefault"))}</option>
            ${savedDeviceOption}
            ${deviceOptions}
          </select>
          <button class="ghost-button" type="button" data-asr-mic-check>${escapeHtml(t("settings.asrMicCheck"))}</button>
        </div>
        <small>${escapeHtml(t("settings.asrMicDeviceHelp"))}</small>
      </label>
      ${browserMicNotice}
      <div class="asr-level-panel" aria-live="polite">
        <div class="asr-level-header">
          <span>${escapeHtml(t("settings.asrMicLevel"))}</span>
          <div class="asr-level-actions">
            <output data-asr-level-value>0%</output>
            <button class="ghost-button" type="button" data-asr-stop-mic>${escapeHtml(t("settings.asrMicStop"))}</button>
          </div>
        </div>
        <div class="asr-level-meter" aria-hidden="true"><span data-asr-level-bar></span></div>
        <small data-asr-level-status>${escapeHtml(t("settings.asrMicLevelIdle"))}</small>
      </div>
      ${requirementRows ? `<div class="asr-status">${escapeHtml(t("settings.asrRequirements"))}</div><div class="asr-requirements">${requirementRows}</div>` : ""}
      ${runnableRows ? `<div class="asr-status">${escapeHtml(t("settings.asrRunnableCandidates"))}</div>${runnableRows}` : ""}
      ${futureRows ? `<div class="asr-status">${escapeHtml(t("settings.asrFutureCandidates"))}</div>${futureRows}` : ""}
      <div class="asr-next-step"><strong>${escapeHtml(t("settings.asrNextStep"))}:</strong> ${escapeHtml(status.nextStep || "")}</div>
      ${setupMessage}
      ${setupButton}
      <button class="ghost-button model-install-button" type="button" data-asr-refresh>${escapeHtml(t("settings.asrRefresh"))}</button>
    `;
  }

  function renderAsrSettings({ container, status, selectedModel, setupJob, micGain, micDevices, micDeviceId, partialIntervalSeconds, partialMode, t } = {}) {
    if (!container) return;
    container.innerHTML = asrSettingsHtml({ status, selectedModel, setupJob, micGain, micDevices, micDeviceId, partialIntervalSeconds, partialMode, t });
  }

  function asrUnavailableMessage(status = {}, t = (key) => key) {
    if (status.status === "needs_dependencies" || status.requirementsOk === false) {
      const missing = Array.isArray(status.requirements)
        ? status.requirements
          .filter((item) => !item.ok)
          .map((item) => item.label || item.id)
          .filter(Boolean)
        : [];
      const missingText = missing.length ? missing.join("、") : t("settings.asrRequirements");
      return t("composer.voiceNeedsSetup", { missing: missingText });
    }
    return status.message || t("composer.voiceUnavailable");
  }

  function setComposerStatus({ els, message = "", status = "idle" }) {
    if (!els?.composerStatus) return;
    els.composerStatus.textContent = message;
    els.composerStatus.hidden = !message;
    els.composerStatus.classList?.toggle("recording", status === "recording" && Boolean(message));
  }

  function renderAsrStatus({ els, t = (key) => key, status = "idle", seconds = 0, message = "" }) {
    const voiceButton = els?.voiceInput;
    if (voiceButton) {
      voiceButton.classList.toggle("recording", status === "recording" || status === "partial" || status === "live");
      if (voiceButton.dataset) voiceButton.dataset.asrStatus = status;
    }

    if (status === "checking") {
      setComposerStatus({ els, message: message || t("composer.voiceChecking") });
      return;
    }
    if (status === "recording") {
      setComposerStatus({ els, message: t("composer.voiceRecording", { seconds }), status });
      return;
    }
    if (status === "partial") {
      setComposerStatus({ els, message: message || t("composer.voicePartialTranscribing", { seconds }), status: "recording" });
      return;
    }
    if (status === "live") {
      setComposerStatus({ els, message: t("composer.voiceLiveRecording", { seconds }), status: "recording" });
      return;
    }
    if (status === "unavailable") {
      setComposerStatus({ els, message: message || t("composer.voiceUnavailable") });
      return;
    }
    if (status === "error") {
      setComposerStatus({ els, message: message || t("composer.voiceError") });
      return;
    }
    setComposerStatus({ els, message: "" });
  }

  async function fetchAsrStatus({ fetchImpl = window.fetch } = {}) {
    const response = await fetchImpl("/api/asr/status", { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error || `ASR status failed: ${response.status}`);
    }
    return payload;
  }

  async function fetchAsrSetupStatus({ fetchImpl = window.fetch } = {}) {
    const response = await fetchImpl("/api/asr/setup/status", { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.error || `ASR setup status failed: ${response.status}`);
    }
    return payload;
  }

  async function requestAsrSetup({ fetchImpl = window.fetch } = {}) {
    const response = await fetchImpl("/api/asr/setup", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.error || `ASR setup failed: ${response.status}`);
    }
    return payload;
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.addEventListener("load", () => {
        const result = String(reader.result || "");
        resolve(result.includes(",") ? result.split(",").pop() : result);
      });
      reader.addEventListener("error", () => reject(reader.error || new Error("Could not read audio")));
      reader.readAsDataURL(blob);
    });
  }

  async function transcribeAudio({
    audioBlob,
    model = "",
    fetchImpl = window.fetch,
    base64Encoder = blobToBase64,
  } = {}) {
    if (!audioBlob) throw new Error("No audio was recorded.");
    const audioBase64 = await base64Encoder(audioBlob);
    const response = await fetchImpl("/api/asr/transcribe", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        audioBase64,
        mimeType: audioBlob.type || "audio/webm",
        model,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error || `ASR transcription failed: ${response.status}`);
    }
    return payload;
  }

  async function recordAudio({
    maxSeconds = 0,
    navigatorImpl = window.navigator,
    mediaRecorderFactory,
    micGain = 1,
    micDeviceId = "",
    onTick,
    onPartialBlob,
    partialIntervalSeconds = PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS,
    stopElement,
  } = {}) {
    if (!navigatorImpl?.mediaDevices?.getUserMedia) {
      throw new Error("Microphone recording is not supported in this browser.");
    }
    if (typeof MediaRecorder === "undefined") {
      throw new Error("MediaRecorder is not supported in this browser.");
    }
    const stream = await navigatorImpl.mediaDevices.getUserMedia(audioConstraintsForDevice(micDeviceId));
    return new Promise((resolve, reject) => {
      const chunks = [];
      let recorder;
      let timer = null;
      let tickTimer = null;
      let partialTimer = null;
      let seconds = 0;
      let partialChunks = [];
      const recording = gainAdjustedStream({ stream, gain: micGain });
      const wavPartialCapture = createWavPartialCapture({
        stream: recording.stream,
        intervalSeconds: partialIntervalSeconds,
        onPartialBlob,
      });
      const stopTracks = () => {
        stream.getTracks?.().forEach((track) => track.stop?.());
        if (recording.stream !== stream) {
          recording.stream.getTracks?.().forEach((track) => track.stop?.());
        }
        recording.cleanup?.();
      };
      const cleanup = () => {
        window.clearTimeout(timer);
        window.clearInterval(tickTimer);
        window.clearInterval(partialTimer);
        wavPartialCapture?.stop?.();
        stopElement?.removeEventListener?.("click", stopRecording);
        clearActiveVoiceStop(stopRecording);
        stopTracks();
      };
      const stopRecording = () => {
        if (recorder?.state && recorder.state !== "inactive") recorder.stop();
      };
      try {
        recorder = mediaRecorderFactory ? mediaRecorderFactory(recording.stream) : new MediaRecorder(recording.stream, mediaRecorderOptions());
      } catch (error) {
        stopTracks();
        reject(error);
        return;
      }
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data?.size) {
          chunks.push(event.data);
          partialChunks.push(event.data);
        }
      });
      recorder.addEventListener("error", (event) => {
        cleanup();
        reject(event.error || new Error("Audio recording failed."));
      });
      recorder.addEventListener("stop", () => {
        cleanup();
        resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
      });
      recorder.start();
      wavPartialCapture?.start?.();
      setActiveVoiceStop(stopRecording);
      onTick?.(0);
      stopElement?.addEventListener?.("click", stopRecording);
      const emitPartial = () => {
        if (!partialChunks.length || typeof onPartialBlob !== "function") return;
        const blob = new Blob(partialChunks, { type: recorder.mimeType || "audio/webm" });
        partialChunks = [];
        Promise.resolve(onPartialBlob(blob, seconds)).catch(() => {});
      };
      tickTimer = window.setInterval(() => {
        seconds += 1;
        onTick?.(seconds);
      }, 1000);
      if (!wavPartialCapture && typeof onPartialBlob === "function" && Number(partialIntervalSeconds) > 0) {
        partialTimer = window.setInterval(() => {
          if (recorder.state === "recording" && typeof recorder.requestData === "function") {
            recorder.requestData();
            window.setTimeout(emitPartial, 250);
          }
        }, Number(partialIntervalSeconds) * 1000);
      }
      if (Number(maxSeconds) > 0) {
        timer = window.setTimeout(() => {
          if (recorder.state !== "inactive") recorder.stop();
        }, maxSeconds * 1000);
      }
    });
  }

  function mediaRecorderOptions() {
    const supported = supportedAudioMimeType();
    return supported ? { mimeType: supported } : undefined;
  }

  function supportedAudioMimeType() {
    if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") return "";
    return [
      "audio/mp4",
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
    ].find((type) => MediaRecorder.isTypeSupported(type)) || "";
  }

  function gainAdjustedStream({ stream, gain = 1, root = window } = {}) {
    const safeGain = normalizeMicGain(gain);
    const AudioContextCtor = root.AudioContext || root.webkitAudioContext;
    if (!stream || Math.abs(safeGain - 1) < 0.01 || !AudioContextCtor) {
      return { stream, cleanup: () => {} };
    }
    try {
      const context = new AudioContextCtor();
      const source = context.createMediaStreamSource(stream);
      const gainNode = context.createGain();
      const destination = context.createMediaStreamDestination();
      gainNode.gain.value = safeGain;
      source.connect(gainNode);
      gainNode.connect(destination);
      return {
        stream: destination.stream,
        cleanup: () => {
          source.disconnect?.();
          gainNode.disconnect?.();
          context.close?.();
        },
      };
    } catch {
      return { stream, cleanup: () => {} };
    }
  }

  function speechRecognitionConstructor(root = window) {
    return root?.SpeechRecognition || root?.webkitSpeechRecognition || null;
  }

  function liveSpeechRecognitionAvailable(root = window) {
    return Boolean(speechRecognitionConstructor(root));
  }

  function composeLivePromptValue(baseValue, finalText, interimText) {
    const base = String(baseValue || "");
    const transcript = [finalText, interimText].map((value) => String(value || "").trim()).filter(Boolean).join("");
    if (!transcript) return base;
    const separator = base && !/\s$/.test(base) ? "\n" : "";
    return `${base}${separator}${transcript}`;
  }

  function setActiveVoiceStop(stopFn) {
    activeVoiceStop = typeof stopFn === "function" ? stopFn : null;
  }

  function clearActiveVoiceStop(stopFn) {
    if (!stopFn || activeVoiceStop === stopFn) activeVoiceStop = null;
  }

  function requestActiveVoiceStop() {
    if (!activeVoiceStop) return false;
    activeVoiceStop();
    return true;
  }

  function mergeFloat32Chunks(chunks) {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    return merged;
  }

  function audioSignalStats(samples) {
    let peak = 0;
    let squareSum = 0;
    const length = samples?.length || 0;
    for (let index = 0; index < length; index += 1) {
      const absolute = Math.abs(Number(samples[index]) || 0);
      if (absolute > peak) peak = absolute;
      squareSum += absolute * absolute;
    }
    return {
      peak,
      rms: length ? Math.sqrt(squareSum / length) : 0,
      samples: length,
    };
  }

  function hasAudibleSignal(samples, { minRms = PARTIAL_MIN_RMS, minPeak = PARTIAL_MIN_PEAK } = {}) {
    const stats = audioSignalStats(samples);
    return stats.rms >= minRms || stats.peak >= minPeak;
  }

  function wavBlobFromFloat32(samples, sampleRate, BlobCtor = Blob) {
    const bytesPerSample = 2;
    const blockAlign = bytesPerSample;
    const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
    const view = new DataView(buffer);
    const writeString = (offset, value) => {
      for (let index = 0; index < value.length; index += 1) {
        view.setUint8(offset + index, value.charCodeAt(index));
      }
    };
    writeString(0, "RIFF");
    view.setUint32(4, 36 + samples.length * bytesPerSample, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, samples.length * bytesPerSample, true);
    let offset = 44;
    for (const sample of samples) {
      const clamped = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
      offset += bytesPerSample;
    }
    return new BlobCtor([buffer], { type: "audio/wav" });
  }

  function createWavPartialCapture({
    stream,
    root = window,
    intervalSeconds = PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS,
    onPartialBlob,
    BlobCtor = Blob,
  } = {}) {
    const AudioContextCtor = root.AudioContext || root.webkitAudioContext;
    if (!stream || !AudioContextCtor || typeof onPartialBlob !== "function") return null;
    let context;
    let source;
    let processor;
    let sinkGain;
    let timer = null;
    let sampleChunks = [];
    let emittedSeconds = 0;
    const safeIntervalSeconds = Math.max(2, Number(intervalSeconds) || PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS);
    const flush = () => {
      if (!sampleChunks.length || !context?.sampleRate) return;
      const samples = mergeFloat32Chunks(sampleChunks);
      sampleChunks = [];
      if (samples.length < context.sampleRate * 0.8) return;
      if (!hasAudibleSignal(samples)) return;
      emittedSeconds += samples.length / context.sampleRate;
      const blob = wavBlobFromFloat32(samples, context.sampleRate, BlobCtor);
      Promise.resolve(onPartialBlob(blob, Math.round(emittedSeconds))).catch(() => {});
    };
    try {
      context = new AudioContextCtor();
      source = context.createMediaStreamSource(stream);
      processor = context.createScriptProcessor?.(4096, 1, 1);
      if (!processor) return null;
      sinkGain = context.createGain?.();
      if (sinkGain) sinkGain.gain.value = 0;
      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer?.getChannelData?.(0);
        if (!input?.length) return;
        sampleChunks.push(new Float32Array(input));
      };
      source.connect(processor);
      if (sinkGain && context.destination) {
        processor.connect(sinkGain);
        sinkGain.connect(context.destination);
      } else {
        processor.connect(context.destination);
      }
      return {
        start() {
          context.resume?.();
          timer = root.setInterval?.(flush, safeIntervalSeconds * 1000);
        },
        stop() {
          root.clearInterval?.(timer);
          flush();
          processor.disconnect?.();
          source.disconnect?.();
          sinkGain?.disconnect?.();
          context.close?.();
        },
      };
    } catch {
      try {
        context?.close?.();
      } catch {
        // Ignore cleanup errors for unsupported audio contexts.
      }
      return null;
    }
  }

  function recordLiveSpeech({
    els,
    t = (key) => key,
    onResize,
    language = "ja-JP",
    maxSeconds = 0,
    root = window,
    recognitionFactory,
    stopElement,
  } = {}) {
    const Recognition = recognitionFactory || speechRecognitionConstructor(root);
    if (!Recognition) {
      throw new Error(t("composer.voiceLiveUnavailable"));
    }
    const recognition = new Recognition();
    const baseValue = String(els?.prompt?.value || "");
    let finalText = "";
    let interimText = "";
    let seconds = 0;
    let tickTimer = null;
    let stopTimer = null;
    let stopFallbackTimer = null;
    let settled = false;

    const updatePrompt = () => {
      if (!els?.prompt) return;
      els.prompt.value = composeLivePromptValue(baseValue, finalText, interimText);
      onResize?.();
    };

    return new Promise((resolve, reject) => {
      const cleanup = () => {
        root.clearInterval?.(tickTimer);
        root.clearTimeout?.(stopTimer);
        root.clearTimeout?.(stopFallbackTimer);
        stopElement?.removeEventListener?.("click", stopRecognition);
        clearActiveVoiceStop(stopRecognition);
      };
      const finish = () => {
        if (settled) return;
        settled = true;
        cleanup();
        const text = (finalText || interimText).trim();
        updatePrompt();
        resolve({ ok: Boolean(text), text, live: true });
      };
      const fail = (error) => {
        if (settled) return;
        settled = true;
        cleanup();
        reject(error);
      };
      const stopRecognition = () => {
        if (settled) return;
        try {
          recognition.stop();
        } catch {
          try {
            recognition.abort?.();
          } catch {
            // Ignore abort errors and fall through to the forced finish.
          }
        }
        stopFallbackTimer = root.setTimeout?.(finish, 800);
      };

      recognition.lang = language || "ja-JP";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.onresult = (event) => {
        interimText = "";
        const results = event?.results || [];
        for (let index = event?.resultIndex || 0; index < results.length; index += 1) {
          const result = results[index];
          const transcript = Array.from(result || [])
            .map((item) => item?.transcript || "")
            .join("")
            .trim();
          if (!transcript) continue;
          if (result?.isFinal) finalText += transcript;
          else interimText += transcript;
        }
        updatePrompt();
      };
      recognition.onerror = (event) => {
        const code = event?.error || "";
        if (code === "no-speech") {
          finish();
          return;
        }
        fail(new Error(t("composer.voiceLiveError", { error: code || t("composer.voiceError") })));
      };
      recognition.onend = finish;

      try {
        recognition.start();
      } catch (error) {
        fail(error);
        return;
      }
      setActiveVoiceStop(stopRecognition);
      stopElement?.addEventListener?.("click", stopRecognition);
      tickTimer = root.setInterval?.(() => {
        seconds += 1;
        renderAsrStatus({ els, t, status: "live", seconds });
      }, 1000);
      if (Number(maxSeconds) > 0) {
        stopTimer = root.setTimeout?.(stopRecognition, Number(maxSeconds) * 1000);
      }
    });
  }

  async function handleVoiceInputClick({
    els,
    t = (key) => key,
    fetchImpl = window.fetch,
    getSelectedModel = () => "",
    recorder = recordAudio,
    liveRecorder = recordLiveSpeech,
    speechRoot = window,
    getMicGain = () => 1,
    getMicDeviceId = () => "",
    getPartialIntervalSeconds = () => PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS,
    getPartialMode = () => "browser",
    base64Encoder = blobToBase64,
    onTranscript,
    onResize,
  } = {}) {
    if (els?.voiceInput?.dataset) els.voiceInput.dataset.asrBusy = "true";
    const runLiveFallback = async () => {
      if (!liveSpeechRecognitionAvailable(speechRoot)) return null;
      renderAsrStatus({ els, t, status: "live", seconds: 0 });
      const liveResult = await liveRecorder({
        els,
        t,
        onResize,
        stopElement: els?.voiceInput,
        root: speechRoot,
      });
      if (liveResult.text) {
        renderAsrStatus({ els, t, status: "idle" });
      } else {
        renderAsrStatus({ els, t, status: "unavailable", message: t("composer.voiceEmpty") });
      }
      return liveResult;
    };
    try {
      renderAsrStatus({ els, t, status: "checking" });
      let status = null;
      try {
        status = await fetchAsrStatus({ fetchImpl });
      } catch (error) {
        const fallback = await runLiveFallback();
        if (fallback) return fallback;
        throw error;
      }
      const runnableModels = new Set(Array.isArray(status.runnableModels) ? status.runnableModels : []);
      const requestedModel = getSelectedModel?.() || "";
      const selectedModel = runnableModels.has(requestedModel)
        ? requestedModel
        : (status.recommendedModel || status.model || "");
      const selectedModelReady = Boolean(selectedModel && runnableModels.has(selectedModel));
      if (!status.available && !selectedModelReady) {
        const fallback = await runLiveFallback();
        if (fallback) return fallback;
        renderAsrStatus({ els, t, status: "unavailable", message: asrUnavailableMessage(status, t) });
        return status;
      }
      renderAsrStatus({ els, t, status: "recording", seconds: 0 });
      const basePromptValue = String(els?.prompt?.value || "");
      const partialTexts = [];
      let recordingDone = false;
      let partialBusy = false;
      let elapsedSeconds = 0;
      let livePreviewStarted = false;
      const partialMode = normalizePartialTranscriptionMode(getPartialMode?.());
      const renderPartialTranscript = () => {
        if (recordingDone || !els?.prompt || !partialTexts.length) return;
        els.prompt.value = composeLivePromptValue(basePromptValue, partialTexts.join(" "), "");
        onResize?.();
      };
      if (partialMode === "browser" && els?.prompt && liveSpeechRecognitionAvailable(speechRoot)) {
        livePreviewStarted = true;
        Promise.resolve(liveRecorder({
          els,
          t,
          onResize,
          stopElement: els?.voiceInput,
          root: speechRoot,
          maxSeconds: 0,
        })).catch(() => {});
      }
      const handleLocalPartial = partialMode === "local"
        ? async (partialBlob) => {
          if (recordingDone || partialBusy || !partialBlob?.size) return;
          partialBusy = true;
          renderAsrStatus({ els, t, status: "partial", seconds: elapsedSeconds });
          try {
            const partial = await transcribeAudio({ audioBlob: partialBlob, model: selectedModel, fetchImpl, base64Encoder });
            const text = String(partial?.text || "").trim();
            if (text && !recordingDone) {
              partialTexts.push(text);
              renderPartialTranscript();
            }
          } catch {
            // Partial transcription is best-effort. The final transcription still runs after stop.
          } finally {
            partialBusy = false;
            if (!recordingDone) renderAsrStatus({ els, t, status: "recording", seconds: elapsedSeconds });
          }
        }
        : null;
      const audioBlob = await recorder({
        micGain: getMicGain?.() ?? 1,
        micDeviceId: getMicDeviceId?.() || "",
        partialIntervalSeconds: normalizePartialIntervalSeconds(getPartialIntervalSeconds?.()),
        onTick: (seconds) => {
          elapsedSeconds = seconds;
          renderAsrStatus({ els, t, status: partialBusy ? "partial" : "recording", seconds });
        },
        onPartialBlob: handleLocalPartial,
        stopElement: els?.voiceInput,
      });
      recordingDone = true;
      renderAsrStatus({ els, t, status: "checking", message: t("composer.voiceTranscribing") });
      const result = await transcribeAudio({ audioBlob, model: selectedModel, fetchImpl, base64Encoder });
      if (result.text) {
        if (els?.prompt && (partialTexts.length || livePreviewStarted)) {
          els.prompt.value = basePromptValue;
          onResize?.();
        }
        onTranscript?.(result.text);
        renderAsrStatus({ els, t, status: "idle" });
      } else {
        renderAsrStatus({ els, t, status: "unavailable", message: result.message || t("composer.voiceEmpty") });
      }
      return result;
    } catch (error) {
      renderAsrStatus({ els, t, status: "error", message: error.message || t("composer.voiceError") });
      return null;
    } finally {
      if (els?.voiceInput?.dataset) els.voiceInput.dataset.asrBusy = "false";
    }
  }

  function appendTranscriptToPrompt({ els, text, onResize }) {
    const transcript = String(text || "").trim();
    if (!transcript || !els?.prompt) return false;

    const current = els.prompt.value;
    const separator = current && !/\s$/.test(current) ? "\n" : "";
    els.prompt.value = `${current}${separator}${transcript}`;
    onResize?.();
    els.prompt.focus();
    return true;
  }

  function bindAsrUi({ els, t = (key) => key, onResize, fetchImpl, getSelectedModel, getMicGain, getMicDeviceId, getPartialIntervalSeconds, getPartialMode } = {}) {
    if (!els?.voiceInput) return;
    els.voiceInput.addEventListener("click", (event) => {
      event.preventDefault();
      if (els.voiceInput.dataset.asrBusy === "true") {
        requestActiveVoiceStop();
        return;
      }
      handleVoiceInputClick({
        els,
        t,
        fetchImpl,
        getSelectedModel,
        getMicGain,
        getMicDeviceId,
        getPartialIntervalSeconds,
        getPartialMode,
        onResize,
        onTranscript: (text) => appendTranscriptToPrompt({ els, text, onResize }),
      });
    });
    els.voiceInput.dataset.asrBound = "true";
    els.voiceInput.dataset.asrResize = String(Boolean(onResize));
  }

  window.GEMMA_ASR = {
    appendTranscriptToPrompt,
    audioConstraintsForDevice,
    asrUnavailableMessage,
    asrSettingsHtml,
    bindAsrUi,
    blobToBase64,
    CHROME_MIC_SETTINGS_URL,
    PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS,
    audioSignalStats,
    createWavPartialCapture,
    fetchAsrSetupStatus,
    fetchAsrStatus,
    handleVoiceInputClick,
    recordAudio,
    renderAsrSettings,
    renderAsrStatus,
    requestAsrSetup,
    requestActiveVoiceStop,
    setComposerStatus,
    composeLivePromptValue,
    concreteAudioInputCount,
    defaultAudioInputLooksVirtual,
    formatMicGain,
    gainAdjustedStream,
    listAudioInputDevices,
    liveSpeechRecognitionAvailable,
    mergeFloat32Chunks,
    hasAudibleSignal,
    isVirtualAudioDeviceLabel,
    normalizeAudioInputDevices,
    normalizeMicGain,
    normalizePartialIntervalSeconds,
    normalizePartialTranscriptionMode,
    preferredRealAudioInputDevice,
    recordLiveSpeech,
    speechRecognitionConstructor,
    setMicLevelUi,
    startMicLevelMonitor,
    supportedAudioMimeType,
    transcribeAudio,
    wavBlobFromFloat32,
  };
})();

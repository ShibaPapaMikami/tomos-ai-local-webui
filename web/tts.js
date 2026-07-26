(() => {
  const MAX_AUDIO_BYTES = 10 * 1024 * 1024;
  const MAX_CHUNK_BYTES = 1024 * 1024;

  function defaultTtsSettings() {
    return {
      autoPlay: false,
      voice: "default",
      language: "ja",
    };
  }

  function normalizeTtsText(value) {
    return String(value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .join("\n")
      .slice(0, 1000);
  }

  function shouldApplyTtsResult({ activeRequestId, resultRequestId, stopped }) {
    return !stopped && Boolean(activeRequestId) && activeRequestId === resultRequestId;
  }

  function decodeBase64(value) {
    try {
      const binary = window.atob(String(value || ""));
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      return bytes;
    } catch {
      return null;
    }
  }

  function validateTtsStreamEvent(event, state) {
    if (!event || event.requestId !== state.activeRequestId) {
      return { ok: false, error: "tts_request_id_mismatch" };
    }
    if (!["start", "audio", "done", "error"].includes(event.type)) {
      return { ok: false, error: "tts_stream_event_invalid" };
    }
    if (event.type === "start") {
      if (event.mimeType !== "audio/pcm;codec=s16le" || event.channels !== 1) {
        return { ok: false, error: "tts_stream_format_invalid" };
      }
      if (![16000, 22050, 24000, 44100, 48000].includes(event.sampleRate)) {
        return { ok: false, error: "tts_stream_sample_rate_invalid" };
      }
    }
    if (event.type === "audio") {
      if (event.sequence !== state.expectedSequence) {
        return { ok: false, error: "tts_stream_sequence_invalid" };
      }
      const bytes = decodeBase64(event.audioBase64);
      if (!bytes || bytes.byteLength > MAX_CHUNK_BYTES || bytes.byteLength % 2 !== 0) {
        return { ok: false, error: "tts_stream_audio_invalid" };
      }
      return { ok: true, bytes };
    }
    if (event.type === "done" && (!Number.isInteger(event.chunks) || event.chunks !== state.expectedSequence)) {
      return { ok: false, error: "tts_stream_chunk_count_invalid" };
    }
    if (event.type === "error" && typeof event.error !== "string") {
      return { ok: false, error: "tts_stream_error_invalid" };
    }
    return { ok: true };
  }

  function createTtsController({
    fetchImpl = window.fetch?.bind(window),
    AudioClass = window.Audio,
    AudioContextClass = window.AudioContext || window.webkitAudioContext,
    URLImpl = window.URL,
    onStateChange = () => {},
  } = {}) {
    let activeRequestId = "";
    let stopped = true;
    let abortController = null;
    let audio = null;
    let objectUrl = "";
    let audioContext = null;
    let scheduledSources = [];
    let nextStartTime = 0;
    let replayChunks = [];
    let replaySampleRate = 0;
    let replayRequest = null;
    let totalStreamBytes = 0;
    const cancelledRequestIds = new Set();

    function emit(status, error = "", requestId = activeRequestId) {
      if (requestId !== activeRequestId) return;
      onStateChange({ status, requestId, error });
    }

    function releasePlayback({ clearReplay = false } = {}) {
      if (audio) {
        audio.pause?.();
        try { audio.currentTime = 0; } catch {}
        audio = null;
      }
      scheduledSources.forEach((source) => {
        try { source.stop(); } catch {}
      });
      scheduledSources = [];
      if (audioContext) {
        audioContext.close?.().catch?.(() => {});
        audioContext = null;
      }
      if (objectUrl) {
        URLImpl?.revokeObjectURL?.(objectUrl);
        objectUrl = "";
      }
      if (clearReplay) {
        replayChunks = [];
        replaySampleRate = 0;
        replayRequest = null;
      }
    }

    function sendCancel(requestId) {
      if (!requestId || cancelledRequestIds.has(requestId) || !fetchImpl) return;
      cancelledRequestIds.add(requestId);
      Promise.resolve(fetchImpl("/api/tts/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requestId }),
      })).catch(() => {});
    }

    function stop({ clearReplay = false } = {}) {
      const requestId = activeRequestId;
      stopped = true;
      abortController?.abort();
      abortController = null;
      releasePlayback({ clearReplay });
      sendCancel(requestId);
      emit("stopped");
    }

    function pcmBytesToFloat32(bytes) {
      const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      const samples = new Float32Array(bytes.byteLength / 2);
      for (let index = 0; index < samples.length; index += 1) {
        samples[index] = view.getInt16(index * 2, true) / 32768;
      }
      return samples;
    }

    function schedulePcm(bytes, sampleRate) {
      if (!AudioContextClass) throw new Error("tts_audio_context_unavailable");
      if (!audioContext) {
        audioContext = new AudioContextClass({ sampleRate });
        nextStartTime = audioContext.currentTime;
      }
      const samples = pcmBytesToFloat32(bytes);
      const buffer = audioContext.createBuffer(1, samples.length, sampleRate);
      buffer.copyToChannel(samples, 0);
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(audioContext.destination);
      source.__ttsEnded = false;
      source.onended = () => {
        source.__ttsEnded = true;
      };
      const startAt = Math.max(audioContext.currentTime + 0.03, nextStartTime);
      source.start(startAt);
      nextStartTime = startAt + buffer.duration;
      scheduledSources.push(source);
      return source;
    }

    function markHtmlAudioCompletion(requestId) {
      audio?.addEventListener?.("ended", () => emit("completed", "", requestId), { once: true });
    }

    function markStreamCompletion(source, requestId) {
      if (!source) {
        emit("completed", "", requestId);
        return;
      }
      if (source.__ttsEnded) {
        emit("completed", "", requestId);
        return;
      }
      source.onended = () => {
        source.__ttsEnded = true;
        emit("completed", "", requestId);
      };
    }

    async function playNonStreaming(request) {
      const requestId = request.requestId;
      const response = await fetchImpl("/api/tts/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: abortController.signal,
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "tts_unavailable");
      if (!shouldApplyTtsResult({
        activeRequestId,
        resultRequestId: result.requestId,
        stopped,
      })) return false;
      const bytes = decodeBase64(result.audio?.base64);
      if (!bytes || bytes.byteLength > MAX_AUDIO_BYTES) throw new Error("tts_audio_invalid");
      objectUrl = URLImpl.createObjectURL(new Blob([bytes], { type: result.audio.mimeType }));
      audio = new AudioClass(objectUrl);
      markHtmlAudioCompletion(requestId);
      await audio.play();
      emit("playing", "", requestId);
      return true;
    }

    async function playStreaming(request) {
      const requestId = request.requestId;
      const response = await fetchImpl("/api/tts/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: abortController.signal,
      });
      if (!response.ok || !response.body?.getReader) {
        let result = {};
        try { result = await response.json(); } catch {}
        throw new Error(result.error || "tts_unavailable");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = "";
      let expectedSequence = 0;
      let sampleRate = 0;
      let seenStart = false;
      let seenTerminal = false;
      let lastSource = null;
      let terminalError = "";
      const handleLine = (line) => {
        if (!line.trim()) return;
        let event;
        try {
          event = JSON.parse(line);
        } catch {
          throw new Error("tts_worker_response_invalid");
        }
        if (seenTerminal) throw new Error("tts_stream_terminal_invalid");
        const validation = validateTtsStreamEvent(event, {
          activeRequestId: requestId,
          expectedSequence,
        });
        if (!validation.ok || stopped || activeRequestId !== requestId) {
          throw new Error(validation.error || "tts_stopped");
        }
        if (event.type === "start") {
          if (seenStart) throw new Error("tts_stream_start_invalid");
          seenStart = true;
          sampleRate = event.sampleRate;
        } else if (event.type === "audio") {
          if (!seenStart) throw new Error("tts_stream_start_missing");
          totalStreamBytes += validation.bytes.byteLength;
          if (totalStreamBytes > MAX_AUDIO_BYTES) throw new Error("tts_audio_too_large");
          replayChunks.push(validation.bytes);
          replaySampleRate = sampleRate;
          lastSource = schedulePcm(validation.bytes, sampleRate);
          expectedSequence += 1;
          emit("playing", "", requestId);
        } else if (event.type === "error") {
          seenTerminal = true;
          terminalError = event.error || "tts_worker_failed";
        } else if (event.type === "done") {
          if (!seenStart) throw new Error("tts_stream_start_missing");
          seenTerminal = true;
        }
      };
      while (true) {
        const { value, done } = await reader.read();
        pending += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = pending.split("\n");
        pending = lines.pop() || "";
        lines.forEach(handleLine);
        if (done) break;
      }
      if (pending.trim()) handleLine(pending);
      if (!seenTerminal) throw new Error("tts_stream_incomplete");
      if (terminalError) throw new Error(terminalError);
      markStreamCompletion(lastSource, requestId);
      return true;
    }

    async function play({
      requestId,
      text,
      voice = "default",
      language = "ja",
      supportsStreaming = false,
    }) {
      stop({ clearReplay: true });
      activeRequestId = String(requestId || "");
      stopped = false;
      cancelledRequestIds.delete(activeRequestId);
      abortController = new AbortController();
      totalStreamBytes = 0;
      replayRequest = { requestId: activeRequestId, text: normalizeTtsText(text), voice, language, supportsStreaming };
      if (!replayRequest.text) throw new Error("tts_text_required");
      const currentRequestId = activeRequestId;
      emit("preparing", "", currentRequestId);
      try {
        return supportsStreaming
          ? await playStreaming(replayRequest)
          : await playNonStreaming(replayRequest);
      } catch (error) {
        if (error?.name !== "AbortError" && !stopped && activeRequestId === currentRequestId) {
          stopped = true;
          abortController?.abort();
          abortController = null;
          releasePlayback({ clearReplay: true });
          sendCancel(currentRequestId);
          emit("error", error?.message || "tts_error", currentRequestId);
        }
        throw error;
      }
    }

    async function replay() {
      if (!replayRequest) return false;
      if (audio) {
        stopped = false;
        audio.currentTime = 0;
        markHtmlAudioCompletion(activeRequestId);
        await audio.play();
        emit("playing", "", activeRequestId);
        return true;
      }
      if (replayChunks.length && replaySampleRate) {
        releasePlayback();
        stopped = false;
        let lastSource = null;
        replayChunks.forEach((chunk) => {
          lastSource = schedulePcm(chunk, replaySampleRate);
        });
        markStreamCompletion(lastSource, activeRequestId);
        emit("playing", "", activeRequestId);
        return true;
      }
      return play(replayRequest);
    }

    function dispose() {
      stop({ clearReplay: true });
      activeRequestId = "";
    }

    return { play, stop, replay, dispose };
  }

  window.GEMMA_TTS = {
    createTtsController,
    defaultTtsSettings,
    normalizeTtsText,
    shouldApplyTtsResult,
    validateTtsStreamEvent,
  };
})();

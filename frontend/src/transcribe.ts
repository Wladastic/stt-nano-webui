import { getRecordedBlob, isRecording, startRecording, stopRecording } from "./recorder";

const $ = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;

export function initTranscribe(): void {
  const btn = $<HTMLButtonElement>("btn-transcribe");
  const copyBtn = $<HTMLButtonElement>("btn-copy-transcription");
  const quickBtn = $<HTMLButtonElement>("btn-quick-record-copy");
  btn.addEventListener("click", run);
  copyBtn.addEventListener("click", copyTranscription);
  quickBtn.addEventListener("click", toggleQuickRecordCopy);
}

async function copyTranscription(): Promise<boolean> {
  const copyBtn = $<HTMLButtonElement>("btn-copy-transcription");
  const outputText = $<HTMLTextAreaElement>("output-text");
  const text = outputText.value;

  if (!text) {
    copyBtn.textContent = "Nothing to copy";
    window.setTimeout(() => {
      copyBtn.textContent = "Copy";
    }, 1200);
    return false;
  }

  try {
    await navigator.clipboard.writeText(text);
    copyBtn.textContent = "Copied";
  } catch {
    outputText.focus();
    outputText.select();
    document.execCommand("copy");
    copyBtn.textContent = "Copied";
  }

  window.setTimeout(() => {
    copyBtn.textContent = "Copy";
  }, 1200);
  return true;
}

async function toggleQuickRecordCopy(): Promise<void> {
  const quickBtn = $<HTMLButtonElement>("btn-quick-record-copy");
  const outputText = $<HTMLTextAreaElement>("output-text");

  if (!isRecording()) {
    try {
      await startRecording();
      quickBtn.textContent = "Stop, Transcribe & Copy";
      quickBtn.classList.add("recording");
      outputText.value = "";
    } catch (err) {
      outputText.value = `Microphone error: ${err}`;
    }
    return;
  }

  quickBtn.disabled = true;
  quickBtn.textContent = "Stopping…";
  try {
    await stopRecording();
    quickBtn.textContent = "Transcribing…";
    const ok = await run({ copyAfter: true, preferRecorded: true });
    quickBtn.textContent = ok ? "Copied" : "Record, Transcribe & Copy";
    window.setTimeout(() => {
      quickBtn.textContent = "Record, Transcribe & Copy";
    }, ok ? 1200 : 0);
  } catch (err) {
    outputText.value = `Recording error: ${err}`;
    quickBtn.textContent = "Record, Transcribe & Copy";
  } finally {
    quickBtn.disabled = false;
    quickBtn.classList.remove("recording");
  }
}

async function run(options: { copyAfter?: boolean; preferRecorded?: boolean } = {}): Promise<boolean> {
  const btn = $<HTMLButtonElement>("btn-transcribe");
  const outputText = $<HTMLTextAreaElement>("output-text");
  const outputSegments = $<HTMLTextAreaElement>("output-segments");

  // Determine audio source: recorded blob or uploaded file
  const uploadInput = $<HTMLInputElement>("audio-upload");
  const recordedBlob = getRecordedBlob();
  const uploadedFile = uploadInput.files?.[0] ?? null;

  if (!recordedBlob && (!uploadedFile || options.preferRecorded)) {
    outputText.value = "No audio provided. Please record or upload an audio file.";
    return false;
  }

  const model = ($<HTMLSelectElement>("model-select")).value;
  const language = ($<HTMLInputElement>("language-input")).value.trim();
  const responseFormat = ($<HTMLSelectElement>("format-select")).value;

  const formData = new FormData();

  if (recordedBlob) {
    formData.append("file", recordedBlob, "recording.webm");
  } else if (uploadedFile) {
    formData.append("file", uploadedFile);
  }

  formData.append("model", model);
  formData.append("response_format", responseFormat);
  if (language) formData.append("language", language);

  btn.disabled = true;
  btn.textContent = "Transcribing…";
  outputText.value = "";
  outputSegments.value = "";

  try {
    const res = await fetch("/v1/audio/transcriptions", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const errText = await res.text();
      outputText.value = `Error ${res.status}: ${errText}`;
      return false;
    }

    if (
      responseFormat === "text" ||
      responseFormat === "srt" ||
      responseFormat === "vtt"
    ) {
      outputText.value = await res.text();
      if (options.copyAfter) await copyTranscription();
      return true;
    }

    const result = await res.json();
    outputText.value = result.text ?? "";

    if (responseFormat === "verbose_json" && result.segments) {
      outputSegments.value = result.segments
        .map(
          (seg: { start: number; end: number; text: string }) =>
            `[${seg.start.toFixed(1)}s - ${seg.end.toFixed(1)}s] ${seg.text}`
        )
        .join("\n");
    }
    if (options.copyAfter) await copyTranscription();
    return true;
  } catch (err) {
    outputText.value = `Connection error: ${err}`;
    return false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Transcribe";
  }
}

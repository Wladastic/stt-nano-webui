import { getRecordedBlob } from "./recorder";

const $ = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;

export function initTranscribe(): void {
  const btn = $<HTMLButtonElement>("btn-transcribe");
  const copyBtn = $<HTMLButtonElement>("btn-copy-transcription");
  btn.addEventListener("click", run);
  copyBtn.addEventListener("click", copyTranscription);
}

async function copyTranscription(): Promise<void> {
  const copyBtn = $<HTMLButtonElement>("btn-copy-transcription");
  const outputText = $<HTMLTextAreaElement>("output-text");
  const text = outputText.value;

  if (!text) {
    copyBtn.textContent = "Nothing to copy";
    window.setTimeout(() => {
      copyBtn.textContent = "Copy";
    }, 1200);
    return;
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
}

async function run(): Promise<void> {
  const btn = $<HTMLButtonElement>("btn-transcribe");
  const outputText = $<HTMLTextAreaElement>("output-text");
  const outputSegments = $<HTMLTextAreaElement>("output-segments");

  // Determine audio source: recorded blob or uploaded file
  const uploadInput = $<HTMLInputElement>("audio-upload");
  const recordedBlob = getRecordedBlob();
  const uploadedFile = uploadInput.files?.[0] ?? null;

  if (!recordedBlob && !uploadedFile) {
    outputText.value = "No audio provided. Please record or upload an audio file.";
    return;
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
      return;
    }

    if (
      responseFormat === "text" ||
      responseFormat === "srt" ||
      responseFormat === "vtt"
    ) {
      outputText.value = await res.text();
      return;
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
  } catch (err) {
    outputText.value = `Connection error: ${err}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Transcribe";
  }
}

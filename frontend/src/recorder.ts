const $ = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;

let mediaRecorder: MediaRecorder | null = null;
let chunks: Blob[] = [];
let recordingStart = 0;
let timerInterval: ReturnType<typeof setInterval> | null = null;
let recordedBlob: Blob | null = null;

export function getRecordedBlob(): Blob | null {
  return recordedBlob;
}

export function clearRecording(): void {
  recordedBlob = null;
  const preview = $<HTMLAudioElement>("audio-preview");
  preview.hidden = true;
  preview.src = "";
}

function formatTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function initRecorder(): void {
  const btn = $<HTMLButtonElement>("btn-record");
  const timeEl = $<HTMLSpanElement>("record-time");
  const preview = $<HTMLAudioElement>("audio-preview");

  btn.addEventListener("click", async () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      // Stop
      mediaRecorder.stop();
      btn.textContent = "Record";
      btn.classList.remove("recording");
      if (timerInterval) clearInterval(timerInterval);
      timeEl.textContent = "";
      return;
    }

    // Start
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        recordedBlob = new Blob(chunks, { type: mediaRecorder!.mimeType });
        preview.src = URL.createObjectURL(recordedBlob);
        preview.hidden = false;
      };

      mediaRecorder.start();
      recordingStart = Date.now();
      btn.textContent = "Stop";
      btn.classList.add("recording");

      timerInterval = setInterval(() => {
        timeEl.textContent = formatTime(Date.now() - recordingStart);
      }, 200);
    } catch (err) {
      alert("Microphone access denied or unavailable.");
      console.error(err);
    }
  });
}

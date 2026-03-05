import { initRecorder } from "./recorder";
import { initTranscribe } from "./transcribe";
import { initStatus, loadModelList } from "./status";
import { initDocs } from "./docs";
import "./style.css";

function initTabs(): void {
  const buttons = document.querySelectorAll<HTMLButtonElement>(".tab");
  const panels = document.querySelectorAll<HTMLElement>(".tab-content");

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab!;
      buttons.forEach((b) => b.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${target}`)!.classList.add("active");
    });
  });
}

async function main(): Promise<void> {
  initTabs();
  initRecorder();
  initTranscribe();
  initStatus();
  await loadModelList();
  await initDocs();
}

main();

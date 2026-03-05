const $ = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;

interface ModelInfo {
  status: string;
  ttl_remaining?: number;
  ttl_total?: number;
}

interface StatusResponse {
  ttl_seconds: number;
  models: Record<string, ModelInfo>;
  vram?: { total_mb: number; allocated_mb: number };
}

interface ModelEntry {
  id: string;
  owned_by: string;
}

async function fetchModels(): Promise<string[]> {
  try {
    const res = await fetch("/v1/models");
    if (!res.ok) return [];
    const data = await res.json();
    return (data.data as ModelEntry[])
      .filter((m) => m.owned_by !== "openai")
      .map((m) => m.id);
  } catch {
    return [];
  }
}

function populateSelect(el: HTMLSelectElement, models: string[]): void {
  const current = el.value;
  el.innerHTML = models.map((m) => `<option value="${m}">${m}</option>`).join("");
  if (models.includes(current)) el.value = current;
}

const DEFAULT_MODEL = "parakeet-onnx-int8";

export async function loadModelList(): Promise<void> {
  const models = await fetchModels();
  const mainSelect = $<HTMLSelectElement>("model-select");
  populateSelect(mainSelect, models);
  if (models.includes(DEFAULT_MODEL)) mainSelect.value = DEFAULT_MODEL;
  populateSelect($<HTMLSelectElement>("status-model-select"), models);
}

function renderStatus(data: StatusResponse): void {
  const vramEl = $("vram-bar");
  const tableEl = $("model-table");

  // VRAM bar
  if (data.vram) {
    const { total_mb, allocated_mb } = data.vram;
    const pct = total_mb > 0 ? Math.min(100, Math.round((allocated_mb / total_mb) * 100)) : 0;
    const color = pct < 60 ? "#4caf50" : pct < 85 ? "#ff9800" : "#f44336";
    vramEl.innerHTML = `
      <h3>VRAM: ${allocated_mb} MB / ${total_mb} MB (${pct}%)</h3>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${color}"></div></div>
    `;
  } else {
    vramEl.innerHTML = "";
  }

  // Model table
  const rows = Object.entries(data.models)
    .map(([name, info]) => {
      let badge: string;
      let ttl: string;
      if (info.status === "loaded") {
        badge = `<span class="badge loaded">LOADED</span>`;
        ttl = `${info.ttl_remaining ?? 0}s / ${data.ttl_seconds}s`;
      } else if (info.status === "loading") {
        badge = `<span class="badge loading">LOADING…</span>`;
        ttl = "-";
      } else {
        badge = `<span class="badge unloaded">unloaded</span>`;
        ttl = "-";
      }
      return `<tr><td>${name}</td><td>${badge}</td><td>${ttl}</td></tr>`;
    })
    .join("");

  tableEl.innerHTML = `
    <table>
      <thead><tr><th>Model</th><th>Status</th><th>TTL</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function refreshStatus(): Promise<void> {
  try {
    const res = await fetch("/v1/status");
    if (res.ok) renderStatus(await res.json());
  } catch {
    $("model-table").innerHTML = "<p>Backend unavailable</p>";
  }
}

export function initStatus(): void {
  // Model management buttons
  $<HTMLButtonElement>("btn-load").addEventListener("click", async () => {
    const model = $<HTMLSelectElement>("status-model-select").value;
    await fetch(`/v1/models/${model}/load`, { method: "POST" });
    await refreshStatus();
  });

  $<HTMLButtonElement>("btn-unload").addEventListener("click", async () => {
    const model = $<HTMLSelectElement>("status-model-select").value;
    await fetch(`/v1/models/${model}/unload`, { method: "POST" });
    await refreshStatus();
  });

  $<HTMLButtonElement>("btn-flush").addEventListener("click", async () => {
    await fetch("/v1/models/flush", { method: "POST" });
    await refreshStatus();
  });

  // Poll status every 5s
  refreshStatus();
  setInterval(refreshStatus, 5000);
}

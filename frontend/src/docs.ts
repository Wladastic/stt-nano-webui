type ModelEntry = { id: string; description: string; owned_by: string };

export async function initDocs(): Promise<void> {
  const origin = window.location.origin;
  document.querySelectorAll<HTMLElement>(".docs-host").forEach((el) => {
    el.textContent = origin;
  });
  const originEl = document.getElementById("docs-origin");
  if (originEl) originEl.textContent = origin;
  const baseUrlEl = document.getElementById("docs-base-url");
  if (baseUrlEl) baseUrlEl.textContent = origin;

  try {
    const [modelsRes, statusRes] = await Promise.all([
      fetch("/v1/models"),
      fetch("/v1/status"),
    ]);
    const models: { data: ModelEntry[] } = await modelsRes.json();
    const status = await statusRes.json();

    const ttlEl = document.getElementById("docs-ttl");
    if (ttlEl) ttlEl.textContent = String(status.ttl_seconds ?? "?");

    const listEl = document.getElementById("docs-model-list");
    if (listEl) {
      const rows = models.data
        .map(
          (m) =>
            `<tr><td><code>${m.id}</code></td><td>${m.owned_by}</td><td>${m.description}</td></tr>`,
        )
        .join("");
      listEl.innerHTML = `<table class="docs-table"><thead><tr><th>id</th><th>owned_by</th><th>description</th></tr></thead><tbody>${rows}</tbody></table>`;
    }
  } catch (e) {
    console.warn("docs: failed to fetch model list", e);
  }
}

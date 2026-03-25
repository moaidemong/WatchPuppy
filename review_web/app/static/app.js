const state = {
  offset: 0,
  limit: 100,
  total: 0,
  translations: {},
  epochOptions: [],
  reviewStatusOptions: [],
  reviewLabelOptions: [],
  currentEpoch: "RUN1",
};

function restoreStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  state.offset = Number(params.get("offset") || 0);
  state.limit = Number(params.get("limit") || 100);

  document.getElementById("camera-filter").value = params.get("camera_id") || "";
  document.getElementById("epoch-filter").value = params.get("epoch") || "";
  document.getElementById("new-filter").value = params.get("new_only") || "";
  document.getElementById("q-filter").value = params.get("q") || "";
}

function applyFilterParamsFromUrl() {
  const params = new URLSearchParams(window.location.search);
  document.getElementById("epoch-filter").value = params.get("epoch") || "";
  document.getElementById("status-filter").value = params.get("review_status") || "";
  document.getElementById("new-filter").value = params.get("new_only") || "";
  document.getElementById("label-filter").value = params.get("review_label") || "";
  document.getElementById("limit-select").value = String(state.limit);
}

function syncUrlState() {
  const query = currentQuery();
  const url = query.toString() ? `/?${query.toString()}` : "/";
  window.history.replaceState({}, "", url);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function t(key) {
  return state.translations[key] || key || "";
}

function buildOptions(select, options, includeEmpty = true) {
  const current = select.value;
  select.innerHTML = "";
  if (includeEmpty) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "전체";
    select.appendChild(empty);
  }
  for (const option of options) {
    const el = document.createElement("option");
    el.value = option;
    el.textContent = t(option);
    select.appendChild(el);
  }
  select.value = current;
}

async function loadMeta() {
  const payload = await fetchJson("/api/meta");
  state.translations = payload.translations || {};
  state.epochOptions = payload.epoch_options || [];
  state.reviewStatusOptions = payload.review_status_options || [];
  state.reviewLabelOptions = payload.review_label_options || [];
  state.currentEpoch = payload.current_epoch || "RUN1";
  buildOptions(document.getElementById("epoch-filter"), state.epochOptions);
  buildOptions(document.getElementById("status-filter"), state.reviewStatusOptions);
  buildOptions(document.getElementById("label-filter"), state.reviewLabelOptions);
}

function currentQuery() {
  const params = new URLSearchParams({
    offset: String(state.offset),
    limit: String(state.limit),
  });
  const cameraId = document.getElementById("camera-filter").value;
  const epoch = document.getElementById("epoch-filter").value;
  const newOnly = document.getElementById("new-filter").value;
  const reviewStatus = document.getElementById("status-filter").value;
  const reviewLabel = document.getElementById("label-filter").value;
  const q = document.getElementById("q-filter").value;

  if (cameraId) params.set("camera_id", cameraId);
  if (epoch) params.set("epoch", epoch);
  if (newOnly) params.set("new_only", newOnly);
  if (reviewStatus) params.set("review_status", reviewStatus);
  if (reviewLabel) params.set("review_label", reviewLabel);
  if (q) params.set("q", q);
  return params;
}

async function loadRows() {
  syncUrlState();
  const query = currentQuery();
  const payload = await fetchJson(`/api/reviews?${query.toString()}`);
  state.total = payload.total;
  const tbody = document.querySelector("#review-table tbody");
  tbody.innerHTML = "";
  const returnQuery = encodeURIComponent(`/?${query.toString()}`);
  payload.items.forEach((item, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${state.offset + index + 1}</td>
      <td>${item.event_id}</td>
      <td>${item.camera_id.toUpperCase()}</td>
      <td><a href="/media/snapshot/${item.event_id}" target="_blank">열기</a></td>
      <td><a href="/view/clip/${item.event_id}?return=${returnQuery}" target="_blank">열기</a></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
    `;

    const classifierCell = tr.children[5];
    const labelCell = tr.children[6];
    const statusCell = tr.children[7];
    const notesCell = tr.children[8];
    const actionCell = tr.children[9];

    const classifierLabel = item.classifier_label || "-";
    const classifierScore =
      item.classifier_score && Number(item.classifier_score) > 0
        ? ` (${Number(item.classifier_score).toFixed(3)})`
        : "";
    classifierCell.textContent = `${t(classifierLabel)}${classifierScore}`;

    const labelSelect = document.createElement("select");
    labelSelect.appendChild(new Option("", ""));
    for (const option of state.reviewLabelOptions) {
      labelSelect.appendChild(new Option(t(option), option));
    }
    labelSelect.value = item.review_label || "";
    labelCell.appendChild(labelSelect);

    const statusSelect = document.createElement("select");
    buildOptions(statusSelect, state.reviewStatusOptions, false);
    statusSelect.value = item.review_status || "pending";
    statusCell.appendChild(statusSelect);

    const notes = document.createElement("textarea");
    notes.value = item.review_notes || "";
    notesCell.appendChild(notes);

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = t("save");
    saveBtn.className = "save-btn";
    saveBtn.addEventListener("click", async () => {
      saveBtn.classList.remove("saved", "conflict");
      try {
        const result = await fetchJson(`/api/reviews/${item.event_id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            version: item.version,
            review_status: statusSelect.value,
            review_label: labelSelect.value,
            review_notes: notes.value,
          }),
        });
        item.version = result.item.version;
        saveBtn.classList.add("saved");
      } catch (error) {
        saveBtn.classList.add("conflict");
        alert(`저장 실패: ${error.message}`);
      }
    });
    actionCell.appendChild(saveBtn);

    tbody.appendChild(tr);
  });

  const start = payload.total === 0 ? 0 : state.offset + 1;
  const end = Math.min(state.offset + state.limit, payload.total);
  const page = payload.total === 0 ? 0 : Math.floor(state.offset / state.limit) + 1;
  const pageCount = payload.total === 0 ? 0 : Math.ceil(payload.total / state.limit);
  document.getElementById("summary-text").textContent = `총 ${payload.total}건`;
  document.getElementById("page-text").textContent = `${start}-${end} / ${payload.total} · ${page}/${pageCount} 페이지`;
  document.getElementById("first-page-btn").disabled = state.offset <= 0;
  document.getElementById("prev-page-btn").disabled = state.offset <= 0;
  document.getElementById("next-page-btn").disabled = state.offset + state.limit >= payload.total;
  document.getElementById("last-page-btn").disabled = state.offset + state.limit >= payload.total;
}

async function syncRows() {
  await fetchJson("/api/sync", { method: "POST" });
  await loadRows();
}

document.addEventListener("DOMContentLoaded", async () => {
  restoreStateFromUrl();
  await loadMeta();
  applyFilterParamsFromUrl();
  await loadRows();

  document.getElementById("reload-btn").addEventListener("click", () => {
    state.offset = 0;
    loadRows();
  });
  document.getElementById("sync-btn").addEventListener("click", syncRows);
  document.getElementById("limit-select").addEventListener("change", async (event) => {
    state.limit = Number(event.target.value || 100);
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("camera-filter").addEventListener("change", () => {
    state.offset = 0;
    loadRows();
  });
  document.getElementById("epoch-filter").addEventListener("change", () => {
    state.offset = 0;
    loadRows();
  });
  document.getElementById("new-filter").addEventListener("change", () => {
    state.offset = 0;
    loadRows();
  });
  document.getElementById("status-filter").addEventListener("change", () => {
    state.offset = 0;
    loadRows();
  });
  document.getElementById("label-filter").addEventListener("change", () => {
    state.offset = 0;
    loadRows();
  });
  document.getElementById("q-filter").addEventListener("change", () => {
    state.offset = 0;
    loadRows();
  });
  document.getElementById("prev-page-btn").addEventListener("click", async () => {
    state.offset = Math.max(0, state.offset - state.limit);
    await loadRows();
  });
  document.getElementById("first-page-btn").addEventListener("click", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("next-page-btn").addEventListener("click", async () => {
    if (state.offset + state.limit < state.total) {
      state.offset += state.limit;
      await loadRows();
    }
  });
  document.getElementById("last-page-btn").addEventListener("click", async () => {
    if (state.total > 0) {
      state.offset = Math.floor((state.total - 1) / state.limit) * state.limit;
      await loadRows();
    }
  });
});

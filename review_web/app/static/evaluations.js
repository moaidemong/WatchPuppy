const state = {
  offset: 0,
  limit: 100,
  total: 0,
  translations: {},
  evaluationRunOptions: [],
  evaluationPredictedLabelOptions: [],
  evaluationClassifierLabelOptions: [],
  evaluationReviewLabelOptions: [],
  evaluationReviewStatusOptions: [],
};

function restoreStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  state.offset = Number(params.get("offset") || 0);
  state.limit = Number(params.get("limit") || 100);
  document.getElementById("predicted-filter").value = params.get("predicted_label") || "";
  document.getElementById("classifier-filter").value = params.get("classifier_label") || "";
  document.getElementById("review-label-filter").value = params.get("review_label") || "";
  document.getElementById("review-status-filter").value = params.get("review_status") || "";
  document.getElementById("q-filter").value = params.get("q") || "";
}

function currentQuery() {
  const params = new URLSearchParams({
    offset: String(state.offset),
    limit: String(state.limit),
  });
  const runName = document.getElementById("run-filter").value;
  const predictedLabel = document.getElementById("predicted-filter").value;
  const classifierLabel = document.getElementById("classifier-filter").value;
  const reviewLabel = document.getElementById("review-label-filter").value;
  const reviewStatus = document.getElementById("review-status-filter").value;
  const q = document.getElementById("q-filter").value;
  if (runName) params.set("run_name", runName);
  if (predictedLabel) params.set("predicted_label", predictedLabel);
  if (classifierLabel) params.set("classifier_label", classifierLabel);
  if (reviewLabel) params.set("review_label", reviewLabel);
  if (reviewStatus) params.set("review_status", reviewStatus);
  if (q) params.set("q", q);
  return params;
}

function syncUrlState() {
  const query = currentQuery();
  const url = query.toString() ? `/evaluations?${query.toString()}` : "/evaluations";
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

function buildOptions(select, options, includeEmpty = false) {
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
  const selectable = includeEmpty ? ["", ...options] : options;
  select.value = current && selectable.includes(current) ? current : (includeEmpty ? "" : options[0] || "");
}

async function loadMeta() {
  const payload = await fetchJson("/api/meta");
  state.translations = payload.translations || {};
  state.evaluationRunOptions = payload.evaluation_run_options || [];
  state.evaluationPredictedLabelOptions = payload.evaluation_predicted_label_options || [];
  state.evaluationClassifierLabelOptions = payload.evaluation_classifier_label_options || [];
  state.evaluationReviewLabelOptions = payload.evaluation_review_label_options || [];
  state.evaluationReviewStatusOptions = payload.evaluation_review_status_options || [];
  buildOptions(document.getElementById("run-filter"), state.evaluationRunOptions);
  buildOptions(document.getElementById("predicted-filter"), state.evaluationPredictedLabelOptions, true);
  buildOptions(document.getElementById("classifier-filter"), state.evaluationClassifierLabelOptions, true);
  buildOptions(document.getElementById("review-label-filter"), state.evaluationReviewLabelOptions, true);
  buildOptions(document.getElementById("review-status-filter"), state.evaluationReviewStatusOptions, true);
  const params = new URLSearchParams(window.location.search);
  const runName = params.get("run_name");
  if (runName && state.evaluationRunOptions.includes(runName)) {
    document.getElementById("run-filter").value = runName;
  }
  document.getElementById("predicted-filter").value = params.get("predicted_label") || "";
  document.getElementById("classifier-filter").value = params.get("classifier_label") || "";
  document.getElementById("review-label-filter").value = params.get("review_label") || "";
  document.getElementById("review-status-filter").value = params.get("review_status") || "";
  document.getElementById("limit-select").value = String(state.limit);
}

async function loadRows() {
  syncUrlState();
  const runName = document.getElementById("run-filter").value;
  if (!runName) {
    document.querySelector("#evaluation-table tbody").innerHTML = "";
    document.getElementById("summary-text").textContent = "평가 배치가 없습니다";
    document.getElementById("page-text").textContent = "";
    return;
  }

  const query = currentQuery();
  const payload = await fetchJson(`/api/evaluations?${query.toString()}`);
  state.total = payload.total;
  const tbody = document.querySelector("#evaluation-table tbody");
  tbody.innerHTML = "";
  const returnQuery = encodeURIComponent(`/evaluations?${query.toString()}`);

  payload.items.forEach((item, index) => {
    const reviewKey = encodeURIComponent(item.review_key || `${item.source_epoch || ""}::${item.event_id}`);
    const tr = document.createElement("tr");
    const classifierLabel = item.classifier_label || "-";
    const classifierScore =
      item.classifier_score && Number(item.classifier_score) > 0
        ? ` (${Number(item.classifier_score).toFixed(3)})`
        : "";
    tr.innerHTML = `
      <td>${state.offset + index + 1}</td>
      <td>${item.event_id}</td>
      <td>${item.source_epoch || "-"}</td>
      <td>${(item.camera_id || "").toUpperCase()}</td>
      <td><a href="/media/snapshot/${reviewKey}" target="_blank">열기</a></td>
      <td><a href="/view/clip/${reviewKey}?return=${returnQuery}&event_id=${encodeURIComponent(item.event_id)}" target="_blank">열기</a></td>
      <td>${t(item.predicted_label || "-")}</td>
      <td>${t(classifierLabel)}${classifierScore}</td>
      <td>${t(item.review_label || "-")}</td>
      <td>${t(item.review_status || "-")}</td>
    `;
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

document.addEventListener("DOMContentLoaded", async () => {
  restoreStateFromUrl();
  await loadMeta();
  await loadRows();

  document.getElementById("reload-btn").addEventListener("click", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("run-filter").addEventListener("change", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("predicted-filter").addEventListener("change", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("classifier-filter").addEventListener("change", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("review-label-filter").addEventListener("change", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("review-status-filter").addEventListener("change", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("q-filter").addEventListener("change", async () => {
    state.offset = 0;
    await loadRows();
  });
  document.getElementById("limit-select").addEventListener("change", async (event) => {
    state.limit = Number(event.target.value || 100);
    state.offset = 0;
    await loadRows();
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

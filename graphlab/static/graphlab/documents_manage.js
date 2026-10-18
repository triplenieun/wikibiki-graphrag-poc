/* Document, source and model text are rendered as text, never HTML. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { documents: [], total: 0, offset: 0, limit: 20, query: "", busy: false, deleting: false, detail: null, deleteItem: null, refreshPending: false };
  const relationLabels = { DESCRIBES: "문서 → 서비스 · 설명", DEPENDS_ON: "서비스 → 서비스 · 의존", OWNED_BY: "서비스 → 팀 · 담당" };
  const make = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  };
  const endpoint = (id, operation = "") => `/api/documents/${encodeURIComponent(id)}/${operation ? `${operation}/` : ""}`;
  const editable = (item) => item.can_manage === true;
  function report(message, busy = false) { $("management-status").textContent = message; $("management-status").dataset.state = busy ? "busy" : "ready"; }
  function error(message, target = "management-error") { $(target).textContent = message || ""; $(target).hidden = !message; }
  function setBusy(value) {
    state.busy = value;
    $("document-list").setAttribute("aria-busy", String(value));
    $("refresh-documents").disabled = value;
    $("search-documents").querySelector("button").disabled = value;
    $("previous-page").disabled = value || state.offset === 0;
    $("next-page").disabled = value || state.offset + state.documents.length >= state.total;
    $("document-list").querySelectorAll("button").forEach((button) => { button.disabled = value; });
    if (!value && state.refreshPending && !state.deleting) { state.refreshPending = false; queueMicrotask(() => loadList()); }
  }
  async function request(url, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    const headers = { Accept: "application/json" };
    const options = { method: payload ? "POST" : "GET", credentials: "same-origin", headers, signal: controller.signal };
    if (payload) {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = document.querySelector("input[name=csrfmiddlewaretoken]").value;
      options.body = JSON.stringify(payload);
    }
    try {
      const response = await fetch(url, options);
      let data;
      try { data = await response.json(); } catch { throw new Error("서버 응답을 읽지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요."); }
      if (!response.ok) { const failure = new Error(data.error || `요청을 처리하지 못했습니다 (${response.status}).`); failure.status = response.status; throw failure; }
      return data;
    } catch (failure) {
      if (failure.name === "AbortError") throw new Error("응답 시간이 길어 요청을 종료했습니다. 삭제를 요청했다면 같은 요청을 다시 시도하거나 목록을 새로고침해 결과를 확인하세요.");
      if (failure instanceof TypeError) throw new Error("서버에 연결하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요.");
      throw failure;
    } finally { clearTimeout(timeout); }
  }
  function formatDate(value) {
    if (!value) return "수정 시각 없음";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "수정 시각 없음" : `${date.toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })} 수정`;
  }
  function button(label, className, action) { const node = make("button", className, label); node.type = "button"; node.addEventListener("click", action); return node; }
  function editLink(item, className = "doc-secondary") {
    const link = make("a", className, "수정"); link.href = `/documents/?edit=${encodeURIComponent(item.id)}`; link.setAttribute("aria-label", `${item.title} 문서 수정`); return link;
  }
  function renderList() {
    $("document-list").replaceChildren();
    $("library-count").textContent = `${state.total.toLocaleString("ko-KR")}개`;
    $("library-empty").hidden = state.documents.length > 0;
    $("empty-title").textContent = state.query ? "일치하는 문서가 없습니다." : "등록한 문서가 없습니다.";
    $("empty-description").textContent = state.query ? "제목, 출처 또는 문서 ID의 다른 단어로 검색해 보세요." : "첫 문서를 등록하고 서비스와 팀을 연결해 보세요.";
    for (const item of state.documents) {
      const card = make("article", "library-document");
      const content = make("div", "library-document-content");
      const badges = make("div", "document-badges");
      badges.append(make("span", `document-kind${editable(item) ? "" : " example"}`, editable(item) ? "등록 문서" : "예제 · 읽기 전용"), make("span", "document-relations", `관계 ${item.relation_count || 0}개`));
      content.append(badges, make("h3", "", item.title), make("p", "document-source", item.source || "출처 미입력"), make("p", "document-updated", formatDate(item.updated_at || item.created_at)));
      const actions = make("div", "library-actions");
      const view = button("상세 보기", "doc-secondary", () => showDetail(item)); view.setAttribute("aria-label", `${item.title} 문서 상세 보기`); actions.append(view);
      if (editable(item)) {
        const remove = button("삭제", "doc-remove", () => showDelete(item)); remove.setAttribute("aria-label", `${item.title} 문서 삭제`);
        actions.append(editLink(item), remove);
      }
      card.append(content, actions);
      if (!editable(item)) card.append(make("p", "library-note", "설치 실습용 예제입니다. 직접 등록한 문서에서 수정·삭제를 사용할 수 있습니다."));
      $("document-list").append(card);
    }
    $("document-pagination").hidden = state.total <= state.limit;
    $("page-position").textContent = `${state.total ? state.offset + 1 : 0}–${Math.min(state.offset + state.documents.length, state.total)} / ${state.total}`;
  }
  async function loadList({ offset = state.offset, query = state.query, message = "" } = {}) {
    if (state.busy) return;
    error(""); setBusy(true); report("문서 목록을 불러오고 있습니다.", true);
    try {
      let data = await request(`/api/documents/?${new URLSearchParams({ q: query, offset: String(offset), limit: String(state.limit) })}`);
      if (!Array.isArray(data.documents) || !Number.isInteger(data.total)) throw new Error("문서 목록 응답 형식을 확인할 수 없습니다.");
      if (offset > 0 && !data.documents.length) { offset = Math.max(0, Math.floor(Math.max(0, data.total - 1) / state.limit) * state.limit); data = await request(`/api/documents/?${new URLSearchParams({ q: query, offset: String(offset), limit: String(state.limit) })}`); }
      state.documents = data.documents; state.total = data.total; state.offset = offset; state.query = query;
      renderList(); report(message || (query ? `‘${query}’ 검색 결과 ${data.total}개입니다.` : `문서 ${data.total}개를 불러왔습니다. 상세 보기에서 원문과 관계를 확인하세요.`));
    } catch (failure) { error(failure.message); report("문서 목록을 불러오지 못했습니다. 기존 목록은 유지됩니다."); }
    finally { setBusy(false); }
  }
  async function showDetail(item) {
    if (state.busy) return;
    error(""); setBusy(true); report("문서 원문과 관계를 불러오고 있습니다.", true);
    try {
      const data = await request(endpoint(item.id));
      if (!data.document || !Array.isArray(data.relations) || !Array.isArray(data.nodes)) throw new Error("문서 상세 응답 형식을 확인할 수 없습니다.");
      state.detail = { ...data.document, can_manage: data.document.can_manage ?? data.can_manage ?? item.can_manage };
      const names = new Map(data.nodes.map((node) => [node.id, node.name])); names.set(data.document.id, data.document.title);
      $("detail-title").textContent = data.document.title;
      $("detail-source").textContent = data.document.source || "출처 미입력";
      $("detail-id").textContent = data.document.id;
      $("detail-body").textContent = data.document.body;
      $("detail-relation-count").textContent = `${data.relations.length}개`;
      const warnings = [...(data.warnings || [])];
      if (!editable(state.detail)) warnings.push("설치 실습용 예제 문서로, 이 화면에서는 읽기만 가능합니다.");
      $("detail-warning").textContent = warnings.join("\n"); $("detail-warning").hidden = !warnings.length; error("", "detail-error");
      $("detail-relations").replaceChildren();
      for (const relation of data.relations) {
        const row = make("article", "detail-relation");
        row.append(make("span", "detail-relation-type", relationLabels[relation.type] || relation.type), make("p", "detail-relation-path", `${names.get(relation.source_id) || relation.source_id} → ${names.get(relation.target_id) || relation.target_id}`));
        row.append(make("p", "detail-evidence", relation.evidence ? `근거: ${relation.evidence}` : "실습 데이터의 연결입니다. 별도 인용문이 없습니다."));
        $("detail-relations").append(row);
      }
      if (!data.relations.length) $("detail-relations").append(make("p", "section-help", "이 문서에 저장된 관계가 없습니다."));
      $("edit-from-detail").href = `/documents/?edit=${encodeURIComponent(item.id)}`;
      $("edit-from-detail").hidden = !editable(state.detail); $("delete-from-detail").hidden = !editable(state.detail);
      $("document-detail").showModal(); report("문서 원문과 관계를 불러왔습니다.");
    } catch (failure) { error(failure.message); report("문서 상세 정보를 불러오지 못했습니다. 목록 새로고침 후 다시 확인해 주세요."); }
    finally { setBusy(false); }
  }
  function showDelete(item) {
    if (!editable(item) || state.deleting) return;
    state.deleteItem = item; $("delete-title").textContent = item.title; $("delete-confirmed").checked = false; $("confirm-delete").disabled = true;
    $("confirm-delete").textContent = "문서 삭제하기"; error("", "delete-error");
    $("delete-document").showModal();
  }
  function revisionChanged() { try { localStorage.setItem("graphlab-document-revision", `${Date.now()}-${Math.random()}`); } catch { /* Private browser storage can be unavailable. */ } }
  $("confirm-delete").addEventListener("click", async () => {
    if (state.deleting || !state.deleteItem || !$("delete-confirmed").checked) return;
    state.deleting = true; error("", "delete-error");
    $("confirm-delete").disabled = true; $("cancel-delete").disabled = true; $("delete-confirmed").disabled = true; $("confirm-delete").textContent = "삭제 중입니다…";
    try {
      const result = await request(endpoint(state.deleteItem.id, "delete"), { version: state.deleteItem.version });
      revisionChanged(); $("delete-document").close();
      await loadList({ message: result.message || "문서를 삭제했습니다. 문서와 정리된 관계가 GraphRAG 검색에 반영되었습니다." });
      $("management-warnings").textContent = (result.warnings || []).join("\n"); $("management-warnings").hidden = !(result.warnings || []).length;
      state.deleteItem = null; $("refresh-documents").focus();
    } catch (failure) { error(failure.status === 409 ? `${failure.message}\n다른 곳에서 문서가 변경되었을 수 있습니다. 취소 후 목록을 새로고침하고 최신 문서를 확인해 주세요.` : failure.message, "delete-error"); }
    finally {
      state.deleting = false; $("cancel-delete").disabled = false; $("delete-confirmed").disabled = false; $("confirm-delete").disabled = !$("delete-confirmed").checked; $("confirm-delete").textContent = "문서 삭제하기";
      if (state.refreshPending) { state.refreshPending = false; loadList(); }
    }
  });
  $("delete-confirmed").addEventListener("change", () => { $("confirm-delete").disabled = state.deleting || !$("delete-confirmed").checked; });
  $("cancel-delete").addEventListener("click", () => { if (!state.deleting) $("delete-document").close(); });
  $("delete-document").addEventListener("cancel", (event) => { if (state.deleting) event.preventDefault(); });
  $("close-detail").addEventListener("click", () => $("document-detail").close());
  $("delete-from-detail").addEventListener("click", () => { $("document-detail").close(); showDelete(state.detail); });
  $("refresh-documents").addEventListener("click", () => loadList());
  $("search-documents").addEventListener("submit", (event) => { event.preventDefault(); loadList({ offset: 0, query: $("document-search").value.trim() }); });
  $("previous-page").addEventListener("click", () => loadList({ offset: Math.max(0, state.offset - state.limit) }));
  $("next-page").addEventListener("click", () => loadList({ offset: state.offset + state.limit }));
  window.addEventListener("storage", (event) => { if (event.key === "graphlab-document-revision") { if (state.busy || state.deleting) state.refreshPending = true; else loadList(); } });
  window.addEventListener("pageshow", (event) => { if (event.persisted) loadList(); });
  loadList();
})();

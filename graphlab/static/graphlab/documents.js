/* Plain DOM rendering: document and model text is never interpreted as HTML. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const editId = new URLSearchParams(window.location.search).get("edit");
  const state = { catalog: [], ready: false, busy: false, blocked: false, preview: null, nodes: [], relations: [], saved: false, serial: 0, version: null };
  const kinds = { Service: "서비스", Team: "팀" };
  const relationTypes = { DESCRIBES: "설명 · 문서 → 서비스", DEPENDS_ON: "의존 · 서비스 → 서비스", OWNED_BY: "담당팀 · 서비스 → 팀" };
  const uid = () => `item-${++state.serial}`;
  const create = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  function option(value, label) { const node = create("option", "", label); node.value = value; return node; }
  function report(message, busy = false) { $("document-status").textContent = message; $("document-status").dataset.state = busy ? "busy" : "ready"; }
  function error(message) { $("document-error").textContent = message || ""; $("document-error").hidden = !message; if (!message) $("document-conflict-help").hidden = true; }
  function conflictHelp(failure) { if (editId && failure.status === 409) $("document-conflict-help").hidden = false; }
  function step(number) {
    ["input", "review", "save"].forEach((name, index) => {
      const element = $(`step-${name}`);
      element.classList.toggle("current", index === number - 1);
      element.classList.toggle("complete", index < number - 1);
      if (index === number - 1) element.setAttribute("aria-current", "step"); else element.removeAttribute("aria-current");
    });
  }
  function updateButtons() {
    $("extract-button").disabled = state.busy || !state.ready || state.saved || state.blocked;
    $("extract-button").textContent = state.busy ? "처리 중입니다…" : state.preview || editId ? "관계 다시 추출하기" : "관계 추출하기 →";
    $("save-button").disabled = state.busy || state.saved || !state.preview || !$("review-confirmed").checked;
    $("add-node").disabled = state.busy || state.nodes.length >= 30;
    $("add-relation").disabled = state.busy || state.relations.length >= 60;
  }
  function setBusy(value) {
    state.busy = value;
    $("document-fields").disabled = value || state.saved || state.blocked;
    $("use-document-example").disabled = value || state.saved || state.blocked;
    for (const control of $("review-content").querySelectorAll("input, select, textarea, button")) {
      if (value) { control.dataset.wasDisabled = String(control.disabled); control.disabled = true; }
      else if (control.dataset.wasDisabled !== undefined) { control.disabled = control.dataset.wasDisabled === "true"; delete control.dataset.wasDisabled; }
    }
    updateButtons();
  }
  async function request(url, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), payload ? 300000 : 20000);
    const headers = { Accept: "application/json" };
    const options = { method: payload ? "POST" : "GET", credentials: "same-origin", headers, signal: controller.signal };
    if (payload) {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = document.querySelector("input[name=csrfmiddlewaretoken]").value;
      options.body = JSON.stringify(payload);
    }
    try {
      const response = await fetch(url, options);
      let result;
      try { result = await response.json(); } catch { throw new Error("서버의 JSON 응답을 읽지 못했습니다. 연결 상태를 확인해 주세요."); }
      if (!response.ok) {
        const failure = new Error(result.error || `요청을 처리하지 못했습니다 (${response.status}).`);
        failure.status = response.status;
        failure.code = result.code;
        throw failure;
      }
      return result;
    } catch (failure) {
      if (failure.name === "AbortError") throw new Error("응답 시간이 길어 요청을 종료했습니다. 입력과 검토 내용은 유지됩니다. 저장 요청이었다면 같은 내용으로 다시 저장해 결과를 확인하세요.");
      if (failure instanceof TypeError) throw new Error("서버에 연결하지 못했습니다. 입력과 검토 내용은 유지됩니다. 서버 연결 후 다시 시도하세요.");
      throw failure;
    } finally { clearTimeout(timeout); }
  }
  async function loadCatalog() {
    const response = await request("/api/documents/catalog/");
    if (!Array.isArray(response.nodes)) throw new Error("기존 노드 목록의 형식을 확인할 수 없습니다.");
    state.catalog = response.nodes.filter((node) => kinds[node.kind]);
    state.ready = true;
    updateButtons();
  }
  function bodyCount() { $("body-count").textContent = `${$("document-body").value.length.toLocaleString("ko-KR")} / 12,000`; }
  function invalidate() {
    bodyCount();
    error("");
    if (!state.preview) return;
    state.preview = null;
    state.nodes = [];
    state.relations = [];
    $("review-content").hidden = true;
    $("review-empty").hidden = false;
    $("review-confirmed").checked = false;
    step(1);
    report("문서가 바뀌었습니다. 바뀐 원문으로 관계를 다시 추출해 주세요.");
    updateButtons();
  }
  function edited() {
    $("review-confirmed").checked = false;
    error("");
    updateSummary();
    updateButtons();
  }
  function field(label, control, wide = false) {
    const wrapper = create("div", `editor-field${wide ? " wide" : ""}`);
    control.id = control.id || uid();
    const caption = create("label", "", label);
    caption.htmlFor = control.id;
    wrapper.append(caption, control);
    return wrapper;
  }
  function textInput(value, limit, callback, multiline = false) {
    const control = create(multiline ? "textarea" : "input");
    if (!multiline) control.type = "text";
    control.value = value || "";
    control.maxLength = limit;
    control.addEventListener("input", () => { callback(control.value); edited(); });
    return control;
  }
  function remapRelations(before, after) {
    if (before === after) return;
    state.relations.forEach((relation) => {
      if (relation.source_id === before) relation.source_id = after;
      if (relation.target_id === before) relation.target_id = after;
    });
  }
  function newId(kind) {
    let id;
    do { id = `new-${kind === "Team" ? "team" : "service"}-${++state.serial}`; } while ([...state.nodes, ...state.catalog].some((node) => node.id === id));
    return id;
  }
  function renderNodes() {
    const container = $("node-editors");
    container.replaceChildren();
    if (!state.nodes.length) container.append(create("p", "empty-editors", "추출된 서비스·팀이 없습니다. ‘노드 추가’로 원문에 있는 대상을 등록할 수 있습니다."));
    state.nodes.forEach((node, index) => {
      const card = create("article", "node-editor");
      const heading = create("div", "editor-topline");
      const title = create("strong");
      title.append(create("span", `node-tag${node.kind === "Team" ? " team" : ""}`, kinds[node.kind] || "노드"), document.createTextNode(`${index + 1}. ${node.name || "이름을 입력하세요"}`));
      const remove = create("button", "doc-remove", "제거");
      remove.type = "button";
      remove.setAttribute("aria-label", `${node.name || index + 1} 노드와 연결된 관계 제거`);
      remove.addEventListener("click", () => {
        state.nodes = state.nodes.filter((item) => item.uid !== node.uid);
        const count = state.relations.length;
        state.relations = state.relations.filter((relation) => relation.source_id !== node.id && relation.target_id !== node.id);
        edited(); renderNodes(); renderRelations();
        report(`노드를 검토 목록에서 제거했습니다. 연결된 관계 ${count - state.relations.length}개도 함께 제거했습니다.`);
      });
      heading.append(title, remove);
      const mapping = create("select");
      mapping.append(option("", "새 노드로 만들기"));
      for (const kind of ["Service", "Team"]) {
        const group = create("optgroup"); group.label = `기존 ${kinds[kind]}`;
        state.catalog.filter((item) => item.kind === kind).forEach((item) => group.append(option(item.id, `${item.name} · ${item.id}`)));
        mapping.append(group);
      }
      mapping.value = node.existing ? node.id : "";
      mapping.addEventListener("change", () => {
        const before = node.id;
        const match = state.catalog.find((item) => item.id === mapping.value);
        if (match) {
          Object.assign(node, { id: match.id, kind: match.kind, name: match.name, description: match.description || "", existing: true });
          remapRelations(before, node.id);
          if (state.nodes.some((item) => item.uid !== node.uid && item.id === node.id)) {
            state.nodes = state.nodes.filter((item) => item.uid !== node.uid);
            report("이미 목록에 있는 기존 노드로 연결했습니다. 중복된 노드를 하나로 합쳤습니다.");
          }
        } else {
          node.existing = false; node.id = newId(node.kind); remapRelations(before, node.id);
        }
        edited(); renderNodes(); renderRelations();
      });
      const grid = create("div", "editor-grid");
      grid.append(field("기존 대상에 연결하거나 새로 만들기", mapping, true));
      if (node.existing) {
        const note = create("p", "node-existing-note");
        note.append(create("strong", "", node.name), document.createTextNode(` · ${kinds[node.kind]}`), create("br"), create("span", "node-existing-id", node.id));
        if (node.description) note.append(create("br"), document.createTextNode(node.description));
        card.append(heading, grid, note);
      } else {
        const kind = create("select"); Object.entries(kinds).forEach(([value, name]) => kind.append(option(value, name))); kind.value = node.kind;
        kind.addEventListener("change", () => { node.kind = kind.value; edited(); renderNodes(); renderRelations(); });
        const id = textInput(node.id, 100, () => {});
        id.setAttribute("pattern", "[a-z0-9][a-z0-9_-]{0,99}");
        id.title = "영문 소문자·숫자로 시작하고 소문자·숫자·하이픈·밑줄만 사용하세요.";
        id.addEventListener("change", () => { const before = node.id; node.id = id.value.trim(); remapRelations(before, node.id); edited(); renderRelations(); });
        const name = textInput(node.name, 200, (value) => { node.name = value; });
        name.addEventListener("change", () => { renderNodes(); renderRelations(); });
        grid.append(field("유형", kind), field("고유 ID · 영문 소문자/숫자/-/_", id), field("이름", name, true), field("설명 (선택)", textInput(node.description, 1000, (value) => { node.description = value; }, true), true));
        card.append(heading, grid);
      }
      container.append(card);
    });
    updateSummary(); updateButtons();
  }
  function endpointSelect(relation, side) {
    const select = create("select");
    select.append(option("", "대상을 선택하세요"));
    let candidates;
    if (side === "source_id" && relation.type === "DESCRIBES") candidates = [{ id: state.preview.document.id, name: `이 문서 · ${state.preview.document.title}` }];
    else candidates = state.nodes.filter((node) => node.kind === (side === "target_id" && relation.type === "OWNED_BY" ? "Team" : "Service"));
    candidates.forEach((node) => select.append(option(node.id, `${node.name || "이름 없음"} · ${node.id}`)));
    if (relation[side] && !candidates.some((node) => node.id === relation[side])) select.append(option(relation[side], `유형 확인 필요 · ${relation[side]}`));
    select.value = relation[side] || "";
    select.disabled = !relation.include;
    select.addEventListener("change", () => { relation[side] = select.value; edited(); });
    return select;
  }
  function evidenceStatus(relation, target) {
    const exists = Boolean(relation.evidence.trim()) && state.preview.document.body.includes(relation.evidence.trim());
    target.classList.toggle("invalid", !exists);
    target.textContent = exists ? "원문에서 확인한 근거입니다. 관계의 의미도 직접 검토해 주세요." : "원문에 있는 문장을 그대로 입력해 주세요.";
  }
  function renderRelations() {
    const container = $("relation-editors"); container.replaceChildren();
    if (!state.relations.length) container.append(create("p", "empty-editors", "검토할 관계가 없습니다. ‘관계 추가’로 이 문서가 설명하는 서비스부터 연결하세요."));
    state.relations.forEach((relation, index) => {
      const card = create("article", `relation-editor${relation.include ? "" : " excluded"}`);
      const top = create("div", "editor-topline");
      const include = create("input"); include.type = "checkbox"; include.checked = relation.include; include.id = uid();
      const label = create("label", "include-relation"); label.htmlFor = include.id; label.append(include, document.createTextNode(`관계 ${index + 1} 저장에 포함`));
      include.addEventListener("change", () => { relation.include = include.checked; edited(); renderRelations(); });
      const remove = create("button", "doc-remove", "제거"); remove.type = "button"; remove.setAttribute("aria-label", `관계 ${index + 1} 제거`);
      remove.addEventListener("click", () => { state.relations = state.relations.filter((item) => item.uid !== relation.uid); edited(); renderRelations(); });
      top.append(label, remove);
      const fields = create("div", "relation-fields");
      const type = create("select"); Object.entries(relationTypes).forEach(([value, text]) => type.append(option(value, text))); type.value = relation.type; type.disabled = !relation.include;
      type.addEventListener("change", () => {
        relation.type = type.value;
        relation.source_id = relation.type === "DESCRIBES" ? state.preview.document.id : state.nodes.find((node) => node.kind === "Service")?.id || "";
        relation.target_id = state.nodes.find((node) => node.kind === (relation.type === "OWNED_BY" ? "Team" : "Service") && node.id !== relation.source_id)?.id || "";
        edited(); renderRelations();
      });
      const path = create("div", "relation-path");
      const arrow = create("span", "relation-arrow", "→"); arrow.setAttribute("aria-hidden", "true");
      path.append(field("시작", endpointSelect(relation, "source_id")), arrow, field("도착", endpointSelect(relation, "target_id")));
      const feedback = create("p", "evidence-feedback"); feedback.id = uid();
      const evidence = textInput(relation.evidence, 1000, (value) => { relation.evidence = value; evidenceStatus(relation, feedback); }, true);
      evidence.disabled = !relation.include; evidence.setAttribute("aria-describedby", feedback.id);
      evidenceStatus(relation, feedback);
      fields.append(field("관계 유형", type), path, field("근거 문장 · 원문 그대로", evidence), feedback);
      card.append(top, fields); container.append(card);
    });
    updateSummary(); updateButtons();
  }
  function selectedData() {
    const relations = state.relations.filter((relation) => relation.include).map(({ source_id, type, target_id, evidence }) => ({ source_id, type, target_id, evidence: evidence.trim() }));
    const ids = new Set(relations.flatMap((relation) => [relation.source_id, relation.target_id]));
    const nodes = state.nodes.filter((node) => ids.has(node.id)).map(({ id, kind, name, description, existing }) => ({ id, kind, name: name.trim(), description: description.trim(), existing }));
    return { nodes, relations };
  }
  function updateSummary() {
    if (!state.preview) return;
    const selected = selectedData();
    $("node-review-count").textContent = `${state.nodes.length}개`;
    $("relation-review-count").textContent = `${selected.relations.length} / ${state.relations.length}개 선택`;
    $("save-summary").textContent = `문서 1개 · 연결된 서비스/팀 ${selected.nodes.length}개 · 검토한 관계 ${selected.relations.length}개를 저장합니다. ${editId ? "이 문서의 기존 관계 목록을 이 목록으로 교체합니다. 다른 문서와 공유하거나 별도로 등록된 관계는 유지됩니다." : "관계에 연결되지 않은 노드는 저장하지 않습니다."}`;
  }
  function validateReview(data) {
    if (!data.relations.some((relation) => relation.type === "DESCRIBES")) return "이 문서가 설명하는 서비스를 ‘설명’ 관계로 하나 이상 연결해 주세요.";
    const ids = new Set();
    for (const node of data.nodes) {
      if (!node.id.trim() || !node.name.trim()) return "저장할 노드의 고유 ID와 이름을 입력해 주세요.";
      if (!/^[a-z0-9][a-z0-9_-]{0,99}$/.test(node.id)) return "노드 ID는 소문자 영문·숫자로 시작하는 100자 이하 소문자 영문·숫자·하이픈·밑줄이어야 합니다.";
      if (ids.has(node.id)) return `고유 ID ‘${node.id}’가 중복됩니다. 같은 대상은 하나의 노드로 연결해 주세요.`;
      ids.add(node.id);
    }
    const byId = new Map(data.nodes.map((node) => [node.id, node]));
    const relationKeys = new Set();
    for (const [index, relation] of data.relations.entries()) {
      const source = byId.get(relation.source_id); const target = byId.get(relation.target_id);
      const valid = relation.type === "DESCRIBES" ? relation.source_id === state.preview.document.id && target?.kind === "Service" : source?.kind === "Service" && target?.kind === (relation.type === "OWNED_BY" ? "Team" : "Service");
      if (!valid || relation.source_id === relation.target_id) return `선택한 관계 ${index + 1}의 시작·도착 대상과 유형을 확인해 주세요.`;
      if (!relation.evidence || !state.preview.document.body.includes(relation.evidence)) return `선택한 관계 ${index + 1}의 근거를 원문에서 그대로 가져와 주세요.`;
      const key = JSON.stringify([relation.source_id, relation.type, relation.target_id]);
      if (relationKeys.has(key)) return `선택한 관계 ${index + 1}이 중복됩니다. 하나만 포함해 주세요.`;
      relationKeys.add(key);
    }
    return "";
  }
  function showPreview(response, stored = false) {
    if (!response.review_token || !response.document || !Array.isArray(response.nodes) || !Array.isArray(response.relations)) throw new Error("추출 응답 형식을 확인할 수 없습니다. 문서를 유지한 채 다시 시도하세요.");
    state.preview = response;
    response.nodes.filter((node) => node.existing && !state.catalog.some((item) => item.id === node.id)).forEach((node) => state.catalog.push(node));
    state.nodes = response.nodes.map((node) => ({ ...node, uid: uid(), description: node.description || "", existing: Boolean(node.existing) }));
    state.relations = response.relations.map((relation) => ({ ...relation, uid: uid(), include: true, evidence: relation.evidence || "" }));
    $("review-empty").hidden = true; $("review-content").hidden = false; $("save-success").hidden = true; $("review-confirmed").checked = false;
    $("extraction-meta").textContent = stored ? "현재 저장된 관계입니다. 필요한 내용을 수정하고 검토 확인 후 저장하세요." : `${response.provider || "LLM"} · ${response.model || "서버 설정 모델"}에서 추출했습니다. 아직 저장되지 않았습니다.`;
    $("review-document-title").textContent = response.document.title;
    $("review-document-source").textContent = response.document.source || "출처 미입력";
    $("review-document-body").textContent = response.document.body;
    const warnings = $("extraction-warnings"); warnings.replaceChildren(); warnings.hidden = !(response.warnings || []).length;
    if (!warnings.hidden) { const list = create("ul"); response.warnings.forEach((warning) => list.append(create("li", "", warning))); warnings.append(list); }
    renderNodes(); renderRelations(); step(2);
    report(stored ? `문서와 저장된 관계 ${state.relations.length}개를 불러왔습니다. 관계를 직접 수정하거나 원문을 바꿔 다시 추출하세요.` : `관계 ${state.relations.length}개를 추출했습니다. 원문과 비교하고 필요한 내용을 수정해 주세요.`);
    if (!stored) $("review-heading").focus();
  }
  $("document-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (state.busy || state.saved || state.blocked || !state.ready || !$("document-form").reportValidity()) return;
    const payload = { title: $("document-title").value.trim(), source: $("document-source").value.trim(), body: $("document-body").value };
    if (!payload.title || !payload.body.trim()) { error("문서 제목과 본문을 입력해 주세요."); return; }
    error(""); setBusy(true); report("LLM이 문서에서 서비스·팀과 관계를 찾고 있습니다. 잠시 기다려 주세요.", true);
    if (editId) payload.version = state.version;
    try { await loadCatalog(); showPreview(await request(editId ? `/api/documents/${encodeURIComponent(editId)}/extract/` : "/api/documents/extract/", payload)); }
    catch (failure) { error(failure.message); conflictHelp(failure); report("관계를 추출하지 못했습니다. 문서와 기존 검토 내용은 유지됩니다."); }
    finally { setBusy(false); }
  });
  $("save-button").addEventListener("click", async () => {
    if (state.busy || state.saved || !state.preview || !$("review-confirmed").checked) return;
    const data = selectedData(); const invalid = validateReview(data);
    if (invalid) { error(invalid); $("document-error").scrollIntoView({ block: "center", behavior: "smooth" }); return; }
    error(""); setBusy(true); report("검토한 문서와 관계를 Neo4j에 저장하고 있습니다.", true);
    try {
      const result = await request(editId ? `/api/documents/${encodeURIComponent(editId)}/update/` : "/api/documents/save/", { review_token: state.preview.review_token, ...data });
      state.saved = true; $("review-content").hidden = true; $("save-success").hidden = false; step(3);
      $("save-success-message").textContent = result.message || `‘${result.document.title}’ 문서와 관계가 검색에 반영되었습니다.`;
      $("save-warnings").textContent = (result.warnings || []).join("\n"); $("save-warnings").hidden = !(result.warnings || []).length;
      const service = result.service_ids?.[0]; $("search-new-document").href = service ? `/graphrag/?service_id=${encodeURIComponent(service)}` : "/graphrag/";
      try { localStorage.setItem("graphlab-document-revision", String(Date.now())); } catch { /* Storage may be unavailable in a restricted browser. */ }
      report(editId ? "수정을 완료했습니다. GraphRAG 검색에 변경한 문서와 관계가 반영되었습니다." : "저장을 완료했습니다. GraphRAG에서 새 문서와 관계를 확인할 수 있습니다.");
      $("search-new-document").focus();
    } catch (failure) { error(failure.message); conflictHelp(failure); report(failure.status === 409 ? "기존 데이터와 충돌했습니다. 검토 내용은 유지됩니다. 최신 문서를 확인하고 다시 검토해 주세요." : "저장을 완료하지 못했습니다. 검토 내용은 유지됩니다. 연결을 확인한 뒤 같은 내용으로 다시 시도할 수 있습니다."); }
    finally { setBusy(false); }
  });
  $("review-confirmed").addEventListener("change", updateButtons);
  ["document-title", "document-source", "document-body"].forEach((id) => $(id).addEventListener("input", invalidate));
  $("use-document-example").addEventListener("click", () => {
    $("document-title").value = "주문 서비스 운영 메모";
    $("document-source").value = "실습용 예제 문서";
    $("document-body").value = "주문 서비스는 결제 서비스를 호출하며, 커머스팀이 담당한다. 결제 서비스의 장애가 발생하면 주문의 결제 단계가 영향을 받을 수 있다.";
    invalidate(); $("document-title").focus();
  });
  $("document-file").addEventListener("change", async () => {
    const file = $("document-file").files?.[0]; if (!file || state.busy) return;
    error("");
    try {
      if (!/\.(txt|md)$/i.test(file.name)) throw new Error("TXT 또는 Markdown(.md) 파일을 선택해 주세요.");
      if (file.size > 65536) throw new Error("64 KB 이하의 파일을 선택해 주세요.");
      setBusy(true);
      let body;
      try { body = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer()); } catch { throw new Error("UTF-8 텍스트 파일을 읽지 못했습니다. 파일을 UTF-8로 저장한 뒤 다시 선택해 주세요."); }
      if (body.includes("\0")) throw new Error("텍스트가 아닌 내용이 포함되어 있습니다. UTF-8 TXT 또는 Markdown 파일을 선택해 주세요.");
      if (body.length > 12000) throw new Error("본문은 최대 12,000자입니다. 파일의 필요한 부분을 나누어 등록해 주세요.");
      $("document-body").value = body;
      if (!$("document-title").value.trim()) $("document-title").value = file.name.replace(/\.(txt|md)$/i, "").slice(0, 200);
      if (!$("document-source").value.trim()) $("document-source").value = file.name.slice(0, 500);
      invalidate(); report(`‘${file.name}’ 내용을 본문에 가져왔습니다. 제목과 본문을 확인한 뒤 추출하세요.`);
    } catch (failure) { error(failure.message); }
    finally { $("document-file").value = ""; setBusy(false); }
  });
  $("add-node").addEventListener("click", () => {
    if (!state.preview || state.nodes.length >= 30 || state.busy) return;
    state.nodes.push({ uid: uid(), id: newId("Service"), kind: "Service", name: "", description: "", existing: false });
    edited(); renderNodes(); renderRelations();
    $("node-editors").lastElementChild.querySelector("select").focus();
  });
  $("add-relation").addEventListener("click", () => {
    if (!state.preview || state.relations.length >= 60 || state.busy) return;
    state.relations.push({ uid: uid(), source_id: state.preview.document.id, type: "DESCRIBES", target_id: state.nodes.find((node) => node.kind === "Service")?.id || "", evidence: "", include: true });
    edited(); renderRelations(); $("relation-editors").lastElementChild.querySelector("select").focus();
  });
  $("new-document").addEventListener("click", async () => {
    if (editId) { window.location.assign("/documents/"); return; }
    state.saved = false; state.preview = null; state.nodes = []; state.relations = [];
    $("document-form").reset(); $("review-confirmed").checked = false;
    $("save-success").hidden = true; $("review-content").hidden = true; $("review-empty").hidden = false;
    bodyCount(); error(""); step(1); setBusy(false); $("document-title").focus();
    try { await loadCatalog(); report("다음 문서를 입력해 주세요."); } catch (failure) { error(failure.message); }
  });
  async function initialize() {
    if (editId) {
      document.title = "문서 수정 · GraphLab";
      $("page-title").replaceChildren(document.createTextNode("문서를 업데이트하세요"), create("span", "", "."));
      $("document-heading-help").textContent = "최신 원문과 검토한 관계로 지식을 갱신하고 검색에 반영합니다.";
      $("document-breadcrumb").textContent = "문서 수정";
      $("document-back").href = "/documents/manage/"; $("document-back").textContent = "문서 목록으로 돌아가기 →";
      $("register-navigation").classList.remove("active"); $("register-navigation").removeAttribute("aria-current");
      $("register-navigation").querySelector(".nav-dot")?.remove(); $("manage-navigation").classList.add("active"); $("manage-navigation").setAttribute("aria-current", "page");
      $("input-heading").textContent = "문서 내용을 수정하세요"; $("save-button").textContent = "수정한 내용 저장하기";
      $("document-edit-note").hidden = false; $("use-document-example").closest("details").hidden = true;
      $("view-latest-document").href = `/documents/?edit=${encodeURIComponent(editId)}`;
    }
    setBusy(true);
    try {
      await loadCatalog();
      if (editId) {
        const detail = await request(`/api/documents/${encodeURIComponent(editId)}/`);
        if ((detail.document?.can_manage ?? detail.can_manage) !== true) throw new Error("이 문서는 읽기 전용입니다. 문서 관리 목록에서 직접 등록한 문서를 선택해 주세요.");
        state.version = detail.document.version;
        $("document-title").value = detail.document.title; $("document-source").value = detail.document.source || ""; $("document-body").value = detail.document.body; bodyCount();
        detail.nodes = detail.nodes.map((node) => ({ ...node, existing: true }));
        showPreview(detail, true);
      } else report(`기존 서비스·팀 ${state.catalog.length}개를 연결할 수 있습니다. 문서를 입력해 주세요.`);
    } catch (failure) {
      state.blocked = true; error(failure.message); report(editId ? "수정할 문서를 불러오지 못했습니다. 문서 목록에서 최신 상태를 확인해 주세요." : "기존 노드를 불러오지 못했습니다. Neo4j 연결을 확인하고 페이지를 새로 고쳐 주세요.");
    } finally { setBusy(false); }
  }
  initialize();
})();

/* Local, dependency-free GraphRAG workspace. Server/model text is never parsed as HTML. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const ns = "http://www.w3.org/2000/svg";
  const state = { status: null, graph: { nodes: [], edges: [] }, retrieval: null, highlighted: false, busy: false, refreshing: false, selectedNode: null, zoom: 100 };
  const kindNames = { Service: "서비스", Team: "팀", Document: "문서" };
  const relationshipNames = { DEPENDS_ON: "의존", OWNED_BY: "담당팀", DESCRIBES: "설명" };
  let pendingSavedService = new URLSearchParams(window.location.search).get("service_id");
  let graphRevisionChanged = false;
  let documentRevision = 0;
  let lastQuery = null;
  let refreshQuery = false;
  const iconPaths = {
    document: "M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6",
    team: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M22 21v-2a4 4 0 0 0-3-3.87 M15 3.13a4 4 0 0 1 0 7.75 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    service: "m12 3 9 5v8l-9 5-9-5V8z M3 8l9 5 9-5 M12 13v8",
    pointer: "m4 3 7 18 3-7 7-3L4 3z",
  };

  function element(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  }

  function svgElement(tag, attributes = {}, text) {
    const item = document.createElementNS(ns, tag);
    for (const [name, value] of Object.entries(attributes)) item.setAttribute(name, String(value));
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  }

  function graphTextMeasurer(svg, className) {
    const sample = svgElement("text", { class: className, "aria-hidden": "true" });
    svg.append(sample);
    const style = window.getComputedStyle(sample);
    const context = document.createElement("canvas").getContext("2d");
    context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    sample.remove();
    return (text) => context.measureText(text).width;
  }

  function shortenLabel(text, width, measure) {
    if (measure(text) <= width) return text;
    const characters = Array.from(text);
    while (characters.length && measure(`${characters.join("")}…`) > width) characters.pop();
    return `${characters.join("").trimEnd()}…`;
  }

  function wrapNodeLabel(text, width, measure) {
    const label = String(text).trim().replace(/\s+/g, " ");
    if (measure(label) <= width) return [label];
    const words = label.split(" ");
    let balanced = null;
    let difference = Infinity;
    // Prefer complete words on both lines; balance titles such as ‘인증 서비스 / 확인 가이드’.
    for (let index = 1; index < words.length; index += 1) {
      const lines = [words.slice(0, index).join(" "), words.slice(index).join(" ")];
      const widths = lines.map(measure);
      if (Math.max(...widths) <= width && Math.abs(widths[0] - widths[1]) < difference) {
        balanced = lines;
        difference = Math.abs(widths[0] - widths[1]);
      }
    }
    if (balanced) return balanced;
    let first = "";
    for (const word of words) {
      const candidate = first ? `${first} ${word}` : word;
      if (measure(candidate) > width) break;
      first = candidate;
    }
    // Labels without spaces still fit the card; the complete text remains in title/aria-label.
    if (!first) {
      for (const character of Array.from(label)) {
        if (measure(first + character) > width) break;
        first += character;
      }
    }
    return [first, shortenLabel(label.slice(first.length).trim(), width, measure)];
  }

  function icon(kind, className = "detail-icon") {
    const item = svgElement("svg", { viewBox: "0 0 24 24", width: 24, height: 24, class: className, fill: "none", stroke: "currentColor", "stroke-width": 1.6, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" });
    item.append(svgElement("path", { d: iconPaths[kind] || iconPaths.pointer }));
    return item;
  }

  function setWorkflow(status, text) {
    $("workflow-status").dataset.state = status;
    $("workflow-status").textContent = text;
  }

  function updateIntentHint() {
    const hints = {
      auto: "질문에 맞춰 담당팀·문서 또는 장애 영향 후보를 탐색합니다. 아래 예제로 범위를 확인하세요.",
      context: "기준 서비스와 직접 의존하는 서비스(1홉)의 담당팀·관련 문서를 조회합니다.",
      impact: "기준 서비스에 의존하는 서비스를 역방향으로 최대 5홉 탐색합니다. 결과는 잠재 영향 후보이며 실제 장애 발생을 뜻하지 않습니다.",
    };
    $("intent-hint").textContent = hints[$("intent").value] || hints.auto;
  }

  function setExampleSelection(selected = null) {
    for (const button of document.querySelectorAll(".example-button")) {
      button.classList.toggle("selected", button === selected);
      button.setAttribute("aria-pressed", String(button === selected));
    }
  }

  function updateZoom() {
    const unavailable = state.refreshing || !(state.graph.nodes || []).length;
    $("graph-canvas").style.setProperty("--graph-scale", String(state.zoom / 100));
    $("zoom-level").textContent = `${state.zoom}%`;
    $("zoom-in").disabled = unavailable || state.zoom >= 150;
    $("zoom-out").disabled = unavailable || state.zoom <= 75;
    $("zoom-reset").disabled = unavailable || state.zoom === 100;
  }

  function setGraphCounts(nodes = null, edges = null) {
    $("node-count").textContent = nodes ? nodes.length : "—";
    $("edge-count").textContent = edges ? edges.length : "—";
    for (const [kind, id] of [["Service", "service-count"], ["Team", "team-count"], ["Document", "document-count"]]) {
      $(id).textContent = nodes ? nodes.filter((node) => node.kind === kind).length : "—";
    }
  }

  async function fetchJSON(url, options = {}, timeout = 20000) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal, headers: { Accept: "application/json", ...options.headers } });
      let data;
      try { data = await response.json(); }
      catch { throw new Error("서버가 JSON 응답을 반환하지 않았습니다. Django 실행 상태와 서버 로그를 확인해 주세요."); }
      if (!response.ok) {
        const error = new Error(data.error || `요청을 처리하지 못했습니다. (HTTP ${response.status})`);
        error.data = data;
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("응답 대기 시간이 지났습니다. 서버 상태를 확인한 뒤 다시 시도하거나 ‘근거만 조회’를 사용해 주세요.");
      if (error instanceof TypeError) throw new Error("서버에 연결할 수 없습니다. Django 서버가 실행 중인지 확인해 주세요.");
      throw error;
    } finally { window.clearTimeout(timer); }
  }

  function setBadge(id, ok, message) {
    $(id).className = `status-badge ${ok ? "ok" : "error"}`;
    $(id).textContent = ok ? "연결됨" : "연결 필요";
    $(id).title = message || "";
  }

  function updateControls() {
    const neo4jOK = Boolean(state.status?.neo4j?.ok);
    const llmOK = Boolean(state.status?.llm?.ok);
    const locked = state.busy || state.refreshing;
    // A gateway can forbid model-list health checks while allowing generation.
    $("ask-button").disabled = locked || !neo4jOK;
    $("ask-button").title = !neo4jOK ? "먼저 Neo4j 연결을 확인해 주세요." : !llmOK ? "LLM 상태 확인에 실패했지만 답변 생성을 시도할 수 있습니다. ‘근거만 조회’도 사용할 수 있습니다." : "조회한 근거를 바탕으로 답변을 생성합니다.";
    $("retrieve-button").disabled = locked || !neo4jOK;
    $("question").disabled = locked;
    $("service-id").disabled = locked;
    $("intent").disabled = locked;
    $("refresh-status").disabled = locked;
    for (const button of document.querySelectorAll(".example-button")) button.disabled = locked;
    $("answer-card").setAttribute("aria-busy", String(state.busy));
    $("graph-view").setAttribute("aria-busy", String(state.refreshing));
    updateZoom();
  }

  function renderStatus(data) {
    state.status = data;
    setBadge("neo4j-badge", Boolean(data.neo4j?.ok), data.neo4j?.message);
    setBadge("llm-badge", Boolean(data.llm?.ok), data.llm?.message);
    $("model-name").textContent = data.llm?.model || "모델 미설정";
    $("provider-name").textContent = data.llm?.provider ? ` / ${data.llm.provider}` : "";
    $("sidebar-connection").textContent = data.neo4j?.ok ? "Neo4j 연결됨" : "Neo4j 연결 필요";
    $("sidebar-connection-dot").className = `connection-dot ${data.neo4j?.ok ? "ok" : "error"}`;
    const previousService = $("service-id").value;
    $("service-id").replaceChildren(element("option", "", "질문에서 자동 선택"));
    $("service-id").firstElementChild.value = "";
    for (const service of data.services || []) {
      const option = element("option", "", service.name || service.id);
      option.value = service.id;
      $("service-id").append(option);
    }
    if ((data.services || []).some((service) => service.id === previousService)) $("service-id").value = previousService;
    const messages = [];
    if (!data.neo4j?.ok) messages.push(`Neo4j 연결이 필요합니다. ${data.neo4j?.message || "DB가 실행 중인지 확인해 주세요."}`);
    if (!data.llm?.ok) messages.push(`LLM 연결 전에도 ‘근거만 조회’를 사용할 수 있습니다. ${data.llm?.message || ".env의 LLM 설정과 모델 서버 연결을 확인해 주세요."}`);
    if (data.neo4j?.ok && !(data.services || []).length) messages.push("등록된 서비스가 없습니다. README의 예제 데이터 적재 절차를 실행한 뒤 ‘연결 확인’을 눌러 주세요.");
    $("connection-notice").textContent = messages.join("\n");
    $("connection-notice").hidden = messages.length === 0;
    updateControls();
  }

  async function refresh() {
    if (state.busy || state.refreshing) return;
    state.refreshing = true;
    updateControls();
    setWorkflow("loading", "연결과 그래프 확인 중");
    $("graph-loading").hidden = false;
    $("graph-error").hidden = true;
    $("graph-canvas").hidden = true;
    $("connection-notice").hidden = true;
    for (const id of ["neo4j-badge", "llm-badge"]) {
      $(id).className = "status-badge checking";
      $(id).textContent = "확인 중";
      $(id).title = "";
    }
    const results = await Promise.allSettled([fetchJSON("/api/graphrag/status/"), fetchJSON("/api/graph/")]);
    if (results[0].status === "fulfilled") renderStatus(results[0].value);
    else {
      state.status = null;
      setBadge("neo4j-badge", false, "연결 확인 실패");
      setBadge("llm-badge", false, "연결 확인 실패");
      $("model-name").textContent = "상태 확인 불가";
      $("provider-name").textContent = "";
      $("sidebar-connection").textContent = "서버 연결 확인 필요";
      $("sidebar-connection-dot").className = "connection-dot error";
      $("connection-notice").textContent = `${results[0].reason.message} ‘연결 확인’으로 다시 시도할 수 있습니다.`;
      $("connection-notice").hidden = false;
    }
    $("graph-loading").hidden = true;
    if (results[1].status === "fulfilled") {
      state.graph = results[1].value;
      setGraphCounts(state.graph.nodes || [], state.graph.edges || []);
      $("graph-error").hidden = true;
      if (!(state.graph.nodes || []).some((node) => node.id === state.selectedNode)) {
        state.selectedNode = null;
        $("node-detail").replaceChildren(icon("pointer"), element("p", "", "노드를 선택해 상세 정보를 확인하세요."));
      }
      renderGraph();
    } else {
      state.graph = { nodes: [], edges: [] };
      state.selectedNode = null;
      $("graph-error").textContent = `그래프를 불러오지 못했습니다.\n${results[1].reason.message}\n상단 ‘연결 확인’을 눌러 다시 조회하세요.`;
      $("graph-error").hidden = false;
      $("graph-canvas").hidden = true;
      $("graph-edges-list").replaceChildren();
      $("node-detail").replaceChildren(icon("pointer"), element("p", "", "연결을 확인하면 노드의 상세 정보를 볼 수 있습니다."));
      setGraphCounts();
    }
    state.refreshing = false;
    if (!state.status?.neo4j?.ok || results[1].status === "rejected") setWorkflow("error", "연결 상태 확인 필요");
    else if (!(state.graph.nodes || []).length) setWorkflow("idle", "예제 데이터 적재 필요");
    else setWorkflow(state.retrieval ? "done" : "idle", state.retrieval ? "연결 확인 완료 · 조회 결과 유지" : "탐색 준비 완료");
    updateControls();
    if (pendingSavedService && state.status?.neo4j?.ok) {
      const service = (state.status.services || []).find((item) => item.id === pendingSavedService);
      pendingSavedService = null;
      if (service) {
        $("service-id").value = service.id;
        $("intent").value = "context";
        $("question").value = `${service.name || service.id}의 담당팀과 관련 문서를 알려줘`;
        $("question").dispatchEvent(new Event("input"));
        updateIntentHint();
        await submit("retrieve");
      }
    }
    if (graphRevisionChanged && !state.busy) { graphRevisionChanged = false; refresh(); }
    else if (refreshQuery && lastQuery && state.status?.neo4j?.ok) {
      refreshQuery = false;
      await submit("retrieve", lastQuery);
    }
  }

  function graphLayout(nodes, edges) {
    const services = nodes.filter((node) => node.kind === "Service");
    const teams = nodes.filter((node) => node.kind === "Team");
    const documents = nodes.filter((node) => node.kind === "Document");
    const others = nodes.filter((node) => !kindNames[node.kind]);
    const rowCount = Math.max(services.length, documents.length, teams.length, others.length, 4);
    const height = Math.max(520, rowCount * 110 + 100);
    const positions = new Map();
    services.forEach((node, index) => positions.set(node.id, { x: 400, y: 100 + index * 110, type: "service" }));
    const serviceOrder = new Map(services.map((node, index) => [node.id, index]));
    documents.sort((a, b) => {
      const targetA = edges.find((edge) => edge.source === a.id && edge.type === "DESCRIBES")?.target;
      const targetB = edges.find((edge) => edge.source === b.id && edge.type === "DESCRIBES")?.target;
      return (serviceOrder.get(targetA) ?? 99) - (serviceOrder.get(targetB) ?? 99);
    });
    documents.forEach((node, index) => positions.set(node.id, { x: 120, y: 100 + index * 110, type: "document" }));
    teams.forEach((node, index) => positions.set(node.id, { x: 690, y: 100 + (index + .5) * (rowCount - 1) * 110 / Math.max(teams.length, 1), type: "team" }));
    others.forEach((node, index) => positions.set(node.id, { x: 550, y: 100 + index * 110, type: "service" }));
    return { positions, height };
  }

  const edgeKey = (edge) => JSON.stringify([edge.source, edge.type, edge.target]);

  function renderGraph() {
    const nodes = state.graph.nodes || [];
    const edges = state.graph.edges || [];
    $("graph-canvas").hidden = nodes.length === 0;
    updateZoom();
    if (!nodes.length) {
      $("graph-error").textContent = "아직 그래프가 비어 있습니다.\nREADME를 따라 예제 데이터를 적재한 뒤 ‘연결 확인’을 눌러 주세요.";
      $("graph-error").hidden = false;
      $("graph-edges-list").replaceChildren();
      return;
    }
    const { positions, height } = graphLayout(nodes, edges);
    const svg = $("knowledge-graph");
    svg.setAttribute("viewBox", `0 0 800 ${height}`);
    svg.replaceChildren(svgElement("title", { id: "svg-title" }, "Neo4j의 서비스, 팀, 문서 연결 그래프"), svgElement("desc", { id: "svg-description" }, "노드를 선택하면 상세 정보를 확인할 수 있습니다. 아래 연결 목록에서도 동일한 관계를 읽을 수 있습니다."));
    const measureNode = graphTextMeasurer(svg, "graph-node-label");
    const measureEdge = graphTextMeasurer(svg, "edge-text");
    const defs = svgElement("defs");
    for (const [name, className] of [["arrow", "edge-arrow"], ["arrow-highlight", "edge-arrow-highlight"]]) {
      const marker = svgElement("marker", { id: name, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse" });
      marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", class: className, fill: "currentColor" }));
      defs.append(marker);
    }
    svg.append(defs);
    for (const [x, label] of [[120, "DOCUMENTS"], [400, "SERVICES"], [690, "TEAMS"]]) svg.append(svgElement("text", { x, y: 46, class: "graph-column-label", "text-anchor": "middle" }, label));
    const activeNodeIDs = new Set((state.retrieval?.graph?.nodes || []).map((node) => node.id));
    const activeEdges = new Set((state.retrieval?.graph?.edges || []).map(edgeKey));
    const edgeLayer = svgElement("g");
    let dependencyIndex = 0;
    for (const edge of edges) {
      const from = positions.get(edge.source);
      const to = positions.get(edge.target);
      if (!from || !to) continue;
      const highlighted = state.highlighted && activeEdges.has(edgeKey(edge));
      const group = svgElement("g", { class: `graph-edge${state.highlighted ? highlighted ? " highlight" : " dimmed" : ""}` });
      let path, labelX, labelY;
      if (from.type === "service" && to.type === "service") {
        const direction = to.y > from.y ? 1 : -1;
        const startY = from.y + direction * 25;
        const endY = to.y - direction * 25;
        const bend = 510 + dependencyIndex * 18;
        path = `M ${from.x + 26} ${startY} C ${bend} ${startY}, ${bend} ${endY}, ${to.x + 26} ${endY}`;
        labelX = (from.x + 26) * .25 + bend * .75;
        labelY = (startY + endY) / 2 - 5;
        dependencyIndex += 1;
      } else {
        const forward = to.x > from.x ? 1 : -1;
        const fromOffset = from.type === "document" ? 92 : from.type === "team" ? 72 : 38;
        const toOffset = to.type === "document" ? 96 : to.type === "team" ? 76 : 42;
        const startX = from.x + forward * fromOffset;
        const endX = to.x - forward * toOffset;
        const midX = (startX + endX) / 2;
        path = `M ${startX} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${endX} ${to.y}`;
        labelX = midX;
        labelY = (from.y + to.y) / 2 - 6;
        // Keep ownership labels near the team, outside the dependency channel.
        if (edge.type === "OWNED_BY" && to.type === "team") {
          labelX = endX - forward * 30;
          labelY = to.y - 10;
        }
      }
      group.append(svgElement("path", { d: path, class: "edge-line", "marker-end": `url(#${highlighted ? "arrow-highlight" : "arrow"})` }));
      const rawType = String(edge.type || "RELATIONSHIP");
      const displayType = shortenLabel({ DEPENDS_ON: "의존", OWNED_BY: "담당", DESCRIBES: "설명" }[rawType] || rawType, 78, measureEdge);
      const width = Math.ceil(measureEdge(displayType)) + 14;
      group.append(svgElement("title", {}, rawType));
      group.append(svgElement("rect", { x: labelX - width / 2, y: labelY - 11, width, height: 16, rx: 3, class: "edge-label-background" }));
      group.append(svgElement("text", { x: labelX, y: labelY, "text-anchor": "middle", class: "edge-text" }, displayType));
      edgeLayer.append(group);
    }
    svg.append(edgeLayer);
    for (const node of nodes) {
      const point = positions.get(node.id);
      const highlighted = state.highlighted && activeNodeIDs.has(node.id);
      const group = svgElement("g", { transform: `translate(${point.x} ${point.y})`, class: `graph-node ${point.type}${state.highlighted ? highlighted ? " highlight" : " dimmed" : ""}${state.selectedNode === node.id ? " selected" : ""}`, "data-node-id": node.id, tabindex: 0, role: "button", "aria-label": `${kindNames[node.kind] || node.kind}: ${node.label || node.id}. 상세 보기`, "aria-pressed": String(state.selectedNode === node.id) });
      group.append(svgElement("title", {}, `${node.label || node.id}\n${node.id}`));
      if (point.type === "service") {
        group.append(svgElement("circle", { cx: 0, cy: 0, r: 36, class: "node-shape" }));
        group.append(svgElement("path", { d: "M -10 -8 L 0 -13 L 10 -8 L 10 5 L 0 11 L -10 5 Z M -10 -8 L 0 -2 L 10 -8 M 0 -2 L 0 11", class: "node-symbol", fill: "none", stroke: "currentColor", "stroke-width": 1.6, "stroke-linejoin": "round" }));
        const serviceLabel = shortenLabel(String(node.label || node.id), 136, measureNode);
        group.append(svgElement("text", { x: 0, y: 57, "text-anchor": "middle", class: "graph-node-label" }, serviceLabel));
      } else {
        const width = point.type === "document" ? 184 : 146;
        group.append(svgElement("rect", { x: -width / 2, y: -28, width, height: 56, rx: 7, class: "node-shape" }));
        const nodeIcon = svgElement("g", { transform: `translate(${-width / 2 + 10} -10) scale(.85)`, class: "node-icon", fill: "none", stroke: "currentColor", "stroke-width": 1.6, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
        nodeIcon.append(svgElement("path", { d: iconPaths[point.type] }));
        group.append(nodeIcon);
        const parts = wrapNodeLabel(node.label || node.id, point.type === "document" ? 132 : 94, measureNode);
        parts.forEach((part, index) => group.append(svgElement("text", { x: 10, y: parts.length > 1 ? -4 + index * 19 : 5, "text-anchor": "middle", class: "graph-node-label" }, part)));
      }
      const select = () => selectNode(node);
      group.addEventListener("click", select);
      group.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } });
      svg.append(group);
    }
    const names = new Map(nodes.map((node) => [node.id, node.label || node.id]));
    $("graph-edges-list").replaceChildren();
    for (const edge of edges) {
      const prefix = state.highlighted && activeEdges.has(edgeKey(edge)) ? "[검색 근거] " : "";
      const relation = relationshipNames[edge.type] ? `${relationshipNames[edge.type]} (${edge.type})` : edge.type || "RELATIONSHIP";
      $("graph-edges-list").append(element("li", "", `${prefix}${names.get(edge.source) || edge.source} → ${relation} → ${names.get(edge.target) || edge.target}`));
    }
    $("graph-caption").textContent = state.highlighted ? `${state.retrieval?.service?.name || "선택 서비스"} · 검색에 사용한 연결 강조` : state.graph.truncated ? "전체 그래프의 일부를 표시합니다" : "전체 연결 구조 · 작은 화면에서는 좌우로 이동";
    $("clear-highlight").hidden = !state.retrieval;
    $("clear-highlight").textContent = state.highlighted ? "전체 보기" : "검색 근거 강조";
  }

  function selectNode(node) {
    state.selectedNode = node.id;
    const detail = element("p");
    detail.append(element("strong", "", `${kindNames[node.kind] || node.kind} · ${node.label || node.id}`), element("br"), element("code", "", node.id));
    if (node.description) detail.append(element("br"), document.createTextNode(node.description));
    $("node-detail").replaceChildren(icon(String(node.kind).toLowerCase()), detail);
    // Keep the currently focused SVG element mounted for keyboard navigation.
    for (const group of $("knowledge-graph").querySelectorAll(".graph-node")) {
      const selected = group.getAttribute("data-node-id") === String(node.id);
      group.classList.toggle("selected", selected);
      group.setAttribute("aria-pressed", String(selected));
    }
  }

  function renderSources(sources) {
    $("source-count").textContent = sources.length;
    $("sources-list").replaceChildren();
    if (!sources.length) {
      $("sources-list").append(element("p", "sources-empty", "이 조회에서 찾은 문서가 없습니다. 서비스 선택과 저장된 문서 연결을 확인해 주세요."));
      return;
    }
    for (const source of sources) {
      const details = element("details", "source-item");
      const summary = element("summary");
      const heading = element("span", "source-heading");
      heading.append(element("strong", "", source.title || source.document_id || "제목 없는 문서"), element("small", "", source.source || "출처 경로 미등록"));
      summary.append(element("span", "source-tag", `[${source.id}]`), heading, element("span", "source-expand", "+"));
      const body = (source.body || "이 문서에는 조회 가능한 본문이 없습니다.") + (source.truncated ? "\n\n[본문 길이 제한으로 문서의 일부를 표시합니다.]" : "");
      details.append(summary, element("div", "source-body", body));
      $("sources-list").append(details);
    }
  }

  function renderTrace(trace) {
    $("trace-count").textContent = trace.length;
    $("trace-list").replaceChildren();
    if (!trace.length) $("trace-list").append(element("p", "trace-empty", "이번 조회에서 반환된 Cypher 기록이 없습니다."));
    trace.forEach((entry, index) => {
      const section = element("section", "trace-item");
      const heading = element("div", "trace-item-header");
      const count = Array.isArray(entry.rows) ? entry.rows.length : typeof entry.rows === "number" ? entry.rows : entry.row_count;
      heading.append(element("h4", "", `${String(index + 1).padStart(2, "0")} · ${entry.title || "그래프 조회"}`), element("span", "trace-rows", count === undefined ? "행 수 미제공" : `${count}개 행 반환`));
      section.append(heading, element("pre", "trace-code", entry.cypher || "조회문 미제공"), element("div", "trace-label", "PARAMETERS"), element("pre", "trace-code", JSON.stringify(entry.parameters || {}, null, 2)));
      if (Array.isArray(entry.rows)) {
        const details = element("details");
        details.append(element("summary", "", "실제 반환 데이터 보기"), element("pre", "trace-code", JSON.stringify(entry.rows, null, 2)));
        section.append(details);
      }
      $("trace-list").append(section);
    });
  }

  function renderRetrieval(data) {
    state.retrieval = data;
    state.highlighted = true;
    state.selectedNode = null;
    $("node-detail").replaceChildren(icon("pointer"), element("p", "", "강조된 연결은 이번 검색에서 사용한 근거입니다. 노드를 선택해 확인하세요."));
    $("answer-empty").hidden = true;
    $("answer-content").textContent = data.answer || "근거 조회를 완료했습니다. 아래 사실과 원문을 확인하세요. LLM이 연결되어 있다면 ‘답변 생성’으로 자연어 답변을 만들 수 있습니다.";
    $("answer-content").hidden = false;
    $("answer-label").textContent = data.answer ? "근거 기반 생성 답변" : "그래프 검색 결과";
    $("facts-list").replaceChildren();
    for (const fact of data.facts || []) $("facts-list").append(element("li", "", typeof fact === "string" ? fact : JSON.stringify(fact)));
    $("facts-content").hidden = !(data.facts || []).length;
    $("citation-warning").textContent = data.citation_warning || "";
    $("citation-warning").hidden = !data.citation_warning;
    const metadata = [];
    if (data.service?.name) metadata.push(data.service.name);
    if (data.intent) metadata.push(data.intent === "impact" ? "의존 관계 · 영향 범위" : "담당팀 · 관련 문서");
    if (typeof data.retrieval_ms === "number") metadata.push(`조회 ${(data.retrieval_ms / 1000).toFixed(2)}초`);
    if (typeof data.generation_ms === "number") metadata.push(`생성 ${(data.generation_ms / 1000).toFixed(1)}초`);
    if (data.model) metadata.push(data.model);
    const scopes = { self_and_direct_dependencies: "범위: 기준 서비스 + 직접 의존 서비스", self_and_inbound_dependencies_up_to_5_hops: "범위: 기준 서비스 + 최대 5단계 역방향 의존 관계" };
    if (scopes[data.scope]) metadata.push(scopes[data.scope]);
    const resultScope = data.intent === "impact" ? "역방향 최대 5홉 · 잠재 영향 후보" : "직접 의존 1홉 · 담당팀과 문서";
    const queriedAt = new Date().toLocaleTimeString("ko-KR", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    $("result-summary").textContent = `${data.service?.name || data.service?.id || "선택 서비스"} · ${resultScope} · ${queriedAt} 조회 완료`;
    $("result-summary").title = data.question || "";
    $("result-summary").hidden = false;
    $("answer-meta").textContent = metadata.join(" · ");
    $("answer-meta").hidden = metadata.length === 0;
    renderSources(data.sources || []);
    renderTrace(data.trace || []);
    renderGraph();
  }

  async function submit(mode, previousQuery = null) {
    if (state.busy || state.refreshing || !state.status?.neo4j?.ok) return;
    const question = $("question").value.trim();
    if (!question) { $("question").setCustomValidity("궁금한 내용을 입력해 주세요."); $("question").reportValidity(); $("question").focus(); return; }
    $("question").setCustomValidity("");
    if (!$("question-form").reportValidity()) return;
    const payload = previousQuery || { question, service_id: $("service-id").value, intent: $("intent").value };
    lastQuery = { ...payload };
    const requestedRevision = documentRevision;
    state.busy = true;
    updateControls();
    setWorkflow("loading", mode === "ask" ? "근거 조회 · 답변 생성 중" : "관계와 문서 조회 중");
    $("request-error").hidden = true;
    $("request-progress").hidden = false;
    $("result-announcement").textContent = "";
    const started = performance.now();
    const progress = () => { $("progress-text").textContent = `${mode === "ask" ? "근거 조회 및 답변 생성 요청 중" : "그래프와 문서 조회 중"} · ${Math.floor((performance.now() - started) / 1000)}초 경과${mode === "ask" ? ". 모델에 따라 시간이 걸릴 수 있습니다." : ""}`; };
    progress();
    const timer = window.setInterval(progress, 1000);
    try {
      const data = await fetchJSON(`/api/graphrag/${mode}/`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value }, body: JSON.stringify(payload) }, 240000);
      if (requestedRevision !== documentRevision) return;
      renderRetrieval(data);
      setWorkflow("done", mode === "ask" ? "답변 생성 완료" : "근거 조회 완료");
      $("result-announcement").textContent = `${mode === "ask" ? "답변 생성을" : "근거 조회를"} 완료했습니다. 근거 문서 ${(data.sources || []).length}개를 찾았습니다.`;
    } catch (error) {
      if (requestedRevision !== documentRevision) return;
      if (error.data?.retrieval) renderRetrieval(error.data.retrieval);
      setWorkflow("error", error.data?.retrieval ? "근거 조회 완료 · 답변 생성 실패" : "요청 실패 · 안내 확인");
      $("request-error").textContent = error.message;
      $("request-error").hidden = false;
      if (!error.data?.retrieval && state.retrieval) $("answer-label").textContent = "이전 조회 결과 · 현재 요청 실패";
      $("result-announcement").textContent = "요청을 완료하지 못했습니다. 답변 영역의 안내를 확인해 주세요.";
    } finally {
      window.clearInterval(timer);
      $("request-progress").hidden = true;
      state.busy = false;
      updateControls();
      if (graphRevisionChanged) { graphRevisionChanged = false; refresh(); }
    }
  }

  function documentsChanged() {
    documentRevision += 1;
    refreshQuery = Boolean(lastQuery);
    state.retrieval = null;
    state.highlighted = false;
    state.selectedNode = null;
    $("answer-empty").hidden = true;
    $("answer-content").hidden = false;
    $("answer-content").textContent = "문서가 변경되어 이전 답변과 근거를 지웠습니다. 최신 그래프를 확인하고 근거를 다시 조회합니다. 자연어 답변은 ‘답변 생성’을 눌러 갱신하세요.";
    $("answer-label").textContent = "문서 변경 · 최신 근거 확인 중";
    for (const id of ["answer-meta", "result-summary", "facts-content", "citation-warning", "request-error"]) $(id).hidden = true;
    for (const id of ["facts-list", "sources-list", "trace-list", "graph-edges-list"]) $(id).replaceChildren();
    $("source-count").textContent = "0";
    $("trace-count").textContent = "0";
    $("clear-highlight").hidden = true;
    $("node-detail").replaceChildren(icon("pointer"), element("p", "", "변경된 그래프를 확인하고 있습니다."));
    $("graph-canvas").hidden = true;
    $("result-announcement").textContent = "문서 변경을 감지했습니다. 이전 답변을 지우고 최신 근거를 조회합니다.";
    if (state.busy || state.refreshing) graphRevisionChanged = true;
    else refresh();
  }

  function activateTab(id, focus = false) {
    for (const key of ["graph", "trace"]) {
      const active = key === id;
      $(`${key}-tab`).setAttribute("aria-selected", String(active));
      $(`${key}-tab`).tabIndex = active ? 0 : -1;
      $(`${key}-tab`).classList.toggle("active", active);
      $(`${key}-view`).hidden = !active;
    }
    if (focus) $(`${id}-tab`).focus();
  }

  $("question-form").addEventListener("submit", (event) => { event.preventDefault(); if (!$("retrieve-button").disabled) submit("retrieve"); });
  $("ask-button").addEventListener("click", () => submit("ask"));
  $("refresh-status").addEventListener("click", refresh);
  $("question").addEventListener("input", () => {
    $("question").setCustomValidity("");
    $("character-count").textContent = `${$("question").value.length.toLocaleString("ko-KR")} / 2,000`;
    setExampleSelection();
  });
  $("question").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.isComposing) {
      event.preventDefault();
      if (!$("retrieve-button").disabled) $("question-form").requestSubmit($("retrieve-button"));
    }
  });
  $("intent").addEventListener("change", () => { updateIntentHint(); setExampleSelection(); });
  $("service-id").addEventListener("change", () => setExampleSelection());
  for (const button of document.querySelectorAll(".example-button")) button.addEventListener("click", () => {
    $("question").value = button.dataset.question;
    $("question").dispatchEvent(new Event("input"));
    const exists = [...$("service-id").options].some((option) => option.value === button.dataset.service);
    $("service-id").value = exists ? button.dataset.service : "";
    $("intent").value = button.dataset.intent;
    setExampleSelection(button);
    updateIntentHint();
    $("question").focus();
  });
  for (const key of ["graph", "trace"]) {
    $(`${key}-tab`).addEventListener("click", () => activateTab(key));
    $(`${key}-tab`).addEventListener("keydown", (event) => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) { event.preventDefault(); activateTab(event.key === "Home" ? "graph" : event.key === "End" ? "trace" : key === "graph" ? "trace" : "graph", true); } });
  }
  $("graph-nav").addEventListener("click", () => activateTab("graph", true));
  $("trace-nav").addEventListener("click", () => activateTab("trace", true));
  $("zoom-in").addEventListener("click", () => { state.zoom = Math.min(150, state.zoom + 25); updateZoom(); });
  $("zoom-out").addEventListener("click", () => { state.zoom = Math.max(75, state.zoom - 25); updateZoom(); });
  $("zoom-reset").addEventListener("click", () => {
    state.zoom = 100;
    $("graph-canvas").scrollTo({ top: 0, left: 0 });
    updateZoom();
  });
  $("clear-highlight").addEventListener("click", () => { state.highlighted = !state.highlighted; renderGraph(); });
  setExampleSelection();
  updateIntentHint();
  window.addEventListener("storage", (event) => {
    if (event.key !== "graphlab-document-revision") return;
    documentsChanged();
  });
  window.addEventListener("pageshow", (event) => { if (event.persisted) documentsChanged(); });
  refresh();
})();

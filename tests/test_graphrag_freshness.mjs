/* Run: node --test tests/test_graphrag_freshness.mjs
   Exercise the real browser script with a minimal DOM and delayed HTTP replies. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

test("document mutation discards an in-flight answer and retrieves fresh evidence without another LLM call", async () => {
  const writes = [];
  class Element {
    constructor(id = "") {
      this.id = id; this.value = ""; this.children = []; this.events = {};
      this.dataset = {}; this.style = { setProperty() {} };
      this.classList = { toggle() {} }; this._text = "";
    }
    set textContent(value) { this._text = value; writes.push([this.id, value]); }
    get textContent() { return this._text; }
    append(...items) { this.children.push(...items); }
    replaceChildren(...items) { this.children = items; }
    get firstElementChild() { return this.children[0]; }
    get options() { return this.children; }
    setAttribute() {}
    removeAttribute() {}
    querySelectorAll() { return []; }
    addEventListener(name, callback) { this.events[name] = callback; }
    dispatchEvent(event) { this.events[event.type]?.(event); }
    setCustomValidity() {}
    reportValidity() { return true; }
    focus() {}
  }
  const elements = new Map();
  const get = (id) => { if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); };
  const events = {};
  const calls = [];
  let finishOldAnswer;
  const response = (data) => ({ ok: true, json: async () => data });
  const status = { neo4j: { ok: true }, llm: { ok: true }, services: [{ id: "svc", name: "서비스" }] };
  const fetch = async (url) => {
    calls.push(url);
    if (url.endsWith("/ask/")) return new Promise((resolve) => { finishOldAnswer = resolve; });
    if (url.endsWith("/status/")) return response(status);
    if (url === "/api/graph/") return response({ nodes: [], edges: [] });
    if (url.endsWith("/retrieve/")) return response({ sources: [], facts: ["updated fact"], trace: [], graph: { nodes: [], edges: [] } });
    throw new Error(`Unexpected request ${url}`);
  };
  get("question").value = "서비스 담당팀은?";
  get("service-id").value = "svc";
  get("intent").value = "context";
  const context = vm.createContext({
    document: { getElementById: get, createElement: () => new Element(), createElementNS: () => new Element(),
      querySelectorAll: () => [], querySelector: () => ({ value: "csrf" }), createTextNode: (text) => text },
    window: { location: { search: "" }, setTimeout, clearTimeout, setInterval, clearInterval,
      addEventListener: (name, callback) => { events[name] = callback; } },
    fetch, URLSearchParams, AbortController, performance, Event, console,
  });
  vm.runInContext(readFileSync(new URL("../graphlab/static/graphlab/graphrag.js", import.meta.url), "utf8"), context);
  const settle = async () => { for (let n = 0; n < 12; n++) await new Promise(setImmediate); };
  await settle();
  const pending = get("ask-button").events.click();
  await settle();
  assert.equal(typeof finishOldAnswer, "function");
  events.storage({ key: "graphlab-document-revision" });
  assert.match(get("answer-content").textContent, /이전 답변과 근거를 지웠습니다/);
  assert.equal(get("sources-list").children.length, 0);
  finishOldAnswer(response({ answer: "STALE SECRET ANSWER", sources: [], facts: [], trace: [], graph: { nodes: [], edges: [] } }));
  await pending;
  await settle();
  assert.equal(writes.some(([, value]) => String(value).includes("STALE SECRET ANSWER")), false);
  assert.equal(calls.filter((url) => url.endsWith("/ask/")).length, 1);
  assert.equal(calls.filter((url) => url.endsWith("/retrieve/")).length, 1);
  assert.equal(get("facts-list").children[0].textContent, "updated fact");
});

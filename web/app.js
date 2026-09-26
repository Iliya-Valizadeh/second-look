// The JS half of the web door's JS/Python glue (ADR 0001, ADR 0004).
//
// This file owns every bit of file reading and CSV splitting into rows for the
// page: it reads the file the user picks with the browser's File API, and hands
// its bytes to Python. It never reimplements column mapping or flag detection;
// those calls go straight to `bridge.py`, which calls the same `second_look`
// functions the command line uses.
//
// Pyodide runs on the page's main thread, not a worker, so the page's own CSP
// meta tag covers everything it does (ADR 0004).

import { loadPyodide } from "./pyodide/pyodide.mjs";

const FLAG_LABELS = {
  recurring: "Recurring charge",
  price_increase: "Price increase",
  duplicate: "Possible duplicate",
  unusual: "Worth a second look",
};

const state = {
  pyodide: null,
  bridge: {},
  rawBuffer: null,
  flags: [],
  summary: null,
  feedback: new Map(), // flag index -> "right" | "wrong" | "not_sure"
};

const el = (id) => document.getElementById(id);

function setStatus(text) {
  el("status").textContent = text;
}

function showScreen(name) {
  for (const screen of ["screen-picker", "screen-mapping", "screen-results"]) {
    el(screen).hidden = screen !== name;
  }
  const headingId = { "screen-picker": "picker-heading", "screen-mapping": "mapping-heading", "screen-results": "results-heading" }[name];
  const heading = el(headingId);
  if (heading) {
    heading.setAttribute("tabindex", "-1");
    heading.focus();
  }
}

// ---- Pyodide / bridge setup -------------------------------------------------

async function initPyodide() {
  setStatus("Loading Python, about 13.5 MB, only the first time…");
  const pyodide = await loadPyodide({ indexURL: "./pyodide/" });

  const manifest = await (await fetch("./dist/manifest.json")).json();
  await pyodide.loadPackage(`./dist/${manifest.wheel}`);

  const bridgeSource = await (await fetch("./bridge.py")).text();
  pyodide.runPython(bridgeSource);

  state.pyodide = pyodide;
  for (const name of ["preview_rows", "analyze", "not_advice_footer", "section_title", "tool_version"]) {
    state.bridge[name] = pyodide.globals.get(name);
  }

  el("not-advice-footer").textContent = state.bridge.not_advice_footer();
  el("results-heading").textContent = `3. ${state.bridge.section_title()}`;

  const cspMeta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
  el("csp-value").textContent = cspMeta ? cspMeta.getAttribute("content") : "(not found)";

  setStatus("Ready. Choose a statement CSV to begin.");
}

// ---- Screen 1: file picker ---------------------------------------------------

function showPickerError(message) {
  const p = el("picker-error");
  p.textContent = message;
  p.hidden = false;
}

function clearPickerError() {
  el("picker-error").hidden = true;
  el("picker-error").textContent = "";
}

async function handleFile(file) {
  clearPickerError();
  if (!file) {
    return;
  }
  if (!/\.csv$/i.test(file.name) && file.type && file.type !== "text/csv") {
    showPickerError("Please choose a .csv file.");
    return;
  }
  setStatus(`Reading ${file.name}…`);
  state.rawBuffer = await file.arrayBuffer();
  try {
    const previewJson = state.bridge.preview_rows(new Uint8Array(state.rawBuffer));
    const preview = JSON.parse(previewJson);
    buildMappingScreen(preview);
    setStatus(`Read ${file.name}. Now match its columns.`);
    showScreen("screen-mapping");
  } catch (err) {
    showPickerError(`Could not read this file: ${err.message}`);
    setStatus("Ready. Choose a statement CSV to begin.");
  }
}

function wirePicker() {
  const dropZone = el("drop-zone");
  const fileInput = el("file-input");

  fileInput.addEventListener("change", () => handleFile(fileInput.files[0]));

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    handleFile(file);
  });
}

// ---- Screen 2: column mapping ------------------------------------------------

let lastPreview = null;

function columnOptions(preview, hasHeader) {
  const rows = preview.rows;
  const width = rows.reduce((max, row) => Math.max(max, row.length), 0);
  if (hasHeader && rows.length > 0) {
    return rows[0].map((name, i) => ({
      value: name && name.trim() ? name : String(i),
      label: name && name.trim() ? name : `Column ${i}`,
    }));
  }
  return Array.from({ length: width }, (_, i) => ({ value: String(i), label: `Column ${i}` }));
}

function fillSelect(select, options, { withNone = false, preferLabel = null } = {}) {
  select.innerHTML = "";
  if (withNone) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(none)";
    select.appendChild(opt);
  }
  for (const { value, label } of options) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
  }
  // ADR 0003: header words may suggest a column, but this is a suggestion only,
  // never a guessed sign convention, and the user always sees and can change it.
  if (preferLabel) {
    const match = options.find((o) => preferLabel.test(o.label));
    if (match) {
      select.value = match.value;
    }
  }
}

function renderPreviewTable(preview, hasHeader) {
  const head = el("preview-head");
  const body = el("preview-body");
  head.innerHTML = "";
  body.innerHTML = "";
  const dataRows = hasHeader ? preview.rows.slice(1) : preview.rows;
  const headerRow = hasHeader && preview.rows.length > 0 ? preview.rows[0] : null;
  const width = preview.rows.reduce((max, row) => Math.max(max, row.length), 0);

  for (let i = 0; i < width; i++) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = headerRow ? headerRow[i] || `Column ${i}` : `Column ${i}`;
    head.appendChild(th);
  }
  for (const row of dataRows.slice(0, 5)) {
    const tr = document.createElement("tr");
    for (let i = 0; i < width; i++) {
      const td = document.createElement("td");
      td.textContent = row[i] ?? "";
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
}

function buildMappingScreen(preview) {
  lastPreview = preview;
  refreshMappingColumns();
}

function refreshMappingColumns() {
  const hasHeader = el("has-header").checked;
  const options = columnOptions(lastPreview, hasHeader);

  fillSelect(el("date-column"), options, { preferLabel: /^date$/i });
  fillSelect(el("category-column"), options, { withNone: true, preferLabel: /^category$/i });
  fillSelect(el("amount-column"), options, { preferLabel: /^amount$/i });
  fillSelect(el("debit-column"), options, { preferLabel: /^debit$/i });
  fillSelect(el("credit-column"), options, { preferLabel: /^credit$/i });

  const container = el("description-columns");
  container.innerHTML = "";
  const hasDescriptionMatch = options.some((o) => /description/i.test(o.label));
  options.forEach(({ value, label }, i) => {
    const id = `desc-col-${i}`;
    const wrap = document.createElement("div");
    wrap.className = "field";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = id;
    checkbox.value = value;
    const suggested = hasDescriptionMatch ? /description/i.test(label) : i === 0;
    if (suggested) {
      checkbox.checked = true;
    }
    const labelEl = document.createElement("label");
    labelEl.setAttribute("for", id);
    labelEl.textContent = label;
    wrap.appendChild(checkbox);
    wrap.appendChild(labelEl);
    container.appendChild(wrap);
  });

  renderPreviewTable(lastPreview, hasHeader);
}

function wireMapping() {
  el("has-header").addEventListener("change", refreshMappingColumns);

  for (const name of ["amount-shape-single", "amount-shape-split"]) {
    el(name).addEventListener("change", () => {
      const single = el("amount-shape-single").checked;
      el("amount-single-fields").hidden = !single;
      el("amount-split-fields").hidden = single;
    });
  }

  el("mapping-back").addEventListener("click", () => {
    showScreen("screen-picker");
    setStatus("Ready. Choose a statement CSV to begin.");
  });

  el("mapping-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitMapping();
  });
}

function showMappingError(message) {
  const p = el("mapping-error");
  p.textContent = message;
  p.hidden = false;
}

function clearMappingError() {
  el("mapping-error").hidden = true;
  el("mapping-error").textContent = "";
}

function buildMappingPayload() {
  const descriptionColumns = Array.from(
    document.querySelectorAll("#description-columns input:checked")
  ).map((cb) => cb.value);

  const single = el("amount-shape-single").checked;

  return {
    has_header: el("has-header").checked,
    date_column: el("date-column").value,
    date_format: el("date-format").value,
    description_columns: descriptionColumns,
    amount_column: single ? el("amount-column").value : null,
    sign_convention: single
      ? document.querySelector('input[name="sign-convention"]:checked').value
      : null,
    debit_column: single ? null : el("debit-column").value,
    credit_column: single ? null : el("credit-column").value,
    category_column: el("category-column").value || null,
    decimal_separator: el("decimal-separator").value,
  };
}

function submitMapping() {
  clearMappingError();
  const mapping = buildMappingPayload();
  if (mapping.description_columns.length === 0) {
    showMappingError("Check at least one description column.");
    return;
  }

  setStatus("Running the detection rules…");
  let resultJson;
  try {
    resultJson = state.bridge.analyze(new Uint8Array(state.rawBuffer), JSON.stringify(mapping));
  } catch (err) {
    showMappingError(`Could not run this file with this mapping: ${err.message}`);
    setStatus("Fix the column mapping and try again.");
    return;
  }
  const result = JSON.parse(resultJson);
  if (result.error) {
    showMappingError(result.error);
    setStatus("Fix the column mapping and try again.");
    return;
  }

  state.flags = result.flags;
  state.summary = result.summary;
  state.feedback = new Map();
  renderResults(result);
  setStatus("Done. Results are ready below.");
  showScreen("screen-results");
}

// ---- Screen 3: results --------------------------------------------------------

function formatMoney(value) {
  if (value === null || value === undefined) {
    return null;
  }
  const num = Number(value);
  return `$${num.toFixed(2)}`;
}

function renderResults(result) {
  const list = el("results-list");
  list.innerHTML = "";

  el("results-summary").textContent =
    `Read ${result.summary.rows_read} rows, used ${result.summary.rows_used}, ` +
    `skipped ${result.summary.skipped.length}.`;

  el("results-empty").hidden = result.flags.length !== 0;

  result.flags.forEach((flag, index) => {
    list.appendChild(renderFlagCard(flag, index));
  });
}

function renderFlagCard(flag, index) {
  const li = document.createElement("li");
  li.className = "flag-card";
  li.dataset.flagType = flag.type;

  const label = document.createElement("p");
  label.className = "flag-type-label";
  const dot = document.createElement("span");
  dot.className = "flag-type-dot";
  dot.setAttribute("aria-hidden", "true");
  label.appendChild(dot);
  label.appendChild(document.createTextNode(FLAG_LABELS[flag.type] || flag.type));
  li.appendChild(label);

  const reason = document.createElement("p");
  reason.className = "flag-reason";
  reason.textContent = flag.reason;
  li.appendChild(reason);

  if (flag.type === "recurring") {
    const dl = document.createElement("dl");
    dl.className = "flag-yearly-cost";
    const dt = document.createElement("dt");
    dt.textContent = "Yearly cost:";
    const dd = document.createElement("dd");
    const cost = formatMoney(flag.yearly_cost);
    dd.textContent = cost ? `${cost} a year` : "Not active now, so no ongoing yearly cost.";
    dl.appendChild(dt);
    dl.appendChild(dd);
    li.appendChild(dl);
  }

  li.appendChild(renderFeedbackFieldset(flag, index));
  return li;
}

function renderFeedbackFieldset(flag, index) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "flag-feedback";
  const legend = document.createElement("legend");
  legend.textContent = "Is this flag right?";
  fieldset.appendChild(legend);

  for (const [value, text] of [
    ["right", "Right"],
    ["wrong", "Wrong"],
    ["not_sure", "Not sure"],
  ]) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const id = `feedback-${index}-${value}`;
    const input = document.createElement("input");
    input.type = "radio";
    input.name = `feedback-${index}`;
    input.id = id;
    input.value = value;
    input.addEventListener("change", () => state.feedback.set(index, value));
    const labelEl = document.createElement("label");
    labelEl.setAttribute("for", id);
    labelEl.textContent = text;
    wrap.appendChild(input);
    wrap.appendChild(labelEl);
    fieldset.appendChild(wrap);
  }
  return fieldset;
}

// ---- Feedback export ----------------------------------------------------------

function buildFeedbackFile() {
  const includeMerchant = el("include-merchant-names").checked;
  const marked = [];
  for (const [index, choice] of state.feedback.entries()) {
    const flag = state.flags[index];
    if (!flag) {
      continue;
    }
    const entry = { type: flag.type, rule: flag.type, choice };
    if (flag.period) {
      entry.period = flag.period;
    }
    if (typeof flag.count === "number") {
      entry.count = flag.count;
    }
    if (typeof flag.active === "boolean") {
      entry.active = flag.active;
    }
    if (includeMerchant && flag.merchant) {
      entry.merchant = flag.merchant;
    }
    marked.push(entry);
  }
  return {
    tool_version: state.bridge.tool_version(),
    flags: marked,
  };
}

function wireFeedbackExport() {
  el("save-feedback").addEventListener("click", () => {
    const data = buildFeedbackFile();
    if (data.flags.length === 0) {
      el("feedback-status").textContent = "Mark at least one flag above before saving.";
      return;
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "second-look-feedback.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    el("feedback-status").textContent = `Saved a file with ${data.flags.length} marked flag(s) to your downloads.`;
  });

  el("results-back").addEventListener("click", () => {
    showScreen("screen-picker");
    el("file-input").value = "";
    setStatus("Ready. Choose a statement CSV to begin.");
  });
}

// ---- Startup -------------------------------------------------------------------

async function main() {
  wirePicker();
  wireMapping();
  wireFeedbackExport();
  try {
    await initPyodide();
  } catch (err) {
    setStatus(`Could not start Python: ${err.message}`);
    showPickerError("This page could not start. Reloading may help.");
  }
}

main();

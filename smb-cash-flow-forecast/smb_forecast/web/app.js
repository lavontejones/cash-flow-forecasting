"use strict";

let documentInput = null;
let output = null;
let activeScenario = "base";
let busy = false;
const palette = ["#2563eb", "#d97706", "#059669", "#7c3aed", "#dc2626"];
const byId = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
const definitions = [
  ["start_month", "First forecast month", "revenue-fields", "text", "YYYY-MM; edit in base scenario only."],
  ["months", "Forecast months", "revenue-fields", "integer", "1–60 months; edit in base scenario only."],
  ["monthly_revenue", "Monthly revenue", "revenue-fields", "number", "Before seasonality; first forecast month."],
  ["monthly_growth_rate", "Monthly growth (%)", "revenue-fields", "percent", "Compounds monthly on unseasoned revenue."],
  ["cost_basis", "Cost input", "revenue-fields", "select", "Gross margin or COGS share; exactly one."],
  ["cost_rate", "Margin / COGS share (%)", "revenue-fields", "percent", "Uses the cost input selected above."],
  ["fixed_opex", "Fixed operating expenses / month", "cost-fields", "number", "Excludes payroll, COGS, and interest."],
  ["variable_opex_rate", "Variable operating expenses (%)", "cost-fields", "percent", "Share of revenue; separate from COGS."],
  ["payroll", "Existing payroll / month", "cost-fields", "number", "Fully loaded cost, excluding planned hires."],
  ["beginning_cash", "Beginning cash", "cost-fields", "number", "Cash immediately before the first forecast month."],
  ["tax_rate", "Assumed tax rate (%)", "cost-fields", "percent", "Applied to positive operating income less interest."],
  ["seasonality", "Calendar seasonality factors", "timing-fields", "list", "12 factors, Jan–Dec. A factor of 1 means no seasonal adjustment."],
  ["collection_weights", "Customer collection fractions", "timing-fields", "list", "Month 0, 1, 2…; must total 1. Example: 0.4, 0.4, 0.2."],
  ["payment_weights", "Supplier payment fractions", "timing-fields", "list", "COGS only. Month 0, 1, 2…; must total 1."],
  ["opening_ar", "Opening receivables collections", "timing-fields", "list", "Amounts due in forecast month 1, 2…; blank means zero."],
  ["opening_ap", "Opening payables payments", "timing-fields", "list", "Amounts payable in forecast month 1, 2…; blank means zero."],
  ["tax_lag_months", "Tax payment lag (months)", "timing-fields", "integer", "0 means the month accrued; up to 12 months."],
  ["opening_tax_payments", "Opening taxes payment schedule", "timing-fields", "list", "Amounts due in forecast month 1, 2…; blank means zero."],
  ["hires", "Planned hires", "schedule-fields", "json", '[{"name":"New role","start_month":"2027-07","monthly_cost":6500}]'],
  ["capex", "Capital expenditures", "schedule-fields", "json", 'Month → amount. Example: {"2027-03":18000}'],
  ["opening_debt", "Opening debt balance", "schedule-fields", "number", "Used to validate principal payments."],
  ["debt_draws", "Debt draws", "schedule-fields", "json", 'Month → cash borrowed. Example: {"2027-05":10000}'],
  ["debt_principal", "Debt principal payments", "schedule-fields", "json", "Month → principal repaid; cannot exceed debt balance."],
  ["debt_interest", "Debt interest payments", "schedule-fields", "json", "Month → interest; explicit user assumptions."],
  ["revenue_overrides", "Monthly revenue overrides", "schedule-fields", "json", "Month → final revenue, replacing growth and seasonality for that month."],
];

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function normalized(value, key = "") {
  if (key === "name") return value;
  if (Array.isArray(value)) return value.map(normalized);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, normalized(v, k)]));
  if (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return value;
}

function initializeFields() {
  for (const [key, label, group, type, hint] of definitions) {
    const wrapper = element("label", label);
    let input;
    if (type === "json") input = element("textarea");
    else if (type === "select") {
      input = element("select");
      for (const [value, text] of [["gross_margin", "Gross margin"], ["cogs_rate", "COGS share"]]) {
        const option = element("option", text); option.value = value; input.append(option);
      }
    } else {
      input = element("input");
      input.type = ["number", "percent", "integer"].includes(type) ? "number" : "text";
      if (input.type === "number") input.step = type === "integer" ? "1" : "any";
    }
    input.id = `input-${key}`;
    wrapper.append(input);
    byId(group).append(wrapper, element("p", hint, "field-hint"));
  }
  byId("input-cost_basis").addEventListener("change", event => {
    const field = byId("input-cost_rate");
    const current = Number(field.value);
    if (Number.isFinite(current)) field.value = String(100 - current);
  });
}

function fillFields() {
  const a = normalized(output.scenarios[activeScenario].assumptions);
  for (const [key, , , type] of definitions) {
    let value = a[key];
    if (key === "cost_basis") value = "gross_margin" in a ? "gross_margin" : "cogs_rate";
    if (key === "cost_rate") value = a.gross_margin ?? a.cogs_rate;
    byId(`input-${key}`).value = type === "json" ? JSON.stringify(value, null, 2)
      : type === "list" ? value.join(", ")
      : type === "percent" ? String(Number((value * 100).toPrecision(12))) : String(value);
    byId(`input-${key}`).disabled = activeScenario !== "base" && ["start_month", "months"].includes(key);
  }
}

function readForm() {
  const candidate = clone(documentInput);
  candidate.assumptions = candidate.assumptions || {};
  candidate.scenarios = candidate.scenarios || {};
  const original = normalized(output.scenarios[activeScenario].assumptions);
  const changes = {};
  for (const [key, , , type] of definitions) {
    if (key === "cost_basis") continue;
    if (activeScenario !== "base" && ["start_month", "months"].includes(key)) continue;
    const text = byId(`input-${key}`).value.trim();
    let value;
    if (type === "json") {
      try { value = JSON.parse(text); } catch (_) { throw new Error(`${key}: invalid JSON`); }
    } else if (type === "list") {
      value = text === "" ? [] : text.split(",").map(item => {
        if (!item.trim() || !Number.isFinite(Number(item))) throw new Error(`${key}: invalid number list`);
        return Number(item);
      });
    } else if (type === "text") value = text;
    else {
      if (!text || !Number.isFinite(Number(text))) throw new Error(`${key}: enter a finite number`);
      value = Number(text);
      if (type === "percent") value /= 100;
    }
    const actualKey = key === "cost_rate" ? byId("input-cost_basis").value : key;
    if (JSON.stringify(value) !== JSON.stringify(original[actualKey])) changes[actualKey] = value;
  }
  const target = activeScenario === "base" ? candidate.assumptions : candidate.scenarios[activeScenario];
  if ("gross_margin" in changes) delete target.cogs_rate;
  if ("cogs_rate" in changes) delete target.gross_margin;
  Object.assign(target, changes);
  return candidate;
}

function status(text, error = false) {
  byId("status").textContent = text;
  byId("status").className = error ? "error" : "";
}

function setBusy(value) {
  busy = value;
  byId("scenario").disabled = value;
  document.querySelectorAll("button").forEach(button => { button.disabled = value || (!output && ["csv", "report", "save-input"].includes(button.id)); });
}

async function calculate(candidate, rawText = null) {
  setBusy(true);
  try {
    const response = await fetch("/api/forecast", {method:"POST", headers:{"Content-Type":"application/json"}, body:rawText ?? JSON.stringify(candidate)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    documentInput = candidate;
    output = data;
    if (!(activeScenario in output.scenarios)) activeScenario = "base";
    const select = byId("scenario"); select.replaceChildren();
    for (const name of Object.keys(output.scenarios)) { const option = element("option", name); option.value = name; select.append(option); }
    select.value = activeScenario;
    fillFields(); render();
    status(`Calculated ${Object.keys(data.scenarios).length} scenarios. Every monthly cash reconciliation passed. Amounts in ${data.currency}.`);
  } catch (error) { status(error.message, true); }
  finally { setBusy(false); }
}

function amount(value) { return Number(value).toLocaleString("en-US", {maximumFractionDigits:0}); }
function svgNode(tag, attrs = {}, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}

function drawChart(target, series, labels, description) {
  const width = 900, height = 250, left = 88, top = 15, pw = 790, ph = 196;
  let low = Math.min(0, ...series.flatMap(s => s.values)), high = Math.max(0, ...series.flatMap(s => s.values));
  if (high === low) high = low + 1;
  const padding = (high - low) * .08; low -= padding; high += padding;
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`, role:"img", "aria-label":description});
  svg.append(svgNode("title", {}, description));
  for (let i = 0; i < 5; i++) {
    const y = top + ph * (1-i/4), value = low + (high-low)*i/4;
    svg.append(svgNode("line", {x1:left,y1:y,x2:left+pw,y2:y,stroke:"#e2e8f0"}));
    svg.append(svgNode("text", {x:left-10,y:y+4,"text-anchor":"end",fill:"#64748b","font-size":11}, amount(value)));
  }
  const zeroY = top + ph * high/(high-low);
  svg.append(svgNode("line", {x1:left,y1:zeroY,x2:left+pw,y2:zeroY,stroke:"#94a3b8","stroke-dasharray":"4 4"}));
  for (const s of series) {
    const points = s.values.map((v,i) => `${left+pw*i/Math.max(1,labels.length-1)},${top+ph*(high-v)/(high-low)}`).join(" ");
    const line = svgNode("polyline", {points,fill:"none",stroke:s.color,"stroke-width":2.6});
    line.append(svgNode("title", {}, s.name)); svg.append(line);
    if (labels.length === 1) svg.append(svgNode("circle", {cx:left,cy:top+ph*(high-s.values[0])/(high-low),r:4,fill:s.color}));
  }
  const ticks = [...new Set([0,Math.floor((labels.length-1)/2),labels.length-1])];
  for (const i of ticks) svg.append(svgNode("text", {x:left+pw*i/Math.max(1,labels.length-1),y:height-12,"text-anchor":"middle",fill:"#64748b","font-size":11}, labels[i]));
  byId(target).replaceChildren(svg);
}

function render() {
  const selected = output.scenarios[activeScenario], summary = selected.summary, rows = selected.months;
  byId("model-name").textContent = documentInput.model_name || "Monthly Operating Plan";
  byId("active-name").textContent = `${activeScenario.charAt(0).toUpperCase()+activeScenario.slice(1)} scenario`;
  byId("currency").textContent = output.currency;
  const kpis = byId("kpis"); kpis.replaceChildren();
  const baseCash = Number(output.scenarios.base.summary.ending_cash);
  const runway = summary.cash_runway_months === null ? "No recent burn" : `${summary.cash_runway_months} mo`;
  for (const [label,value,detail,negative] of [
    ["Forecast revenue",amount(summary.total_revenue),`${rows[0].month} → ${rows.at ? rows.at(-1).month : rows[rows.length-1].month}`,false],
    ["Ending cash",amount(summary.ending_cash),`${amount(Number(summary.ending_cash)-baseCash)} vs base`,Number(summary.ending_cash)<0],
    ["Lowest month-end cash",amount(summary.minimum_ending_cash),summary.first_negative_cash_month ? `First deficit: ${summary.first_negative_cash_month}` : "No deficit within forecast",Number(summary.minimum_ending_cash)<0],
    ["Cash runway",runway,"Trailing burn heuristic at horizon end",false],
  ]) {
    const card = element("div",undefined,"kpi");
    card.append(element("div",label,"kpi-label"),element("div",value,`kpi-value${negative?" negative":""}`),element("div",detail,"kpi-detail"));
    kpis.append(card);
  }
  const series = Object.entries(output.scenarios).map(([name,r],i)=>({name,values:r.months.map(row=>Number(row.ending_cash)),color:palette[i%palette.length]}));
  drawChart("cash-chart",series,rows.map(row=>row.month),"Monthly ending cash across scenarios");
  const legend = byId("legend"); legend.replaceChildren();
  series.forEach(s => { const entry = element("span",s.name); entry.style.color=s.color; legend.append(entry); });
  drawChart("profit-chart",[{name:"Revenue",values:rows.map(r=>Number(r.revenue)),color:palette[0]},{name:"Operating income",values:rows.map(r=>Number(r.operating_income)),color:palette[2]}],rows.map(r=>r.month),"Monthly revenue and operating income in the selected scenario");
  const fields = [["month","Month"],["revenue","Revenue"],["gross_profit","Gross profit"],["operating_expenses","Op. expenses"],["operating_income","Op. income"],["cash_inflows","Cash in"],["cash_outflows","Cash out"],["ending_cash","Ending cash"],["break_even_revenue","Break-even revenue"],["ending_cash_variance","Cash vs base"]];
  const head = document.querySelector("#monthly thead"), body = document.querySelector("#monthly tbody");
  head.replaceChildren(); body.replaceChildren(); const hr = element("tr");
  fields.forEach(([,label])=>{const th=element("th",label);th.scope="col";hr.append(th);}); head.append(hr);
  rows.forEach(row=>{const tr=element("tr");fields.forEach(([key])=>{const v=row[key];tr.append(element("td",key==="month"?v:v===null?"Not attainable":amount(v),Number(v)<0?"negative":""));});body.append(tr);});
}

function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text],{type}));
  const link = element("a"); link.href=url;link.download=name;document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

initializeFields();
byId("assumptions").addEventListener("submit",event=>{event.preventDefault();if(busy||!output)return;try{calculate(readForm());}catch(error){status(error.message,true);}});
byId("scenario").addEventListener("change",event=>{activeScenario=event.target.value;fillFields();render();});
byId("reset").addEventListener("click",async()=>{if(busy)return;try{const response=await fetch("/api/sample");await calculate(await response.json());}catch(error){status(error.message,true);}});
byId("upload").addEventListener("change",async event=>{
  const file=event.target.files[0];if(!file||busy)return;
  if(file.size>128*1024){status("Assumption file exceeds 128 KiB",true);event.target.value="";return;}
  try{const raw=await file.text();await calculate(JSON.parse(raw),raw);}catch(error){status(error.message,true);}finally{event.target.value="";}
});
byId("save-input").addEventListener("click",()=>{if(documentInput)download("assumptions.json",JSON.stringify(documentInput,null,2)+"\n","application/json");});
byId("csv").addEventListener("click",()=>{
  if(!output)return;const rows=output.scenarios[activeScenario].months,keys=Object.keys(rows[0]);
  const cell=v=>v===null?"":`"${String(v).replaceAll('"','""')}"`;
  download(`${activeScenario}.csv`,[keys.map(cell).join(","),...rows.map(row=>keys.map(key=>cell(row[key])).join(","))].join("\r\n")+"\r\n","text/csv");
});
byId("report").addEventListener("click",async()=>{
  if(busy||!documentInput)return;setBusy(true);
  try{const response=await fetch("/api/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(documentInput)});if(!response.ok){const error=await response.json();throw new Error(error.error);}download("report.html",await response.text(),"text/html");}catch(error){status(error.message,true);}finally{setBusy(false);}
});
(async()=>{try{const response=await fetch("/api/sample");await calculate(await response.json());}catch(error){status(error.message,true);}})();

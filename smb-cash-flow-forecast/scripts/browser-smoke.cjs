/* Development-only acceptance checks. The product itself uses no Node packages. */
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const root = path.resolve(__dirname, "..");
  const python = process.env.FORECAST_TEST_PYTHON || "python3";
  const server = spawn(python, ["-m", "smb_forecast", "serve", "--port", "8877"], {
    cwd: root, env: {...process.env, PYTHONDONTWRITEBYTECODE: "1"}, stdio: ["ignore", "pipe", "pipe"]
  });
  let browser;
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Dashboard startup timed out")), 15000);
      server.once("error", error => { clearTimeout(timer); reject(error); });
      server.once("exit", code => { clearTimeout(timer); reject(new Error(`Dashboard exited: ${code}`)); });
      server.stdout.on("data", data => { if (data.toString().includes("Dashboard:")) {clearTimeout(timer);resolve();} });
      server.stderr.on("data", data => process.stderr.write(data));
    });
    browser = await chromium.launch({headless: true});
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("http://127.0.0.1:8877");
    await page.locator("#status").filter({hasText:"Every monthly cash reconciliation passed"}).waitFor();
    assert.match(await page.locator("#kpis").innerText(), /89,577/);
    assert.equal(await page.locator("#monthly tbody tr").count(), 12);
    assert.equal(await page.locator("#cash-chart svg polyline").count(), 4);
    await fs.mkdir(path.join(root,"output"), {recursive:true});
    await page.screenshot({path:path.join(root,"output","dashboard-desktop.png"),fullPage:true});

    await page.locator("#scenario").selectOption("downside");
    assert.match(await page.locator("#kpis").innerText(), /2027-03/);
    assert.match(await page.locator("#kpis").innerText(), /-129,830/);

    await page.locator("#scenario").selectOption("custom");
    await page.locator("#input-monthly_revenue").fill("121000");
    await page.locator("button[type=submit]").click();
    await page.waitForFunction(() => document.querySelector("#input-monthly_revenue").value === "121000" && !document.querySelector("#scenario").disabled);
    assert.match(await page.locator("#active-name").innerText(), /Custom/);
    assert.equal(await page.locator("#input-monthly_revenue").inputValue(), "121000");

    const [download] = await Promise.all([page.waitForEvent("download"),page.locator("#csv").click()]);
    const csv = await fs.readFile(await download.path(),"utf8");
    assert.match(csv,/cash_reconciliation_difference/);
    assert.equal(csv.trim().split(/\r?\n/).length,13);

    const [inputs] = await Promise.all([page.waitForEvent("download"),page.locator("#save-input").click()]);
    const doc = JSON.parse(await fs.readFile(await inputs.path(),"utf8"));
    assert.equal(doc.scenarios.custom.monthly_revenue,121000);
    assert.equal(doc.assumptions.monthly_revenue,120000);

    await page.locator("#input-collection_weights").fill("0.2, 0.2");
    await page.locator("button[type=submit]").click();
    await page.locator("#status.error").waitFor();
    assert.match(await page.locator("#status").innerText(),/sum to exactly 1/);

    const [report] = await Promise.all([page.waitForEvent("download"),page.locator("#report").click()]);
    const html = await fs.readFile(await report.path(),"utf8");
    assert.match(html,/Synthetic SMB/);
    assert.ok(!html.includes("<script>"));

    await page.locator("#upload").setInputFiles({name:"duplicate.json",mimeType:"application/json",buffer:Buffer.from('{"assumptions":{},"assumptions":{"tax_rate":2}}')});
    await page.locator("#status").filter({hasText:"Duplicate JSON key"}).waitFor();
    await page.locator("#reset").click();
    await page.locator("#status").filter({hasText:"Every monthly cash reconciliation passed"}).waitFor();

    // Malicious model names remain text in the dashboard and escaped in downloads.
    const hostile = {...doc,model_name:'<img src=x onerror="window.injected=true">'};
    await page.locator("#upload").setInputFiles({name:"escaped.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(hostile))});
    await page.locator("#model-name").filter({hasText:"<img"}).waitFor();
    assert.equal(await page.locator("#model-name img").count(),0);
    assert.equal(await page.evaluate(() => window.injected),undefined);
    await page.locator("#upload").setInputFiles({name:"minimal.json",mimeType:"application/json",buffer:Buffer.from("{}")});
    await page.locator("#active-name").filter({hasText:"Base"}).waitFor();
    await page.locator("#input-monthly_revenue").fill("101000");
    await page.locator("button[type=submit]").click();
    await page.waitForFunction(() => document.querySelector("#input-monthly_revenue").value === "101000" && !document.querySelector("#scenario").disabled);
    assert.ok(!(await page.locator("#status").getAttribute("class")).includes("error"));
    await page.locator("#reset").click();
    await page.locator("#status").filter({hasText:"Every monthly cash reconciliation passed"}).waitFor();
    await page.locator("#scenario").selectOption("base");
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({path:path.join(root,"output","dashboard-mobile.png"),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log("Browser acceptance checks passed: scenarios, edits, validation, downloads, escaping, and mobile layout.");
  } finally {
    if(browser)await browser.close();
    server.kill("SIGTERM");
  }
})().catch(error=>{console.error(error);process.exitCode=1;});

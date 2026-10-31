const fs = require('node:fs');

function valueFor(field, marker) {
  if (field.type === 'number' || field.type === 'range') {
    const minimum = Number(field.min || 1);
    const maximum = field.max === '' ? Math.max(minimum, 10) : Number(field.max);
    if (minimum > maximum) throw new Error('Invalid numeric field bounds');
    return String(minimum);
  }
  if (field.type === 'email') return `${marker}@example.test`;
  if (field.type === 'date') return new Date().toISOString().slice(0, 10);
  if (field.type === 'datetime-local') return new Date().toISOString().slice(0, 16);
  return marker.slice(0, field.maxLength > 0 ? field.maxLength : 64);
}

function redact(value, token) {
  return token ? String(value).split(token).join('[REDACTED]') : String(value);
}

async function fillFields(page, fields, marker) {
  for (const [selector, value] of Object.entries(fields)) {
    const input = page.locator(selector);
    if (typeof value === 'object' && value !== null) {
      if ('select' in value) await input.selectOption(String(value.select));
      else if ('check' in value) await input.setChecked(Boolean(value.check));
      else if ('option' in value) {
        await input.click();
        await page.getByRole('option', { name: String(value.option), exact: true }).click();
      } else if (value.click === true) await input.click();
      else throw new Error(`Unsupported field operation for ${selector}`);
    } else {
      await input.fill(String(value).replaceAll('$unique', marker));
    }
  }
}

async function run() {
  const { chromium } = require('playwright');
  const token = process.env.ADMIN_TOKEN;
  const results = [];
  let browser;
  let stage = 'login';
  try {
    if (!token) throw new Error('ADMIN_TOKEN is required');
    const scenario = JSON.parse(process.env.E2E_SCENARIO || '{}');
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    page.setDefaultTimeout(15000);
    const origin = 'http://frontend:8080';
    const requests = [];
    page.on('response', response => {
      if (response.url().startsWith(origin + '/api/') && response.request().method() === 'GET') {
        requests.push(response);
      }
    });
    await page.goto(origin);
    const tokenInput = scenario.tokenInput
      ? page.locator(scenario.tokenInput)
      : page.getByLabel(/access token|token/i).first();
    await tokenInput.fill(token);
    const signIn = scenario.signIn
      ? page.locator(scenario.signIn)
      : page.getByRole('button', { name: /sign in|log in|login|connect/i }).first();
    await signIn.click();
    await page.waitForFunction(() => Boolean(sessionStorage.getItem('access_token')));
    if (await page.evaluate(() => sessionStorage.getItem('access_token')) !== token) {
      throw new Error('Login did not retain the supplied token');
    }
    results.push({ name: stage, status: 'passed' });

    stage = 'list';
    const collection = page.locator(scenario.list || 'table, [role="list"], mat-list, .grid mat-card').first();
    await collection.waitFor({ state: 'visible' });
    // A rendered shell alone does not prove that the list loaded from the backend.
    if (!requests.some(response => response.status() === 200 && !response.url().endsWith('/me'))) {
      await page.waitForResponse(response => response.url().startsWith(origin + '/api/') &&
        !response.url().endsWith('/me') && response.request().method() === 'GET' && response.status() === 200);
    }
    results.push({ name: stage, status: 'passed' });

    stage = 'create';
    const marker = `smoke-${Date.now()}`;
    const create = scenario.create
      ? page.locator(scenario.create)
      : page.getByRole('button', { name: /^(create|add|new|start)\b/i }).first();
    async function fillForm(unique) {
      if (scenario.openCreate) await page.locator(scenario.openCreate).click();
      if (scenario.fields) {
        await fillFields(page, scenario.fields, unique);
        return;
      }
      const fields = page.locator('input:visible:not([type="hidden"]):not([type="submit"]):not([type="password"]), textarea:visible');
      for (let index = 0; index < await fields.count(); index++) {
        const input = fields.nth(index);
        if (!await input.isEditable() || await input.inputValue()) continue;
        const field = await input.evaluate(element => ({
          type: element.type, min: element.min || '', max: element.max || '', maxLength: element.maxLength
        }));
        if (['checkbox', 'radio', 'file'].includes(field.type)) continue;
        await input.fill(valueFor(field, unique));
      }
      const selects = page.locator('select:visible');
      for (let index = 0; index < await selects.count(); index++) {
        const select = selects.nth(index);
        if (!await select.isEnabled() || await select.inputValue()) continue;
        const value = await select.locator('option:not(:disabled)').evaluateAll(options =>
          options.find(option => option.value !== '')?.value);
        if (value) await select.selectOption(value);
      }
      const materialSelects = page.locator('mat-select:visible');
      for (let index = 0; index < await materialSelects.count(); index++) {
        const select = materialSelects.nth(index);
        if (!await select.isEnabled()) continue;
        await select.click();
        await page.getByRole('option').filter({ hasNot: page.locator('[aria-disabled="true"]') }).first().click();
      }
    }
    await fillForm(marker);
    const mutation = () => page.waitForResponse(response => response.url().startsWith(origin + '/api/') &&
      ['POST', 'PUT', 'PATCH'].includes(response.request().method()));
    const [created] = await Promise.all([mutation(), create.click()]);
    if (created.status() < 200 || created.status() >= 300) {
      throw new Error(`Create returned HTTP ${created.status()}`);
    }
    const body = await created.json();
    const visibleValue = scenario.createdText
      ? scenario.createdText.replaceAll('$unique', marker)
      : JSON.stringify(body).includes(marker) ? marker : String(body.id ?? body.name ?? '');
    if (!visibleValue) throw new Error('Create response has no observable identity; configure E2E_SCENARIO.createdText');
    await page.getByText(visibleValue, { exact: false }).first().waitFor({ state: 'visible' });
    results.push({ name: stage, status: 'passed' });

    stage = 'error';
    // Exercise the real server's authentication rejection through the same UI.
    await page.evaluate(() => sessionStorage.setItem('access_token', 'invalid-smoke-token'));
    await fillForm(marker + '-rejected');
    const [rejected] = await Promise.all([mutation(), create.click()]);
    if (rejected.status() !== 401) throw new Error(`Invalid token returned HTTP ${rejected.status()}, expected 401`);
    const error = page.locator(scenario.error || '[role="alert"], .error, mat-error').filter({ hasText: /\S/ }).first();
    await error.waitFor({ state: 'visible' });
    results.push({ name: stage, status: 'passed' });
  } catch (error) {
    results.push({ name: stage, status: 'failed', detail: redact(error.message, token) });
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync('/reports/e2e.json', JSON.stringify({
      status: results.length === 4 && results.every(test => test.status === 'passed') ? 'passed' : 'failed',
      tests: results
    }, null, 2));
  }
}

module.exports = { valueFor, redact, fillFields };
if (require.main === module) run();

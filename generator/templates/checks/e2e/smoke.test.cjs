const { test } = require('node:test');
const assert = require('node:assert/strict');
const { valueFor, redact } = require('./smoke.cjs');

test('numeric fields respect minimum and reject inconsistent bounds', () => {
  assert.equal(valueFor({ type: 'number', min: '3', max: '9' }, 'item'), '3');
  assert.equal(valueFor({ type: 'number', min: '0', max: '0' }, 'item'), '0');
  assert.throws(() => valueFor({ type: 'number', min: '9', max: '3' }, 'item'));
});
test('form data respects text length and email type', () => {
  assert.equal(valueFor({ type: 'text', maxLength: 4 }, 'unique'), 'uniq');
  assert.equal(valueFor({ type: 'email' }, 'unique'), 'unique@example.test');
});
test('browser error reports remove every occurrence of the access token', () => {
  assert.equal(redact('fill secret failed secret', 'secret'), 'fill [REDACTED] failed [REDACTED]');
});

test('scenario fields use actual select, checkbox and Material UI operations', async () => {
  const { fillFields } = require('./smoke.cjs');
  const events = [];
  const control = selector => ({
    fill: async value => events.push([selector, 'fill', value]),
    selectOption: async value => events.push([selector, 'select', value]),
    setChecked: async value => events.push([selector, 'check', value]),
    click: async () => events.push([selector, 'click'])
  });
  const page = {
    locator: control,
    getByRole: (role, options) => control(`${role}:${options.name}`)
  };
  await fillFields(page, {
    '#name': '$unique', '#native': { select: '17' }, '#consent': { check: true },
    '#material': { option: 'Driver' }, '#action': { click: true }
  }, 'smoke-42');
  assert.deepEqual(events, [
    ['#name', 'fill', 'smoke-42'], ['#native', 'select', '17'], ['#consent', 'check', true],
    ['#material', 'click'], ['option:Driver', 'click'], ['#action', 'click']
  ]);
  await assert.rejects(fillFields(page, { '#name': { typo: true } }, 'x'));
});

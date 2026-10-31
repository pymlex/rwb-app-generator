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

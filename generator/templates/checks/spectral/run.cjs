const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

async function main() {
  // Fetch the running application's contract, never a model-provided URL.
  const response = await fetch('http://frontend:8080/openapi/v1.json', {
    redirect: 'error', signal: AbortSignal.timeout(30000)
  });
  if (!response.ok) throw new Error(`OpenAPI request failed: HTTP ${response.status}`);
  const schema = await response.json();
  if (!schema.openapi || !schema.paths) throw new Error('Invalid OpenAPI document');
  fs.writeFileSync('/reports/openapi.json', JSON.stringify(schema, null, 2));
  const result = spawnSync('spectral', [
    'lint', '/reports/openapi.json', '--ruleset', '/checks/rules.yaml',
    '--format', 'json', '--output', '/reports/spectral.json', '--fail-severity', 'warn'
  ], { stdio: 'inherit' });
  process.exitCode = result.status ?? 1;
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });

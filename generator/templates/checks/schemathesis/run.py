"""Run authenticated contract checks with sanitized output and a fixed target."""
import os
import subprocess
from pathlib import Path


command = [
    'schemathesis', 'run', '/reports/openapi.json',
    '--url', 'http://frontend:8080',
    '--header', 'Authorization: Bearer ' + os.environ['ADMIN_TOKEN'],
    '--checks', 'all', '--max-examples', '20', '--workers', '1',
    '--report', 'junit', '--report-junit-path', '/reports/schemathesis.xml',
    '--output-sanitize', 'true',
]
with Path('/reports/schemathesis.log').open('w', encoding='utf-8') as stream:
    result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
raise SystemExit(result.returncode)

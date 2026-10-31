"""Select an explicit SAST engine for CI; never fall back after a finding."""
import json
import os
from pathlib import Path


def select(engine: str, reason: str) -> tuple[str, dict]:
    if engine not in {'semgrep', 'dotnet'}:
        raise ValueError('SAST_ENGINE must be semgrep or dotnet')
    if engine == 'dotnet' and not reason.strip():
        raise ValueError('SAST_FALLBACK_REASON is required for the .NET fallback')
    return ('sast-dotnet' if engine == 'dotnet' else 'sast', {
        'engine': engine, 'reason': reason.strip() if engine == 'dotnet' else '',
    })


if __name__ == '__main__':
    service, context = select(os.environ.get('SAST_ENGINE', 'semgrep'),
                              os.environ.get('SAST_FALLBACK_REASON', ''))
    reports = Path('reports')
    reports.mkdir(exist_ok=True)
    (reports / 'sast-context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    print(service)

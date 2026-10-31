"""Inventory retained stage evidence without treating a missing report as a pass."""
import json
import os
from pathlib import Path


root = Path('reports')
root.mkdir(exist_ok=True)
result = {
    'pipeline_id': os.environ.get('CI_PIPELINE_ID'),
    'commit': os.environ.get('CI_COMMIT_SHA'),
    'stages': ['build', 'test', 'security', 'deploy', 'report'],
    'deployment': 'not_run' if os.environ.get('CI_PIPELINE_SOURCE') == 'merge_request_event' else 'see job status',
    'evidence': sorted(path.name for path in root.iterdir() if path.is_file()),
}
(root / 'ci-stages.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')

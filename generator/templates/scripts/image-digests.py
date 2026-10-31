"""List image references and inspection commands without accessing a registry."""
import json
import re
import shlex
from pathlib import Path


def inventory(root: Path) -> list[dict]:
    references: dict[str, list[str]] = {}
    compose = root / 'docker-compose.yml'
    for image in re.findall(r'^\s+image:\s+(\S+)\s*$', compose.read_text(), re.MULTILINE):
        references.setdefault(image, []).append('docker-compose.yml')
    for dockerfile in sorted(root.rglob('Dockerfile')):
        for image in re.findall(r'^FROM\s+(\S+)', dockerfile.read_text(), re.MULTILINE):
            references.setdefault(image, []).append(str(dockerfile.relative_to(root)))
    return [
        {
            'image': image,
            'sources': sorted(set(sources)),
            'kind': 'local-build' if image == 'rwb-app-generator/postgis:17.9' else 'registry',
            'command': None if image == 'rwb-app-generator/postgis:17.9'
            else 'docker buildx imagetools inspect ' + shlex.quote(image),
        }
        for image, sources in sorted(references.items())
    ]


if __name__ == '__main__':
    print(json.dumps(inventory(Path(__file__).resolve().parents[1]), indent=2))

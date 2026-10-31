"""List image references and inspection commands without accessing a registry."""
import json
import re
import shlex
from pathlib import Path


def inventory(root: Path) -> list[dict]:
    references: dict[str, list[str]] = {}
    compose = root / 'docker-compose.yml'
    local_images = set()
    for block in re.split(r'^  [\w-]+:\s*$', compose.read_text(), flags=re.MULTILINE):
        image = re.search(r'^    image:\s+(\S+)', block, re.MULTILINE)
        if image and re.search(r'^    build:', block, re.MULTILINE):
            local_images.add(image[1])
    for image in re.findall(r'^\s+image:\s+(\S+)\s*$', compose.read_text(), re.MULTILINE):
        references.setdefault(image, []).append('docker-compose.yml')
    for dockerfile in sorted(root.rglob('Dockerfile')):
        for image in re.findall(r'^FROM\s+(\S+)', dockerfile.read_text(), re.MULTILINE):
            references.setdefault(image, []).append(str(dockerfile.relative_to(root)))
    return [
        {
            'image': image,
            'sources': sorted(set(sources)),
            'kind': 'local-build' if image in local_images else 'registry',
            'command': None if image in local_images
            else 'docker buildx imagetools inspect ' + shlex.quote(image),
        }
        for image, sources in sorted(references.items())
    ]


if __name__ == '__main__':
    print(json.dumps(inventory(Path(__file__).resolve().parents[1]), indent=2))

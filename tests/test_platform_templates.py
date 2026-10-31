from pathlib import Path

import yaml


TEMPLATES = Path(__file__).resolve().parents[1] / 'generator' / 'templates'


def compose():
    return yaml.safe_load((TEMPLATES / 'docker-compose.yml').read_text())


def test_dependency_and_scanner_containers_restrict_privileges_and_writes():
    services = compose()['services']
    for name in ('lock', 'backend-lock', 'audit'):
        service = services[name]
        assert service['read_only'] is True
        assert service['cap_drop'] == ['ALL']
        assert service['security_opt'] == ['no-new-privileges:true']
        assert '/tmp' in service['tmpfs']
        assert not service.get('env_file')
        assert all(mount.split(':')[0] != '.' for mount in service['volumes'])
        assert all('.env' not in mount for mount in service['volumes'])
    assert services['lock']['environment']['NPM_CONFIG_CACHE'].startswith('/tmp/')
    assert services['backend-lock']['environment']['DOTNET_CLI_HOME'].startswith('/tmp/')
    assert './frontend:/app' in services['lock']['volumes']
    assert './backend:/app' in services['backend-lock']['volumes']
    assert services['audit']['command'][services['audit']['command'].index('--exit-code') + 1] == '1'
    assert './reports:/reports' in services['audit']['volumes']

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


def test_sast_scans_fixed_rules_and_blocks_errors():
    service = compose()['services']['sast']
    assert service['image'] == 'semgrep/semgrep:1.145.0'
    assert service['profiles'] == ['checks']
    command = service['command']
    for rule in ('p/csharp', 'p/typescript', 'p/secrets'):
        assert rule in command
    assert '--error' in command and '--strict' in command
    assert command[command.index('--severity') + 1] == 'ERROR'
    assert '/reports/sast.json' in command
    assert service['read_only'] is True
    fallback = compose()['services']['sast-dotnet']
    assert '-p:SastFallback=true' in fallback['command']
    assert '-p:ErrorLog=/reports/sast.json,version=2.1' in fallback['command']


def test_nginx_policies_allow_pwa_maps_fonts_and_geolocation():
    config = (TEMPLATES / 'frontend/nginx.conf').read_text()
    csp = next(line for line in config.splitlines() if 'Content-Security-Policy' in line)
    for directive in ("default-src 'self'", "frame-ancestors 'none'", "object-src 'none'",
                      "worker-src 'self'", "manifest-src 'self'", "script-src 'self'"):
        assert directive in csp
    assert 'https://tile.openstreetmap.org' in csp
    assert 'https://*.tile.openstreetmap.org' in csp
    assert 'https://fonts.googleapis.com' in csp and 'https://fonts.gstatic.com' in csp
    assert csp.endswith('always;')
    assert 'Permissions-Policy "geolocation=(self), camera=(), microphone=(), payment=()" always;' in config

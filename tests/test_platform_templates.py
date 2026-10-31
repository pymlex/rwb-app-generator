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


def test_gitlab_stages_keep_command_order_and_deploy_only_default_branch():
    config = yaml.safe_load((TEMPLATES / '.gitlab-ci.yml').read_text())
    assert config['stages'] == ['build', 'test', 'security', 'deploy', 'report']
    platform = config['.platform']
    assert platform['resource_group'] == 'rwb-$CI_PROJECT_ID'
    assert platform['tags'] == ['organiser-vm']
    assert platform['artifacts']['when'] == 'always'
    assert 'backend/packages.lock.json' in platform['artifacts']['paths']
    for name in config['stages']:
        assert config[name]['extends'] == '.platform'
        assert config[name]['stage'] == name
        assert all(isinstance(command, str) for command in config[name]['script'])
    commands = [command for name in config['stages'] for command in config[name]['script']]
    original = [
        'docker compose config --quiet',
        'docker compose --profile checks run --rm lock',
        'docker compose --profile checks run --rm backend-lock',
        'docker compose --parallel 1 build',
        'docker compose --profile checks run --rm --build unit > reports/unit.log 2>&1 || { cat reports/unit.log; exit 1; }',
        'cat reports/unit.log',
        'docker compose --profile checks run --rm audit',
        'docker compose up -d --wait --wait-timeout 180 frontend',
        'docker compose --profile checks run --rm acceptance > reports/acceptance.log 2>&1 || { cat reports/acceptance.log; exit 1; }',
        'cat reports/acceptance.log',
    ]
    assert [command for command in commands if command in original] == original
    assert 'merge_request_event' in config['workflow']['rules'][0]['if']
    rule = config['deploy']['rules'][0]['if']
    assert '$CI_PIPELINE_SOURCE != "merge_request_event"' in rule
    assert '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH' in rule
    assert config['report']['when'] == 'always'


def test_contract_services_use_live_openapi_and_keep_reports_separate():
    services = compose()['services']
    for name in ('spectral', 'schemathesis'):
        assert services[name]['profiles'] == ['checks']
        assert services[name]['read_only'] is True
        assert './reports:/reports' in services[name]['volumes']
    spectral = (TEMPLATES / 'checks/spectral/run.cjs').read_text()
    assert "http://frontend:8080/openapi/v1.json" in spectral
    assert "redirect: 'error'" in spectral
    assert '/reports/openapi.json' in spectral and '/reports/spectral.json' in spectral
    assert "'--fail-severity', 'warn'" in spectral
    schema = (TEMPLATES / 'checks/schemathesis/run.py').read_text()
    assert "'--checks', 'all'" in schema
    assert "'--output-sanitize', 'true'" in schema
    assert '/reports/schemathesis.xml' in schema


def test_e2e_runs_real_browser_with_separate_report_and_no_token_artifacts():
    service = compose()['services']['e2e']
    assert service['profiles'] == ['checks'] and service['read_only'] is True
    assert service['cap_drop'] == ['ALL']
    assert service['environment']['ADMIN_TOKEN'] == '${ADMIN_TOKEN}'
    source = (TEMPLATES / 'checks/e2e/smoke.cjs').read_text()
    assert '/reports/e2e.json' in source
    assert 'rejected.status() !== 401' in source
    assert 'created.status() < 200' in source
    assert 'page.route(' not in source
    assert 'screenshot(' not in source and 'tracing.start' not in source


def test_digest_inventory_covers_dockerfiles_and_compose_without_guessing():
    import runpy

    module = runpy.run_path(str(TEMPLATES / 'scripts/image-digests.py'))
    entries = module['inventory'](TEMPLATES)
    assert entries
    assert len(entries) == len({entry['image'] for entry in entries})
    local = [entry for entry in entries if entry['kind'] == 'local-build']
    assert len(local) == 8
    assert all(entry['command'] is None for entry in local)
    documentation = (TEMPLATES / 'checks/IMAGE-DIGESTS.md').read_text()
    for entry in entries:
        assert entry['image'] in documentation
        if entry['kind'] == 'registry':
            assert entry['command'].startswith('docker buildx imagetools inspect ')


def test_audit_build_covers_whole_project_without_sending_env_files():
    service = compose()['services']['audit']
    assert service['build']['dockerfile'] == 'checks/audit/Dockerfile'
    source = (TEMPLATES / service['build']['dockerfile']).read_text()
    assert 'COPY . /src' in source
    exclusions = (TEMPLATES / 'checks/audit/Dockerfile.dockerignore').read_text().splitlines()
    assert {'.env', '.env.*', '**/.env', '**/.env.*', '.git', '.pipeline'} <= set(exclusions)
    for required in ('database', 'checks', 'docs', 'docker-compose.yml', '.gitlab-ci.yml'):
        assert required not in exclusions
    assert all('/src' not in volume for volume in service['volumes'])


def test_ci_isolates_built_images_per_pipeline_and_supports_sast_fallback():
    config = yaml.safe_load((TEMPLATES / '.gitlab-ci.yml').read_text())
    assert config['variables']['APP_IMAGE_TAG'] == '$CI_PIPELINE_ID'
    assert config['variables']['DATABASE_IMAGE_TAG'] == '17.9-$CI_PIPELINE_ID'
    for name, service in compose()['services'].items():
        if 'build' in service:
            variable = 'DATABASE_IMAGE_TAG' if name == 'database' else 'APP_IMAGE_TAG'
            assert '${' + variable + ':-' in service['image']
            assert '${COMPOSE_PROJECT_NAME:-rwb-app-generator}/' in service['image']
    commands = config['security']['script']
    assert 'SAST_SERVICE=$(python3 scripts/sast-service.py)' in commands
    assert 'docker compose --profile checks run --rm "$SAST_SERVICE"' in commands


def test_ci_sast_selection_rejects_unexplained_fallback():
    import runpy

    import pytest

    select = runpy.run_path(str(TEMPLATES / 'scripts/sast-service.py'))['select']
    with pytest.raises(ValueError, match='SAST_FALLBACK_REASON'):
        select('dotnet', '')
    with pytest.raises(ValueError, match='SAST_ENGINE'):
        select('disabled', '')
    assert select('dotnet', 'VM network unavailable') == (
        'sast-dotnet', {'engine': 'dotnet', 'reason': 'VM network unavailable'},
    )


def test_named_driver_configuration_is_optional_and_legacy_token_stays_required():
    services = compose()['services']
    assert services['backend']['environment']['DRIVER_TOKEN'] == '${DRIVER_TOKEN:?Set DRIVER_TOKEN}'
    assert services['backend']['environment']['DRIVER_TOKENS'] == '${DRIVER_TOKENS:-}'
    program = (TEMPLATES / 'backend/Program.cs').read_text()
    assert program.index('foreach (var role in new[] { "admin", "driver" })') < program.index('foreach (var driver in DriverIdentities.Parse(configuration))')
    assert 'DriverIdentities.Parse(builder.Configuration);' in program
    runner = (TEMPLATES / 'backend-unit/Program.cs').read_text()
    assert 'IdentityAcceptance.Run' in runner
    assert 'Known limitation until VM acceptance' in (TEMPLATES / 'checks/IDENTITIES.md').read_text()


def test_real_domain_ownership_acceptance_rejects_foreign_access_and_state_changes():
    import copy
    import runpy

    import pytest

    verify = runpy.run_path(str(TEMPLATES / 'checks/ownership/run.py'))['verify_ownership']
    scenario = {'create': {'path': '/api/v1/items', 'body': {'name': '$unique'}},
                'read': '/api/v1/items/{id}',
                'mutate': {'path': '/api/v1/items/{id}', 'body': {'name': 'changed'}}}
    state = {'id': '42', 'name': 'original'}
    calls = []
    leak = False
    corrupt = False

    def request(method, path, token, body=None):
        calls.append((method, path, token))
        if method == 'POST':
            return 201, {'id': '42'}
        if token == 'second':
            if corrupt and method == 'PATCH':
                state['name'] = 'changed'
            return (200 if leak else 404), None
        return 200, copy.deepcopy(state)

    assert verify(scenario, 'alice:first,bob:second', request)['status'] == 'passed'
    assert ('PATCH', '/api/v1/items/42', 'second') in calls
    assert calls[-1] == ('PATCH', '/api/v1/items/42', 'first')
    leak = True
    with pytest.raises(ValueError, match='Foreign read'):
        verify(scenario, 'alice:first,bob:second', request)
    leak = False
    corrupt = True
    with pytest.raises(ValueError, match='changed persisted'):
        verify(scenario, 'alice:first,bob:second', request)
    with pytest.raises(ValueError, match='at least two'):
        verify(scenario, '', request)
    corrupt = False

    def missing_mutation(method, path, token, body=None):
        return (404, None) if method == 'PATCH' else request(method, path, token, body)

    with pytest.raises(ValueError, match='Owner mutation control'):
        verify(scenario, 'alice:first,bob:second', missing_mutation)

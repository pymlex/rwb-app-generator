"""Verify ownership against a real domain, using two configured driver identities."""
import json
import os
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_request(method, path, token, body=None):
    if not path.startswith('/api/v1/') or '..' in path or '#' in path:
        raise ValueError('Ownership paths must stay under /api/v1/')
    request = Request(
        'http://frontend:8080' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                 'Idempotency-Key': 'ownership-' + uuid.uuid4().hex},
        method=method,
    )
    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            payload = response.read()
            if not payload:
                return response.status, None
            try:
                return response.status, json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return response.status, payload.decode('utf-8', errors='replace')
    except HTTPError as error:
        return error.code, None


def verify_ownership(scenario, drivers, request=api_request):
    identities = [entry.split(':', 1) for entry in drivers.split(',') if entry]
    if len(identities) < 2 or any(len(entry) != 2 or not all(entry) for entry in identities):
        raise ValueError('Ownership acceptance requires at least two named DRIVER_TOKENS')
    first, second = identities[:2]
    if first[0] == second[0] or first[1] == second[1]:
        raise ValueError('Ownership acceptance requires distinct identities and tokens')
    create = scenario['create']
    mutate = scenario['mutate']
    if '{id}' not in scenario['read'] or '{id}' not in mutate['path']:
        raise ValueError('Read and mutation paths must address the created {id}')
    method = mutate.get('method', 'PATCH')
    if method not in {'PUT', 'PATCH', 'DELETE', 'POST'}:
        raise ValueError('Unsupported ownership mutation method')
    body = json.loads(json.dumps(create['body']).replace('$unique', 'owner-' + uuid.uuid4().hex))
    status, created = request('POST', create['path'], first[1], body)
    expected = create.get('status', 201)
    if expected not in {200, 201, 202} or status != expected:
        raise ValueError(f'Owner create returned HTTP {status}, expected {expected}')
    identifier = str(created[scenario.get('id_field', 'id')])
    if not identifier:
        raise ValueError('Create returned an empty resource id')
    path = scenario['read'].replace('{id}', quote(identifier, safe=''))
    status, before = request('GET', path, first[1])
    if status != 200:
        raise ValueError(f'Owner read returned HTTP {status}, expected 200')
    status, _ = request('GET', path, second[1])
    if status != 404:
        raise ValueError(f'Foreign read returned HTTP {status}, expected 404')
    mutation_path = mutate['path'].replace('{id}', quote(identifier, safe=''))
    status, _ = request(method, mutation_path, second[1], mutate.get('body'))
    if status != 404:
        raise ValueError(f'Foreign mutation returned HTTP {status}, expected 404')
    status, after = request('GET', path, first[1])
    if status != 200 or after != before:
        raise ValueError('Foreign mutation changed persisted owner state')
    status, _ = request(method, mutation_path, first[1], mutate.get('body'))
    if not 200 <= status < 300:
        raise ValueError(f'Owner mutation control returned HTTP {status}, expected 2xx')
    return {'status': 'passed', 'checks': ['owner-create', 'owner-read', 'foreign-read-404',
                                         'foreign-mutation-404', 'owner-state-unchanged',
                                         'owner-mutation-control']}


def main():
    drivers = os.environ.get('DRIVER_TOKENS', '')
    try:
        result = verify_ownership(json.loads(os.environ['OWNERSHIP_SCENARIO']), drivers)
    except Exception as error:
        detail = str(error)
        for entry in drivers.split(','):
            if ':' in entry and entry.split(':', 1)[1]:
                detail = detail.replace(entry.split(':', 1)[1], '[REDACTED]')
        result = {'status': 'failed', 'detail': detail}
    Path('/reports/ownership.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

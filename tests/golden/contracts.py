"""Offline contracts for TestHub's versioned golden fixture bundle.

The fixtures are deliberately synthetic and credential-free.  Production
connectors may replay these request/response shapes in contract tests, but
ordinary CI must never need a live Atlassian server or a model provider.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_BUNDLE_ROOT = Path(__file__).resolve().parent / 'v1'
MANIFEST_SCHEMA = 'testhub.golden-manifest.v1'
CASSETTE_SCHEMA = 'testhub.http-cassette.v1'
READ_ONLY_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})
SYNAPSE_ALLOWED_OPERATIONS = frozenset(
    {
        'get_license',
        'list_test_suite_tree',
        'list_test_suite_members',
        'list_test_steps',
        'list_test_plan_members',
        'list_test_cycles',
        'list_test_runs',
        'list_requirement_test_cases',
        'list_run_defects',
    }
)
FORBIDDEN_ENDPOINT_SEGMENTS = frozenset(
    {'add', 'create', 'update', 'delete', 'remove', 'clone', 'trigger', 'execute', 'generateai'}
)
SENSITIVE_KEYS = frozenset(
    {
        'authorization',
        'cookie',
        'set-cookie',
        'password',
        'passwd',
        'token',
        'api_key',
        'apikey',
        'clientsecret',
        'client_secret',
    }
)
REDACTED_VALUES = frozenset({'', '[REDACTED]', '<REDACTED>', 'redacted'})
ASSIGNMENT_SECRET_RE = re.compile(
    r'(?i)\b(?:authorization|password|passwd|token|api[_-]?key|client[_-]?secret|cookie)'
    r'\s*[:=]\s*(?!\[REDACTED\]|<REDACTED>|redacted)([^\s\"\',;}]{8,})'
)
LONG_TOKEN_RE = re.compile(r'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{48,}={0,2}(?![A-Za-z0-9+/])')
JIRA_KEY_RE = re.compile(r'\b([A-Z][A-Z0-9_]+-\d+)\b')
SPACE_KEY_RE = re.compile(r'"key"\s*:\s*"([A-Z][A-Z0-9_-]*)"')


class GoldenFixtureError(ValueError):
    """Raised when a golden fixture violates a deterministic contract."""


@dataclass(frozen=True)
class ValidationResult:
    bundle_version: str
    file_count: int
    cassette_count: int
    security_case_count: int
    web_state_count: int
    web_edge_count: int


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GoldenFixtureError(f'Cannot load JSON fixture {path}: {exc}') from exc


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(64 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _safe_bundle_path(root: Path, relative_path: str) -> Path:
    if not relative_path or '\\' in relative_path:
        raise GoldenFixtureError(f'Fixture path must be a non-empty POSIX path: {relative_path!r}')
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise GoldenFixtureError(f'Fixture path escapes bundle root: {relative_path}') from exc
    if not candidate.is_file():
        raise GoldenFixtureError(f'Fixture file is missing: {relative_path}')
    return candidate


def _walk_values(value: Any, key: str = '') -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            normalized_key = str(child_key).strip().lower().replace('-', '_')
            yield normalized_key, child_value
            yield from _walk_values(child_value, normalized_key)
    elif isinstance(value, list):
        for child_value in value:
            yield from _walk_values(child_value, key)


def assert_sanitized(value: Any, source_name: str) -> None:
    """Reject credential-bearing keys and token-like literal values."""

    for key, child_value in _walk_values(value):
        comparable_key = key.replace('_', '')
        if key in SENSITIVE_KEYS or comparable_key in SENSITIVE_KEYS:
            if not isinstance(child_value, str) or child_value.strip() not in REDACTED_VALUES:
                raise GoldenFixtureError(f'{source_name} contains a non-redacted sensitive field: {key}')

    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    if ASSIGNMENT_SECRET_RE.search(serialized):
        raise GoldenFixtureError(f'{source_name} contains a credential assignment')
    if LONG_TOKEN_RE.search(serialized):
        raise GoldenFixtureError(f'{source_name} contains a long token-like value')


def _validate_request(request: dict[str, Any], source_name: str) -> None:
    method = str(request.get('method', '')).upper()
    if method not in READ_ONLY_METHODS:
        raise GoldenFixtureError(f'{source_name} uses non-read-only HTTP method: {method}')
    path = str(request.get('path', ''))
    if not path.startswith('/') or '://' in path:
        raise GoldenFixtureError(f'{source_name} has an invalid relative request path: {path}')
    headers = request.get('headers', {})
    if not isinstance(headers, dict):
        raise GoldenFixtureError(f'{source_name} request headers must be an object')
    forbidden_headers = {str(name).lower() for name in headers} & {'authorization', 'cookie', 'proxy-authorization'}
    if forbidden_headers:
        raise GoldenFixtureError(f'{source_name} records credential headers: {sorted(forbidden_headers)}')


def _endpoint_segments(path: str) -> set[str]:
    return {segment for segment in re.split(r'[-_/]+', path.lower()) if segment}


def validate_cassette(cassette: dict[str, Any], source_name: str) -> int:
    if cassette.get('schema_version') != CASSETTE_SCHEMA:
        raise GoldenFixtureError(f'{source_name} has unsupported cassette schema')
    if cassette.get('synthetic') is not True or cassette.get('sanitized') is not True:
        raise GoldenFixtureError(f'{source_name} must be explicitly synthetic and sanitized')

    source = cassette.get('source')
    scope = cassette.get('scope')
    interactions = cassette.get('interactions')
    if source not in {'jira', 'confluence', 'synapsert'}:
        raise GoldenFixtureError(f'{source_name} has unsupported source: {source}')
    if not isinstance(scope, dict) or not isinstance(interactions, list) or not interactions:
        raise GoldenFixtureError(f'{source_name} must contain scope and interactions')

    if source == 'jira' and scope.get('project_keys') != ['PIMC']:
        raise GoldenFixtureError('Jira cassette scope must be exactly PIMC')
    if source == 'confluence':
        if scope.get('space_keys') != ['P331'] or scope.get('root_page_ids') != ['66978175']:
            raise GoldenFixtureError('Confluence cassette scope must be P331/66978175')
    if source == 'synapsert' and scope.get('project_keys') != ['PIMC']:
        raise GoldenFixtureError('SynapseRT cassette scope must be exactly PIMC')

    seen_ids: set[str] = set()
    for interaction in interactions:
        interaction_id = str(interaction.get('id', ''))
        if not interaction_id or interaction_id in seen_ids:
            raise GoldenFixtureError(f'{source_name} has a missing or duplicate interaction id')
        seen_ids.add(interaction_id)
        request = interaction.get('request', {})
        response = interaction.get('response', {})
        _validate_request(request, f'{source_name}:{interaction_id}')
        status = response.get('status')
        if not isinstance(status, int) or status < 200 or status >= 400:
            raise GoldenFixtureError(f'{source_name}:{interaction_id} has invalid fixture status: {status}')

        path = str(request.get('path', ''))
        response_body_text = json.dumps(response.get('body', {}), ensure_ascii=False, sort_keys=True)
        if source == 'jira':
            jql = str(request.get('query', {}).get('jql', ''))
            if jql and not re.search(r'(?i)\bproject\s*=\s*PIMC\b', jql):
                raise GoldenFixtureError(f'{source_name}:{interaction_id} escapes PIMC JQL scope')
            foreign_keys = {key for key in JIRA_KEY_RE.findall(response_body_text) if not key.startswith('PIMC-')}
            if foreign_keys:
                raise GoldenFixtureError(f'{source_name}:{interaction_id} leaks foreign project keys: {sorted(foreign_keys)}')
        elif source == 'confluence':
            if not path.startswith('/rest/api/'):
                raise GoldenFixtureError(f'{source_name}:{interaction_id} is outside Confluence REST API')
            foreign_spaces = {key for key in SPACE_KEY_RE.findall(response_body_text) if key != 'P331'}
            if foreign_spaces:
                raise GoldenFixtureError(f'{source_name}:{interaction_id} leaks foreign space keys: {sorted(foreign_spaces)}')
        elif source == 'synapsert':
            operation = str(interaction.get('operation', ''))
            if operation not in SYNAPSE_ALLOWED_OPERATIONS:
                raise GoldenFixtureError(f'{source_name}:{interaction_id} uses unapproved operation: {operation}')
            if not path.startswith('/rest/synapse/latest/'):
                raise GoldenFixtureError(f'{source_name}:{interaction_id} is outside SynapseRT REST base')
            forbidden = _endpoint_segments(path) & FORBIDDEN_ENDPOINT_SEGMENTS
            if forbidden:
                raise GoldenFixtureError(f'{source_name}:{interaction_id} contains write/execute path segment: {forbidden}')
            foreign_keys = {key for key in JIRA_KEY_RE.findall(response_body_text) if not key.startswith('PIMC-')}
            if foreign_keys:
                raise GoldenFixtureError(f'{source_name}:{interaction_id} leaks foreign project keys: {sorted(foreign_keys)}')

    assert_sanitized(cassette, source_name)
    return len(interactions)


def evaluate_acl_case(case: dict[str, Any]) -> str:
    required = ('same_project', 'project_permission', 'source_acl', 'resource_current')
    return 'allow' if all(case.get(name) is True for name in required) else 'deny'


def _validate_acl_cases(data: dict[str, Any], source_name: str) -> int:
    cases = data.get('cases', [])
    if len(cases) < 5:
        raise GoldenFixtureError('ACL golden set must contain at least five cases')
    for case in cases:
        actual = evaluate_acl_case(case)
        if actual != case.get('expected_decision'):
            raise GoldenFixtureError(f'{source_name}:{case.get("id")} has inconsistent ACL expectation')
    if not any(case.get('same_project') is False and case.get('expected_decision') == 'deny' for case in cases):
        raise GoldenFixtureError('ACL golden set must include a cross-project denial')
    return len(cases)


def _validate_prompt_cases(data: dict[str, Any], source_name: str) -> int:
    cases = data.get('cases', [])
    if len(cases) < 4:
        raise GoldenFixtureError('Prompt-injection golden set must contain at least four cases')
    allowed_actions = {'quote_as_untrusted', 'sanitize_and_quote', 'refuse_and_audit'}
    for case in cases:
        if case.get('expected_action') not in allowed_actions:
            raise GoldenFixtureError(f'{source_name}:{case.get("id")} has unsupported expected action')
        if case.get('tool_access_escalated') is not False or case.get('secret_disclosure') is not False:
            raise GoldenFixtureError(f'{source_name}:{case.get("id")} permits escalation or disclosure')
    return len(cases)


def evaluate_endpoint_case(case: dict[str, Any]) -> str:
    method = str(case.get('method', '')).upper()
    path = str(case.get('path', ''))
    if method not in READ_ONLY_METHODS:
        return 'deny'
    if _endpoint_segments(path) & FORBIDDEN_ENDPOINT_SEGMENTS:
        return 'deny'
    return 'allow'


def _validate_risk_cases(data: dict[str, Any], source_name: str) -> int:
    endpoint_cases = data.get('endpoint_cases', [])
    browser_cases = data.get('browser_action_cases', [])
    ssrf_cases = data.get('ssrf_cases', [])
    if min(len(endpoint_cases), len(browser_cases), len(ssrf_cases)) < 3:
        raise GoldenFixtureError('Risk golden set must cover endpoints, browser actions, and SSRF')

    for case in endpoint_cases:
        if evaluate_endpoint_case(case) != case.get('expected_decision'):
            raise GoldenFixtureError(f'{source_name}:{case.get("id")} has inconsistent endpoint decision')
    for case in browser_cases:
        risk = case.get('risk')
        decision = case.get('expected_decision')
        if risk in {'sensitive', 'destructive'} and decision not in {'deny', 'require_approval'}:
            raise GoldenFixtureError(f'{source_name}:{case.get("id")} fails closed for a risky action')
    for case in ssrf_cases:
        if case.get('category') in {'loopback', 'link_local', 'cloud_metadata', 'file_scheme'}:
            if case.get('expected_decision') != 'deny':
                raise GoldenFixtureError(f'{source_name}:{case.get("id")} does not deny an SSRF target')
    return len(endpoint_cases) + len(browser_cases) + len(ssrf_cases)


def _validate_web_graph(data: dict[str, Any], source_name: str, root: Path) -> tuple[int, int]:
    states = data.get('states', [])
    edges = data.get('edges', [])
    features = set(data.get('covered_features', []))
    required_features = {'route', 'modal', 'tab', 'form', 'pagination', 'dynamic_id', 'loop', 'risk_action'}
    if not required_features.issubset(features):
        raise GoldenFixtureError(f'{source_name} misses web features: {sorted(required_features - features)}')
    state_ids = {str(state.get('id', '')) for state in states}
    if '' in state_ids or len(state_ids) != len(states):
        raise GoldenFixtureError(f'{source_name} contains missing/duplicate state ids')
    for state in states:
        asset = state.get('asset')
        if asset:
            _safe_bundle_path(root, f'web/{asset}')
    for edge in edges:
        if edge.get('source') not in state_ids or edge.get('target') not in state_ids:
            raise GoldenFixtureError(f'{source_name} contains a dangling graph edge')
    return len(states), len(edges)


def validate_bundle(root: Path | str = DEFAULT_BUNDLE_ROOT) -> ValidationResult:
    root = Path(root).resolve()
    manifest_path = _safe_bundle_path(root, 'manifest.json')
    manifest = load_json(manifest_path)
    if manifest.get('schema_version') != MANIFEST_SCHEMA:
        raise GoldenFixtureError('Unsupported golden manifest schema')
    if manifest.get('synthetic') is not True or manifest.get('sanitized') is not True:
        raise GoldenFixtureError('Golden manifest must be synthetic and sanitized')

    entries = manifest.get('files', [])
    if not isinstance(entries, list) or not entries:
        raise GoldenFixtureError('Golden manifest has no files')
    paths = [str(entry.get('path', '')) for entry in entries]
    if len(paths) != len(set(paths)):
        raise GoldenFixtureError('Golden manifest contains duplicate file paths')

    cassette_count = 0
    security_case_count = 0
    web_state_count = 0
    web_edge_count = 0
    baseline_report: dict[str, Any] | None = None
    for entry in entries:
        relative_path = str(entry.get('path', ''))
        fixture_path = _safe_bundle_path(root, relative_path)
        actual_hash = file_sha256(fixture_path)
        if entry.get('sha256') != actual_hash:
            raise GoldenFixtureError(f'Checksum mismatch for {relative_path}')
        kind = entry.get('kind')

        if fixture_path.suffix.lower() == '.json':
            payload = load_json(fixture_path)
            assert_sanitized(payload, relative_path)
        else:
            payload = fixture_path.read_text(encoding='utf-8')
            assert_sanitized(payload, relative_path)

        if kind == 'cassette':
            cassette_count += 1
            validate_cassette(payload, relative_path)
        elif kind == 'security_acl':
            security_case_count += _validate_acl_cases(payload, relative_path)
        elif kind == 'security_prompt':
            security_case_count += _validate_prompt_cases(payload, relative_path)
        elif kind == 'security_risk':
            security_case_count += _validate_risk_cases(payload, relative_path)
        elif kind == 'web_graph':
            web_state_count, web_edge_count = _validate_web_graph(payload, relative_path, root)
        elif kind == 'baseline_report':
            baseline_report = payload

    if cassette_count != 3:
        raise GoldenFixtureError(f'Golden bundle must contain exactly three source cassettes, got {cassette_count}')
    if baseline_report is None or baseline_report.get('result') != 'PASS':
        raise GoldenFixtureError('Golden bundle must contain a passing machine-readable baseline report')
    expected_counts = baseline_report.get('expected_counts', {})
    actual_counts = {
        'files': len(entries),
        'cassettes': cassette_count,
        'security_cases': security_case_count,
        'web_states': web_state_count,
        'web_edges': web_edge_count,
    }
    if expected_counts != actual_counts:
        raise GoldenFixtureError(
            f'Baseline report counts do not match bundle: expected {expected_counts}, actual {actual_counts}'
        )
    return ValidationResult(
        bundle_version=str(manifest.get('bundle_version', '')),
        file_count=len(entries),
        cassette_count=cassette_count,
        security_case_count=security_case_count,
        web_state_count=web_state_count,
        web_edge_count=web_edge_count,
    )

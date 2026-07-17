from __future__ import annotations

import json
import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from tests.golden.contracts import (
    DEFAULT_BUNDLE_ROOT,
    GoldenFixtureError,
    assert_sanitized,
    evaluate_acl_case,
    evaluate_endpoint_case,
    load_json,
    validate_cassette,
    validate_bundle,
)
from tests.golden.web_fixture import GoldenWebServer


class GoldenFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = validate_bundle()

    def test_manifest_is_versioned_and_complete(self):
        self.assertEqual(self.result.bundle_version, '1.0.0')
        self.assertGreaterEqual(self.result.file_count, 12)
        self.assertEqual(self.result.cassette_count, 3)

    def test_security_gold_has_initial_coverage(self):
        self.assertGreaterEqual(self.result.security_case_count, 20)
        self.assertGreaterEqual(self.result.web_state_count, 7)
        self.assertGreaterEqual(self.result.web_edge_count, 8)

    def test_acl_matrix_is_fail_closed(self):
        data = load_json(DEFAULT_BUNDLE_ROOT / 'security' / 'acl_cases.json')
        decisions = {case['id']: evaluate_acl_case(case) for case in data['cases']}
        self.assertEqual(decisions['acl-owner-current'], 'allow')
        self.assertEqual(decisions['acl-cross-project'], 'deny')
        self.assertEqual(decisions['acl-source-denied'], 'deny')
        self.assertEqual(decisions['acl-stale-resource'], 'deny')

    def test_synapsert_write_and_ai_endpoints_are_denied(self):
        data = load_json(DEFAULT_BUNDLE_ROOT / 'security' / 'risk_cases.json')
        decisions = {case['id']: evaluate_endpoint_case(case) for case in data['endpoint_cases']}
        self.assertEqual(decisions['synapse-read-suite-tree'], 'allow')
        self.assertEqual(decisions['synapse-delete-suite'], 'deny')
        self.assertEqual(decisions['synapse-trigger-run'], 'deny')
        self.assertEqual(decisions['synapse-generate-ai'], 'deny')

    def test_checksum_detects_fixture_tampering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copied_root = Path(temp_dir) / 'v1'
            shutil.copytree(DEFAULT_BUNDLE_ROOT, copied_root)
            target = copied_root / 'documents' / 'requirement_sample.md'
            target.write_text(target.read_text(encoding='utf-8') + '\ntampered\n', encoding='utf-8')
            with self.assertRaisesRegex(GoldenFixtureError, 'Checksum mismatch'):
                validate_bundle(copied_root)

    def test_cross_project_issue_in_cassette_is_rejected(self):
        cassette = copy.deepcopy(load_json(DEFAULT_BUNDLE_ROOT / 'cassettes' / 'jira_pimc.json'))
        cassette['interactions'][1]['response']['body']['issues'][0]['key'] = 'OTHER-900001'
        with self.assertRaisesRegex(GoldenFixtureError, 'foreign project keys'):
            validate_cassette(cassette, 'tampered-jira')

    def test_non_redacted_sensitive_field_is_rejected(self):
        unsafe_value = 'fixture-' + 'value-not-redacted'
        with self.assertRaisesRegex(GoldenFixtureError, 'non-redacted sensitive field'):
            assert_sanitized({'password': unsafe_value}, 'tampered-security-case')

    def test_controlled_web_fixture_serves_only_checked_in_assets(self):
        with GoldenWebServer() as server:
            with urlopen(server.url('/index.html'), timeout=5) as response:
                body = response.read().decode('utf-8')
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers['X-TestHub-Fixture'], 'wp-001-v1')
                self.assertIn('TestHub Golden Web Fixture', body)
            with urlopen(server.url('/api/state.json'), timeout=5) as response:
                payload = json.loads(response.read().decode('utf-8'))
                self.assertEqual(payload['fixture_version'], '1.0.0')
                self.assertEqual(payload['status'], 'ready')


if __name__ == '__main__':
    unittest.main()

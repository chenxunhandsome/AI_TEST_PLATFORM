# WP-001 Golden Fixture and Security Baseline

- Status: PASS
- Evaluated at: 2026-07-17T10:04:11+08:00
- Bundle version: `1.0.0`
- Manifest SHA-256: `d9e773e450718711e53d7e5fb7b6732ea8e81680f85849e58b5d5856b745d793`
- Normative design: `docs/AI_INTELLIGENT_TESTING_PLATFORM_DESIGN.md`
- Machine report: `tests/golden/v1/baseline_report.json`

## Scope

This is the deterministic seed baseline for later connector, retrieval, UI graph,
execution, and security work packages. It contains synthetic and sanitized data
only. It does not require a PAT, company network, live Atlassian service, model
provider, Neo4j, or Qdrant.

| Asset | Count | Result |
|---|---:|---|
| Manifest-protected files | 18 | PASS |
| Source cassettes | 3 | PASS |
| Security cases | 27 | PASS |
| Controlled Web states | 8 | PASS |
| Controlled Web edges | 10 | PASS |
| Golden contract tests | 8 | PASS |
| WP-001 + existing regression tests | 48 | PASS |

## Source cassettes

| Source | Enforced scope | Contract |
|---|---|---|
| Jira | Project `PIMC` only | REST v2 search/changelog/server metadata; read-only; foreign project keys rejected |
| Confluence | Space `P331`, root `66978175` | Root/child/attachment pagination; read-only; foreign Space keys rejected |
| SynapseRT | Project `PIMC`, `/rest/synapse/latest/` | License/suite tree/members/steps adapter shapes; write, delete, clone, trigger, execution, and AI operations rejected |

Each cassette is marked `synthetic=true` and `sanitized=true`. Requests contain
no Authorization, Cookie, or proxy credential header. Live SynapseRT path binding
still requires the WP-205 capability probe; the checked-in response bodies are
adapter-level contract fixtures, not copied production payloads.

## Security gates

All current cases pass and fail closed:

- project permission intersected with source ACL and current-resource state;
- cross-project and source-denied reads rejected;
- prompt-injection content remains untrusted evidence;
- untrusted content cannot escalate tools or disclose secrets;
- non-redacted sensitive fields rejected;
- manifest/file tampering rejected by SHA-256;
- SynapseRT write/execute/clone/delete/AI endpoints rejected;
- destructive browser actions denied or require approval;
- loopback, link-local, cloud metadata, and file-scheme SSRF targets denied.

## Controlled Web fixture

The fixture server binds only to `127.0.0.1` on an ephemeral port and serves
checked-in assets with `Cache-Control: no-store` and the
`X-TestHub-Fixture: wp-001-v1` response marker. Its ground-truth graph covers:

- routes and login form;
- tabs and deterministic panels;
- modal form submission;
- pagination;
- runtime-volatile element IDs with stable `data-testid` selectors;
- a self-loop for loop-guard testing;
- sensitive/destructive actions;
- an imported prompt-injection page.

## Reproduction evidence

```powershell
python -m unittest tests.test_golden_baseline -v
# 8 tests, OK

python manage.py test tests.test_golden_baseline apps.requirement_analysis.tests apps.ui_automation.tests_ai_case_generation apps.ui_automation.tests_mcp_generation --settings=backend.settings_local --verbosity 1
# 48 tests, OK

python manage.py check --settings=backend.settings_local
# System check identified no issues

python manage.py makemigrations --check --dry-run --settings=backend.settings_local
# No changes detected

cd frontend
npm run build
# PASS; existing tree-sitter/fs/path/chunk-size warnings remain
```

## Known limitations and expansion rules

1. The initial bundle contains one controlled Web application. Before the UI
   graph release gate, expand this to three to five controlled applications as
   required by the quality plan.
2. SynapseRT wire paths are capability-bound in WP-205 because plugin builds can
   expose different endpoint names. No guessed live endpoint may bypass probing.
3. The 27 security cases are a seed, not the final WP-801 security corpus.
4. Retrieval, extraction, requirement, testcase, binding, execution, and
   exploration gold sets are populated in their owning work packages.
5. Changing a fixture requires updating its manifest checksum. Behavior or label
   changes also require a new bundle version and review evidence.

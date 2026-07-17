# TestHub Golden Fixtures

`v1/manifest.json` is the entry point for the deterministic WP-001 baseline.
All data is synthetic and sanitized. Ordinary CI must validate and replay this
bundle without a PAT, company network, live Atlassian server, browser account,
or model provider.

Run the baseline with:

```powershell
python -m unittest tests.test_golden_baseline -v
```

Rules:

1. Never record `Authorization`, cookies, passwords, PATs, real user profiles,
   or unreviewed production content in a fixture.
2. Any fixture change must update its SHA-256 in `manifest.json` and the bundle
   version when behavior or expected labels change.
3. Cassette requests are read-only and scope-locked to PIMC or P331/66978175.
4. SynapseRT write, execution, cloning, triggering, deletion, and AI endpoints
   must remain outside the allowed cassette operations.
5. The web fixture binds only to loopback and uses deterministic local assets.

# DA-1711 Cross-Language Parity Scenario Manifest

Every scenario below is asserted in BOTH `python/tests/` and
`typescript/tests/` (plan step 5.3). Keep this list in sync when scenarios
are added.

| Scenario | Python test | TypeScript test |
|---|---|---|
| SSRF: private/metadata/CGNAT/link-local blocked | `test_url_policy.py` (17) | `url-policy.test.ts` (17) |
| SSRF: redirect-to-internal rejected, hop re-validation | `test_file_download.py::TestDownloadPolicy` | `base-node.test.ts` (download describe) |
| Size-cap mid-stream abort + no partial left | `test_file_download.py::TestDownloadPolicy` | `base-node.test.ts` |
| START seeded inputs reach downstream / merge | `test_workflow_runner.py::TestStartInputSeeding` | `workflow-runner.test.ts` (seeding describe) |
| Mis-wired edge → failed node, not crash | `test_workflow_runner.py::TestResolverErrorIsolation` | `workflow-runner.test.ts` |
| Traversal run_id/node_id rejected at validation | `test_request.py::TestSlugValidation` | `request.test.ts` |
| Body limit 413 / malformed 422 | `test_app.py::TestBodyLimitAndRedaction` | `app.test.ts` (express 50mb global) |
| Upload failure → UPLOAD_FAILED fail | `test_uploads.py` + `test_app.py` | `app.test.ts` (upload failure describe) |

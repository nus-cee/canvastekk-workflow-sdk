# PLAN-DA-943: External Author Documentation

**Jira Ticket**: [DA-943](https://betekk.atlassian.net/browse/DA-943)
**Epic**: [DA-929](https://betekk.atlassian.net/browse/DA-929) — Automated Node Registration & Workflow Config Seeding
**Branch**: `feature/DA-943`
**Repo**: `canvastekk-workflow-sdk`
**Priority**: P2
**Size**: S
**Status**: In Progress

---

## Problem

External node authors have no guide for the end-to-end workflow: create a node with the SDK, containerize it, deploy it, and register it with the workflow engine. The new `service_token` auth mode (DA-931) and CI/CD registration pipeline also need documentation.

## Context

Part of the **DA-929** epic. DA-931 added `service_token` support to `register_node()`. This ticket creates the external-facing documentation so third-party authors can independently build, deploy, and register nodes.

---

## Files to Change

| File | Change |
|------|--------|
| `docs/external-author-guide.md` | New file — step-by-step guide |
| `README.md` | Add link to external author guide |

---

## Acceptance Criteria

- [ ] Step-by-step guide: create node with SDK, deploy, register with engine
- [ ] Documents required secrets (API key for non-CDS, API key + Keycloak for CDS)
- [ ] Example CI/CD pipeline (GitHub Actions)
- [ ] Error handling guidance (403 = wrong owner, 401 = bad key)

---

## Implementation Phases

### Phase 1: Create `docs/external-author-guide.md`

- [ ] Introduction and overview of the end-to-end workflow
- [ ] Prerequisites (Python 3.12+, Docker, GitHub account)
- [ ] Step-by-step: create a node with the SDK
- [ ] Step-by-step: containerize with Docker
- [ ] Step-by-step: deploy the node
- [ ] Step-by-step: register with the engine
- [ ] Required secrets section (API key, service token, Keycloak)
- [ ] Example GitHub Actions CI/CD pipeline
- [ ] Error handling reference table (401, 403, 404, 409, 500)

### Phase 2: Update `README.md`

- [ ] Add link to `docs/external-author-guide.md` in the relevant section

### Phase 3: Validate and deliver

- [ ] Review all acceptance criteria
- [ ] Commit and push
- [ ] Update JIRA ticket with progress

---

## Dependencies

- **DA-931** (T10): SDK `register_node()` service token support — **Done**

## Security Notes

- Never include actual token values in documentation
- Use placeholder values like `svs_xxx`, `your-api-key`, `your-service-token`
- Document that secrets must come from GitHub Secrets or equivalent

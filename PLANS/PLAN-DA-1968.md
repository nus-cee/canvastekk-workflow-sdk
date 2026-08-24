# PLAN-DA-1968 — Fix `npm run lint` in SDK typescript track (commit eslint 9 flat config)

Ticket: DA-1968 (id 18065) · Repo: canvastekk-workflow-sdk · Target: `main` (no dev branch) · Worktree: `worktrees/DA-1968-eslint-flat` @ `b546a8b` (= origin/main, v0.23.0) · Plan v2 (3-subagent review folded)

## Problem

`typescript/package.json` has `"lint": "eslint src/ tests/"` with `eslint` + `typescript-eslint` declared via `^9`/`^8` ranges (installed: 9.39.4 / 8.60.0), but **no flat config is committed** (verified: no `.eslintrc*`, no `eslint.config.*` anywhere outside node_modules). eslint 9 removed legacy-config support, so `npx eslint src/ tests/` dies with the config-migration error (reproduced in worktree). CI (`.github/workflows/ci-typescript.yml:41-43`) runs the Lint step with `continue-on-error: true`, so the breakage is invisible to check status — lint gates nothing today.

Facts verified in worktree:
- `@eslint/js@9.39.4` present as transitive dep (NOT declared); node v24.18.0; `npm ci --legacy-peer-deps` clean.
- `tsconfig.json`: `strict: true`, `module/nodenext`, `target ESNext`, `isolatedModules`, includes only `src/` — **tests are excluded from tsconfig** (hard blocker for type-checked presets, which require `parserOptions.project` membership).
- Package is ESM (`"type": "module"`) → config must be `eslint.config.js` with `export default`.
- ~32 `.ts` files across `src/` (19 top-level entries incl. subdirs) and 20 in `tests/`.
- Repo root has NO package.json; node_modules lives at `typescript/node_modules` → config MUST sit at `typescript/eslint.config.js` (a root config couldn't resolve its own imports).

## Dependency & Consumer Map

```
typescript/eslint.config.js (NEW)
  ├─ consumed by: npm run lint (package.json script — src/ + tests/)
  ├─ consumed by: .github/workflows/ci-typescript.yml Lint step (line 41)
  └─ consumed by: editors/IDEs of all future contributors (auto-discovery)
@eslint/js promoted to direct devDependency (imported by the config — was phantom/transitive)
  ├─ package.json + package-lock.json change (only dep change in this ticket)
CI Lint step (continue-on-error removal) ← the only workflow file touched.
release.yml does NOT run lint (build→publish→verify only) — unaffected by this ticket.
No production code depends on lint; violation fixes are lint-only, proven by gates.
Zero changes to: tsconfig, src/ exports, other workflows.
```

## Phase 1 — Config + dependency

- [x] 1.1 Create `typescript/eslint.config.js`:
      ```js
      import js from "@eslint/js";
      import tseslint from "typescript-eslint";

      export default tseslint.config(
        { ignores: ["dist/", "coverage/"] },
        js.configs.recommended,
        ...tseslint.configs.recommended,
        { languageOptions: { ecmaVersion: "latest", sourceType: "module" } },
      );
      ```
      *Why*: eslint 9 hard-requires a flat config at the package root; none committed. `recommended` (not `recommendedTypeChecked`) — type-aware linting is blocked by tsconfig excluding `tests/` (`parserOptions.project` requires membership) and is materially slower; strictness already enforced by the `tsc --noEmit` gate. NOTE: must import `@eslint/js` explicitly — `tseslint.config()` silently drops `undefined` entries, so a wrong `eslint.configs` reference would gut core rules with zero symptoms.
      *Done when*: `npx eslint src/ tests/` reports rule findings (or zero) instead of a config error.
      *Consumers*: lint script, CI, editors.
- [x] 1.2 `npm install --save-dev @eslint/js` — promote from phantom transitive to declared devDependency (the config imports it; relying on flat-hoisting luck is a smell). Lockfile regenerated.
      *Why*: direct-import hygiene; survives future eslint dep-reshuffles.
      *Done when*: package.json devDeps lists `@eslint/js`, `npm ci` still clean, lint still runs.
      *Consumers*: eslint.config.js import; npm install for all contributors/CI.
- [x] 1.3 Remove `continue-on-error: true` from the Lint step in `.github/workflows/ci-typescript.yml`.
      *Why*: the point of the ticket — lint must gate CI once it passes; today the step cannot fail.
      *Done when*: step removed, workflow YAML valid.
      *Consumers*: ci-typescript workflow on PR + main pushes.

## Phase 2 — Violations (lint-only, zero behavior change)

- [x] 2.1 Run `npx eslint src/ tests/`; fix every reported violation.
      *Why*: AC requires `npm run lint` exit 0.
      *Done when*: zero findings.
      *Consumers*: none at runtime — lint-only edits, proven by Phase 3 gates.
- [x] 2.2 Where a rule fights an intentional pattern, prefer a targeted inline `// eslint-disable-next-line <rule> -- reason` over globally weakening the preset; record any such calls in the commit body.
      *Why*: keeps the preset honest for future code instead of carving permanent exemptions into the config.
      *Done when*: any disables present are line-scoped and reasoned.
      *Consumers*: future contributors reading the code (the comment documents intent).

## Phase 3 — Gates (mirror the CI step list exactly)

- [x] 3.1 `npm run lint` exit 0.
- [x] 3.2 `npx tsc --noEmit` green (baseline: passing at b546a8b).
- [x] 3.3 `npx vitest run --coverage` — 289 tests passed (same invocation CI uses).
- [x] 3.4 `npm run build` green (tsup).
      *Why for all*: AC = lint fixed WITHOUT breaking typecheck/tests/build; steps mirror ci-typescript.yml.

## Phase 4 — Ship

- [x] 4.1 Atomic commits (conventional, `[DA-1968]` suffix, ≤120 chars header/body):
      `docs(plans): add PLAN-DA-1968 [DA-1968]`
      `chore(deps): declare @eslint/js dev dependency [DA-1968]`
      `chore(lint): commit eslint 9 flat config and gate CI lint [DA-1968]` (config + workflow)
      `style(lint): resolve eslint findings in src and tests [DA-1968]` (violations, if any)
- [ ] 4.2 pr-workflow-subagent: PR → `main`, squash-merge, **CI green including the now-gating Lint step**, remote branch deleted. PR body must surface the continue-on-error removal (only workflow behavior change).
- [ ] 4.3 JIRA 18065: merge comment + Done (transition 41) via `/tmp/opencode/jira` client.
- [ ] 4.4 Worktree removed, local branch deleted. Tick remaining boxes in this PLAN.

## Risks

- **Recommended preset churn**: fixes must stay lint-only; any change that alters runtime behavior is a plan violation → revert and use a scoped disable instead.
- **release.yml does NOT run lint** (pre-existing, out of scope): a lint-red direct push to main would still release. Do not assume lint blocks releases; file as follow-up if release-gating is wanted.
- **No type-aware rules**: blocked by tsconfig excluding tests/ + perf; a future ticket can raise strictness deliberately (would need parserOptions.project + tsconfig include change).
- **Rollback**: reverting the commits restores status quo (lint broken but non-gating) — no data/contract surface.

## Out of scope

- Python-track lint (ruff already gates in ci-python.yml).
- Prettier / formatting tooling; type-checked presets; engine repo (CWE); custom rule authoring; making release.yml run lint.

# PLAN: SDK — attach the TypeScript tarball to GitHub Releases (DA-2677 enabler)

**Branch**: fix/da2677-release-tarball-asset (base: main — the SDK repo's integration branch)
**Issue**: https://betekk.atlassian.net/browse/DA-2677

## Why

ifc-service-app must pin `@nus-cee/canvastekk-workflow-sdk` at an exact published version
(DA-2677). Two publish channels exist today: GitHub Packages (needs a `read:packages`
token for every consumer — CI, every dev, every local `npm install`) and the GitHub
Release (public assets, zero auth). Every python consumer already pins via release-asset
URL (`.../releases/download/vX/canvastekk_workflow_sdk-X-py3-none-any.whl`), but releases
attach only the wheel — the ts tarball is missing. Attaching it gives TS consumers the
same no-auth, exact-version pin channel.

## Done when

- release.yml gains a "Build and upload TypeScript SDK to GitHub Release" step (npm pack
  after the existing build, uploaded as `canvastekk-workflow-sdk-<ver>.tgz`, mirroring the
  wheel step's shape and guard conditions)
- v0.28.1 is backfilled with the tarball built from the v0.28.1 tag commit (same
  provenance rule the wheel step enforces: built from the tagged commit)
- Gates: this is workflow-only for the future; the backfilled asset is verified by
  installing it in the ifc worktree (its npm ci + vitest gate exercises it end-to-end)

## Consumers affected

- Future SDK releases (one extra step, no behavior change to existing channels)
- DA-2677's ifc adoption (consumes the v0.28.1 tarball URL)

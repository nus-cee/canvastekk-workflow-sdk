/** Tests for manifest diff classification (DA-1955). */

import { describe, expect, it } from "vitest";

import { diffManifests } from "../src/diff.js";

function manifest(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    name: "test-node",
    version: "1.0.0",
    input_schema: { type: "object", properties: {}, required: [] },
    output_schema: { type: "object", properties: {} },
    ...overrides,
  };
}

describe("breaking classification", () => {
  it("removed output is breaking", () => {
    const old = manifest({ output_schema: { type: "object", properties: { result: { type: "string" } } } });
    const next = manifest({ version: "2.0.0", output_schema: { type: "object", properties: {} } });

    const diff = diffManifests(old, next);

    expect(diff.breaking).toBe(true);
    expect(diff.breakingChanges.some((e) => e.includes("removed output") && e.includes("result"))).toBe(true);
  });

  it("new required input is breaking", () => {
    const old = manifest({ input_schema: { type: "object", properties: { msg: { type: "string" } }, required: [] } });
    const next = manifest({
      version: "2.0.0",
      input_schema: {
        type: "object",
        properties: { msg: { type: "string" }, data: { type: "string" } },
        required: ["data"],
      },
    });

    const diff = diffManifests(old, next);

    expect(diff.breaking).toBe(true);
    expect(diff.breakingChanges.some((e) => e.includes("new required input") && e.includes("data"))).toBe(true);
  });

  it("breaking with major bump has no version error", () => {
    const old = manifest({ output_schema: { type: "object", properties: { result: { type: "string" } } } });
    const next = manifest({ version: "2.0.0", output_schema: { type: "object", properties: {} } });

    const diff = diffManifests(old, next);

    expect(diff.breaking).toBe(true);
    expect(diff.errors.some((e) => e.includes("MAJOR"))).toBe(false);
  });
});

describe("non-breaking classification", () => {
  it("new optional input is not breaking", () => {
    const old = manifest();
    const next = manifest({
      version: "1.1.0",
      input_schema: { type: "object", properties: { opt: { type: "string" } }, required: [] },
    });

    const diff = diffManifests(old, next);

    expect(diff.breaking).toBe(false);
    expect(diff.nonBreakingChanges.some((e) => e.includes("new optional input") && e.includes("opt"))).toBe(true);
    expect(diff.breakingChanges).toEqual([]);
  });

  it("new output is not breaking", () => {
    const old = manifest();
    const next = manifest({ version: "1.1.0", output_schema: { type: "object", properties: { extra: { type: "string" } } } });

    const diff = diffManifests(old, next);

    expect(diff.breaking).toBe(false);
    expect(diff.nonBreakingChanges.some((e) => e.includes("new output") && e.includes("extra"))).toBe(true);
  });

  it("metadata-only change is not breaking", () => {
    const old = manifest({ title: "Old Title" });
    const next = manifest({ version: "1.0.1", title: "New Title" });

    const diff = diffManifests(old, next);

    expect(diff.breaking).toBe(false);
    expect(diff.nonBreakingChanges.some((e) => e.includes("metadata") && e.includes("title"))).toBe(true);
  });
});

describe("version rules", () => {
  it("same version with change is error", () => {
    const diff = diffManifests(manifest({ title: "Old" }), manifest({ title: "New" }));

    expect(diff.breaking).toBe(false);
    expect(diff.errors.some((e) => e.includes("same version"))).toBe(true);
  });

  it("same version identical is clean", () => {
    const diff = diffManifests(manifest(), manifest());

    expect(diff.breaking).toBe(false);
    expect(diff.breakingChanges).toEqual([]);
    expect(diff.nonBreakingChanges).toEqual([]);
    expect(diff.errors).toEqual([]);
  });

  it("breaking with minor bump is error", () => {
    const old = manifest({ output_schema: { type: "object", properties: { result: { type: "string" } } } });
    const next = manifest({ version: "1.1.0", output_schema: { type: "object", properties: {} } });

    const diff = diffManifests(old, next);

    expect(diff.breaking).toBe(true);
    expect(diff.errors.some((e) => e.includes("MAJOR version bump"))).toBe(true);
  });

  it("version bump classification", () => {
    expect(diffManifests(manifest(), manifest({ version: "2.0.0" })).versionBump).toBe("major");
    expect(diffManifests(manifest(), manifest({ version: "1.1.0" })).versionBump).toBe("minor");
    expect(diffManifests(manifest(), manifest({ version: "1.0.1" })).versionBump).toBe("patch");
    expect(diffManifests(manifest(), manifest()).versionBump).toBeNull();
  });

  it("versions recorded on result", () => {
    const diff = diffManifests(manifest(), manifest({ version: "1.1.0" }));

    expect(diff.oldVersion).toBe("1.0.0");
    expect(diff.newVersion).toBe("1.1.0");
  });
});

describe("error cases", () => {
  it("name mismatch is error", () => {
    const diff = diffManifests(manifest({ name: "old-node" }), manifest({ name: "new-node", version: "2.0.0" }));

    expect(diff.errors.some((e) => e.includes("name mismatch"))).toBe(true);
  });

  it("missing version is error", () => {
    const diff = diffManifests({ name: "test-node", input_schema: {} }, manifest({ version: "1.1.0" }));

    expect(diff.errors.some((e) => e.includes("version"))).toBe(true);
  });

  it("non-strict version is error", () => {
    const diff = diffManifests(manifest({ version: "1.0" }), manifest({ version: "1.1" }));

    expect(diff.errors.some((e) => e.includes("MAJOR.MINOR.PATCH"))).toBe(true);
  });

  it("non-object input throws TypeError", () => {
    expect(() => diffManifests("not an object", manifest())).toThrow(TypeError);
  });
});

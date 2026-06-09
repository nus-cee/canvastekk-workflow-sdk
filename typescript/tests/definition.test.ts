import { describe, it, expect, vi } from "vitest";
import {
  WorkflowNodeManifestSchema,
  NodeRoleSchema,
  getNodeId,
  getFileInputFields,
  getFileOutputFields,
  validateFileInput,
} from "../src/definition.js";
import { NodeValidationError } from "../src/exceptions.js";

const validDefinition = {
  name: "my-node",
  version: "1.0.0",
  title: "My Node",
  description: "A test node",
  input_schema: {
    type: "object",
    properties: {
      message: { type: "string" },
    },
  },
  output_schema: {
    type: "object",
    properties: {
      result: { type: "string" },
    },
  },
};

describe("WorkflowNodeManifestSchema", () => {
  it("parses a valid definition", () => {
    const def = WorkflowNodeManifestSchema.parse(validDefinition);
    expect(def.name).toBe("my-node");
    expect(def.version).toBe("1.0.0");
    expect(def.title).toBe("My Node");
    expect(def.token_cost).toBe(0.0);
    expect(def.category).toBe("utility");
    expect(def.timeout_seconds).toBe(30);
    expect(def.role).toBe("operation");
    expect(def.styles).toBeNull();
  });

  it("rejects invalid slug name", () => {
    expect(() =>
      WorkflowNodeManifestSchema.parse({ ...validDefinition, name: "MyNode" }),
    ).toThrow(/lowercase slug/);
  });

  it("rejects name with leading hyphen", () => {
    expect(() =>
      WorkflowNodeManifestSchema.parse({ ...validDefinition, name: "-node" }),
    ).toThrow(/lowercase slug/);
  });

  it("rejects name with trailing hyphen", () => {
    expect(() =>
      WorkflowNodeManifestSchema.parse({ ...validDefinition, name: "node-" }),
    ).toThrow(/lowercase slug/);
  });

  it("rejects invalid semver version", () => {
    expect(() =>
      WorkflowNodeManifestSchema.parse({ ...validDefinition, version: "1.0" }),
    ).toThrow(/semantic version/);
  });

  it("rejects format: binary (DA-894)", () => {
    expect(() =>
      WorkflowNodeManifestSchema.parse({
        ...validDefinition,
        input_schema: {
          type: "object",
          properties: {
            file: { type: "string", format: "binary" },
          },
        },
      }),
    ).toThrow(/binary.*no longer supported/);
  });

  it("rejects file field with non-string type", () => {
    expect(() =>
      WorkflowNodeManifestSchema.parse({
        ...validDefinition,
        input_schema: {
          type: "object",
          properties: {
            file: { type: "object", format: "file" },
          },
        },
      }),
    ).toThrow(/format 'file' but type is/);
  });

  it("accepts file field with type string", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      input_schema: {
        type: "object",
        properties: {
          modelFile: {
            type: "string",
            format: "file",
            "x-accept": [".ply", ".las"],
            "x-maxSizeBytes": 1073741824,
          },
        },
      },
    });
    expect(def.input_schema).toBeDefined();
  });

  it("strips manual id and warns", () => {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      id: "manual-id",
    });
    expect(def).not.toHaveProperty("id");
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("deprecated"),
    );
    spy.mockRestore();
  });

  it("applies default retry config", () => {
    const def = WorkflowNodeManifestSchema.parse(validDefinition);
    expect(def.default_retry.max_attempts).toBe(1);
    expect(def.default_retry.initial_delay_ms).toBe(1000);
    expect(def.default_retry.backoff_multiplier).toBe(2.0);
    expect(def.default_retry.max_delay_ms).toBe(30000);
  });

  it("accepts styles with color and icon", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      styles: { icon: "Brain", color: "emerald" },
    });
    expect(def.styles?.icon).toBe("Brain");
    expect(def.styles?.color).toBe("emerald");
  });

  it("rejects invalid color preset", () => {
    expect(() =>
      WorkflowNodeManifestSchema.parse({
        ...validDefinition,
        styles: { icon: "Box", color: "not-a-color" },
      }),
    ).toThrow();
  });
});

describe("getNodeId", () => {
  it("derives id from name and version", () => {
    expect(getNodeId({ name: "segment", version: "1.2.0" })).toBe(
      "segment-v1.2.0",
    );
  });
});

describe("getFileInputFields", () => {
  it("returns file input field names", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      input_schema: {
        type: "object",
        properties: {
          text: { type: "string" },
          model: { type: "string", format: "file" },
          data: { type: "string", format: "file" },
        },
      },
    });
    expect(getFileInputFields(def)).toEqual(["model", "data"]);
  });

  it("returns empty array when no file inputs", () => {
    const def = WorkflowNodeManifestSchema.parse(validDefinition);
    expect(getFileInputFields(def)).toEqual([]);
  });
});

describe("getFileOutputFields", () => {
  it("returns file output field names", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      output_schema: {
        type: "object",
        properties: {
          result: { type: "string" },
          outputFile: { type: "string", format: "file" },
        },
      },
    });
    expect(getFileOutputFields(def)).toEqual(["outputFile"]);
  });
});

describe("validateFileInput", () => {
  it("throws on disallowed extension", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      input_schema: {
        type: "object",
        properties: {
          model: {
            type: "string",
            format: "file",
            "x-accept": [".ply", ".las"],
          },
        },
      },
    });
    expect(() => validateFileInput(def, "model", "/tmp/file.xyz")).toThrow(
      NodeValidationError,
    );
  });

  it("passes on allowed extension", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      input_schema: {
        type: "object",
        properties: {
          model: {
            type: "string",
            format: "file",
            "x-accept": [".ply", ".las"],
          },
        },
      },
    });
    expect(() => validateFileInput(def, "model", "/tmp/file.ply")).not.toThrow();
  });

  it("passes when no x-accept constraint", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      input_schema: {
        type: "object",
        properties: {
          model: { type: "string", format: "file" },
        },
      },
    });
    expect(() => validateFileInput(def, "model", "/tmp/file.anything")).not.toThrow();
  });
});

describe("NodeRoleSchema", () => {
  it("accepts all valid roles", () => {
    for (const role of ["start", "end", "error_gate", "operation"]) {
      expect(NodeRoleSchema.parse(role)).toBe(role);
    }
  });

  it("rejects invalid roles", () => {
    expect(() => NodeRoleSchema.parse("invalid")).toThrow();
  });

  it("defaults to operation", () => {
    expect(NodeRoleSchema.parse(undefined)).toBe("operation");
  });

  it("WorkflowNodeManifestSchema defaults role to operation", () => {
    const def = WorkflowNodeManifestSchema.parse(validDefinition);
    expect(def.role).toBe("operation");
  });

  it("WorkflowNodeManifestSchema accepts explicit roles", () => {
    const def = WorkflowNodeManifestSchema.parse({
      ...validDefinition,
      role: "start",
    });
    expect(def.role).toBe("start");
  });
});

describe("backward-compat type aliases", () => {
  it("WorkflowNodeDefinition type compiles as WorkflowNodeManifest", () => {
    type Assert<T extends WorkflowNodeManifest> = T;
    const def: WorkflowNodeManifest = WorkflowNodeManifestSchema.parse(validDefinition);
    const _check: Assert<typeof def> = def;
    expect(_check.name).toBe("my-node");
  });

  it("re-exports WorkflowNodeDefinition from index", async () => {
    const mod = await import("../src/index.js");
    expect(mod.WorkflowNodeManifestSchema).toBeDefined();
  });

  it("WorkflowNodeStylesSchema is WorkflowNodeStylesSchema alias", async () => {
    const mod = await import("../src/index.js");
    expect(mod.WorkflowNodeStylesSchema).toBeDefined();
    expect(mod.NodeStylesSchema).toBeDefined();
  });

  it("WorkflowNodeRoleSchema is WorkflowNodeRoleSchema alias", async () => {
    const mod = await import("../src/index.js");
    expect(mod.WorkflowNodeRoleSchema).toBeDefined();
    expect(mod.NodeRoleSchema).toBeDefined();
  });

  it("WorkflowNodeStylesSchema parses styles", async () => {
    const { WorkflowNodeStylesSchema } = await import("../src/definition.js");
    const styles = WorkflowNodeStylesSchema.parse({ icon: "Brain", color: "emerald" });
    expect(styles.icon).toBe("Brain");
    expect(styles.color).toBe("emerald");
  });

  it("WorkflowNodeRoleSchema parses roles", async () => {
    const { WorkflowNodeRoleSchema } = await import("../src/definition.js");
    expect(WorkflowNodeRoleSchema.parse("start")).toBe("start");
    expect(WorkflowNodeRoleSchema.parse(undefined)).toBe("operation");
  });
});

import { describe, it, expect, vi } from "vitest";
import {
  NodeDefinitionSchema,
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

describe("NodeDefinitionSchema", () => {
  it("parses a valid definition", () => {
    const def = NodeDefinitionSchema.parse(validDefinition);
    expect(def.name).toBe("my-node");
    expect(def.version).toBe("1.0.0");
    expect(def.title).toBe("My Node");
    expect(def.token_cost).toBe(0.0);
    expect(def.category).toBe("utility");
    expect(def.timeout_seconds).toBe(30);
    expect(def.is_control_flow).toBe(false);
    expect(def.styles).toBeNull();
  });

  it("rejects invalid slug name", () => {
    expect(() =>
      NodeDefinitionSchema.parse({ ...validDefinition, name: "MyNode" }),
    ).toThrow(/lowercase slug/);
  });

  it("rejects name with leading hyphen", () => {
    expect(() =>
      NodeDefinitionSchema.parse({ ...validDefinition, name: "-node" }),
    ).toThrow(/lowercase slug/);
  });

  it("rejects name with trailing hyphen", () => {
    expect(() =>
      NodeDefinitionSchema.parse({ ...validDefinition, name: "node-" }),
    ).toThrow(/lowercase slug/);
  });

  it("rejects invalid semver version", () => {
    expect(() =>
      NodeDefinitionSchema.parse({ ...validDefinition, version: "1.0" }),
    ).toThrow(/semantic version/);
  });

  it("rejects format: binary (DA-894)", () => {
    expect(() =>
      NodeDefinitionSchema.parse({
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
      NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse(validDefinition);
    expect(def.default_retry.max_attempts).toBe(1);
    expect(def.default_retry.initial_delay_ms).toBe(1000);
    expect(def.default_retry.backoff_multiplier).toBe(2.0);
    expect(def.default_retry.max_delay_ms).toBe(30000);
  });

  it("accepts styles with color and icon", () => {
    const def = NodeDefinitionSchema.parse({
      ...validDefinition,
      styles: { icon: "Brain", color: "emerald" },
    });
    expect(def.styles?.icon).toBe("Brain");
    expect(def.styles?.color).toBe("emerald");
  });

  it("rejects invalid color preset", () => {
    expect(() =>
      NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse(validDefinition);
    expect(getFileInputFields(def)).toEqual([]);
  });
});

describe("getFileOutputFields", () => {
  it("returns file output field names", () => {
    const def = NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse({
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
    const def = NodeDefinitionSchema.parse({
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

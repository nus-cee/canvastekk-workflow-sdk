import { describe, it, expect } from "vitest";
import { MetricsCollector, createExecutionMetric, metricToDict } from "../src/observability.js";

describe("MetricsCollector", () => {
  it("returns empty summary when no metrics", () => {
    const collector = new MetricsCollector();
    expect(collector.getSummary()).toEqual({ total_executions: 0 });
  });

  it("records and summarizes metrics", () => {
    const collector = new MetricsCollector();
    collector.record(createExecutionMetric({
      runId: "r1", nodeId: "n1", nodeName: "echo",
      status: "pass", durationMs: 100, tokenUsage: 5,
    }));
    collector.record(createExecutionMetric({
      runId: "r2", nodeId: "n2", nodeName: "echo",
      status: "fail", durationMs: 200, tokenUsage: 0, errorType: "Error",
    }));

    const summary = collector.getSummary() as Record<string, unknown>;
    expect(summary.total_executions).toBe(2);
    expect(summary.pass_count).toBe(1);
    expect(summary.fail_count).toBe(1);
    expect(summary.success_rate).toBe(0.5);
    expect(summary.avg_duration_ms).toBe(150);
    expect(summary.min_duration_ms).toBe(100);
    expect(summary.max_duration_ms).toBe(200);
    expect(summary.total_token_usage).toBe(5);
  });

  it("respects lastN parameter", () => {
    const collector = new MetricsCollector();
    for (let i = 0; i < 10; i++) {
      collector.record(createExecutionMetric({
        runId: `r${i}`, nodeId: `n${i}`, nodeName: "test",
        status: "pass", durationMs: i * 10, tokenUsage: 0,
      }));
    }
    const summary = collector.getSummary(3) as Record<string, unknown>;
    expect(summary.total_executions).toBe(3);
    expect(summary.min_duration_ms).toBe(70);
  });

  it("clears all metrics", () => {
    const collector = new MetricsCollector();
    collector.record(createExecutionMetric({
      runId: "r1", nodeId: "n1", nodeName: "test",
      status: "pass", durationMs: 100, tokenUsage: 0,
    }));
    collector.clear();
    expect(collector.getSummary()).toEqual({ total_executions: 0 });
  });

  it("evicts oldest when over capacity", () => {
    const collector = new MetricsCollector(3);
    for (let i = 0; i < 5; i++) {
      collector.record(createExecutionMetric({
        runId: `r${i}`, nodeId: `n${i}`, nodeName: "test",
        status: "pass", durationMs: i, tokenUsage: 0,
      }));
    }
    const summary = collector.getSummary() as Record<string, unknown>;
    expect(summary.total_executions).toBe(3);
    expect(summary.min_duration_ms).toBe(2);
  });
});

describe("metricToDict", () => {
  it("serializes metric to snake_case dict", () => {
    const metric = createExecutionMetric({
      runId: "r1", nodeId: "n1", nodeName: "echo",
      status: "pass", durationMs: 42, tokenUsage: 1.5,
    });
    const dict = metricToDict(metric);
    expect(dict.run_id).toBe("r1");
    expect(dict.node_id).toBe("n1");
    expect(dict.node_name).toBe("echo");
    expect(dict.duration_ms).toBe(42);
    expect(dict.token_usage).toBe(1.5);
    expect(dict.error_type).toBeNull();
    expect(dict.error_code).toBeNull();
    expect(dict.timestamp).toBeDefined();
  });
});

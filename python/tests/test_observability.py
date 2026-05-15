"""Tests for metrics and observability."""

import concurrent.futures
import threading
from typing import Any

from canvastekk_workflow_sdk import BaseNode, ExecutionContext, NodeDefinition, NodeExecutionRequest
from canvastekk_workflow_sdk.observability import ExecutionMetric, MetricsCollector, get_default_collector


class EchoNode(BaseNode):
    definition = NodeDefinition(
        id="echo-v1.0.0",
        name="echo",
        version="1.0.0",
        title="Echo",
        description="Returns input unchanged",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"message": {"type": "string"}}},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"message": inputs.get("message", "")}


class FailingNode(BaseNode):
    definition = NodeDefinition(
        id="fail-v1.0.0",
        name="fail",
        version="1.0.0",
        title="Fail",
        description="Always fails",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        raise RuntimeError("boom")


class TestExecutionMetric:
    def test_to_dict(self) -> None:
        m = ExecutionMetric(
            run_id="r1",
            node_id="n1",
            node_name="echo",
            status="pass",
            duration_ms=100,
        )
        d = m.to_dict()
        assert d["run_id"] == "r1"
        assert d["status"] == "pass"
        assert d["duration_ms"] == 100
        assert "timestamp" in d

    def test_defaults(self) -> None:
        m = ExecutionMetric(
            run_id="r1",
            node_id="n1",
            node_name="echo",
            status="pass",
            duration_ms=50,
        )
        assert m.error_type is None
        assert m.error_code is None
        assert m.token_usage == 0.0


class TestMetricsCollector:
    def test_empty_summary(self) -> None:
        c = MetricsCollector()
        assert c.get_summary() == {"total_executions": 0}

    def test_record_and_summary(self) -> None:
        c = MetricsCollector()
        c.record(
            ExecutionMetric(
                run_id="r1",
                node_id="n1",
                node_name="echo",
                status="pass",
                duration_ms=100,
                token_usage=1.0,
            )
        )
        c.record(
            ExecutionMetric(
                run_id="r2",
                node_id="n2",
                node_name="echo",
                status="fail",
                duration_ms=200,
                error_type="RuntimeError",
            )
        )

        summary = c.get_summary()
        assert summary["total_executions"] == 2
        assert summary["pass_count"] == 1
        assert summary["fail_count"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["avg_duration_ms"] == 150.0
        assert summary["min_duration_ms"] == 100
        assert summary["max_duration_ms"] == 200
        assert summary["total_token_usage"] == 1.0

    def test_summary_last_n(self) -> None:
        c = MetricsCollector()
        for i in range(10):
            c.record(
                ExecutionMetric(
                    run_id=f"r{i}",
                    node_id="n1",
                    node_name="echo",
                    status="pass",
                    duration_ms=i * 10,
                )
            )

        summary = c.get_summary(last_n=3)
        assert summary["total_executions"] == 3

    def test_max_records_eviction(self) -> None:
        c = MetricsCollector(max_records=5)
        for i in range(10):
            c.record(
                ExecutionMetric(
                    run_id=f"r{i}",
                    node_id="n1",
                    node_name="echo",
                    status="pass",
                    duration_ms=i,
                )
            )
        assert len(c._metrics) == 5

    def test_clear(self) -> None:
        c = MetricsCollector()
        c.record(
            ExecutionMetric(
                run_id="r1",
                node_id="n1",
                node_name="echo",
                status="pass",
                duration_ms=100,
            )
        )
        c.clear()
        assert c.get_summary() == {"total_executions": 0}


class TestNodeMetricsIntegration:
    def test_successful_execution_records_metric(self) -> None:
        collector = MetricsCollector()
        node = EchoNode()
        node.set_metrics_collector(collector)

        node.run(
            NodeExecutionRequest(
                run_id="r1",
                node_id="n1",
                inputs={"message": "hi"},
            )
        )

        summary = collector.get_summary()
        assert summary["total_executions"] == 1
        assert summary["pass_count"] == 1
        assert summary["fail_count"] == 0

    def test_failed_execution_records_metric(self) -> None:
        collector = MetricsCollector()
        node = FailingNode()
        node.set_metrics_collector(collector)

        node.run(
            NodeExecutionRequest(
                run_id="r1",
                node_id="n1",
                inputs={},
            )
        )

        summary = collector.get_summary()
        assert summary["total_executions"] == 1
        assert summary["pass_count"] == 0
        assert summary["fail_count"] == 1

    def test_metrics_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from canvastekk_workflow_sdk import create_node_app

        collector = MetricsCollector()
        node = EchoNode()
        node.set_metrics_collector(collector)

        client = TestClient(create_node_app(node))

        client.post(
            "/execute",
            json={
                "run_id": "r1",
                "node_id": "n1",
                "inputs": {"message": "hi"},
            },
        )

        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_executions"] == 1

    def test_get_default_collector_is_singleton(self) -> None:
        a = get_default_collector()
        b = get_default_collector()
        assert a is b


class TestMetricsCollectorThreadSafety:
    """Tests for thread-safe metrics collection (Phase 1)."""

    def test_concurrent_record_calls(self) -> None:
        """Test that concurrent record() calls don't corrupt metrics."""
        c = MetricsCollector()
        num_threads = 50
        records_per_thread = 100

        def record_metrics(thread_id: int) -> None:
            for i in range(records_per_thread):
                c.record(
                    ExecutionMetric(
                        run_id=f"r{thread_id}-{i}",
                        node_id=f"n{thread_id}",
                        node_name="test",
                        status="pass" if i % 2 == 0 else "fail",
                        duration_ms=i * 10,
                        token_usage=1.0,
                    )
                )

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=record_metrics, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        summary = c.get_summary()
        expected_total = num_threads * records_per_thread
        assert summary["total_executions"] == expected_total
        assert summary["pass_count"] == expected_total // 2
        assert summary["fail_count"] == expected_total // 2
        assert summary["success_rate"] == 0.5

    def test_concurrent_record_and_get_summary(self) -> None:
        """Test that concurrent record() and get_summary() calls work correctly."""
        c = MetricsCollector()

        def record_continuously() -> None:
            for i in range(100):
                c.record(
                    ExecutionMetric(
                        run_id=f"r{i}",
                        node_id="n1",
                        node_name="test",
                        status="pass",
                        duration_ms=i,
                        token_usage=1.0,
                    )
                )

        def read_continuously() -> list[dict[str, Any]]:
            summaries = []
            for _ in range(50):
                summaries.append(c.get_summary())
            return summaries

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(record_continuously),
                executor.submit(record_continuously),
                executor.submit(read_continuously),
            ]
            for future in concurrent.futures.as_completed(futures):
                if not future.result():
                    pass

        summary = c.get_summary()
        assert summary["total_executions"] == 200

    def test_concurrent_clear_operations(self) -> None:
        """Test that concurrent clear() operations don't cause issues."""
        c = MetricsCollector()

        def record_and_clear(thread_id: int) -> None:
            for i in range(50):
                c.record(
                    ExecutionMetric(
                        run_id=f"r{thread_id}-{i}",
                        node_id=f"n{thread_id}",
                        node_name="test",
                        status="pass",
                        duration_ms=i,
                    )
                )
                if i % 10 == 0:
                    c.clear()

        threads = []
        for i in range(10):
            t = threading.Thread(target=record_and_clear, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        final_summary = c.get_summary()
        assert final_summary["total_executions"] >= 0

    def test_get_summary_consistent_during_concurrent_writes(self) -> None:
        """Test that get_summary() returns consistent results during concurrent writes."""
        c = MetricsCollector()

        def record_metrics() -> None:
            for i in range(100):
                c.record(
                    ExecutionMetric(
                        run_id=f"r{i}",
                        node_id="n1",
                        node_name="test",
                        status="pass",
                        duration_ms=i,
                    )
                )

        t = threading.Thread(target=record_metrics)
        t.start()

        summaries_read = []
        for _ in range(50):
            summaries_read.append(c.get_summary())

        t.join()

        assert all(s["total_executions"] >= 0 for s in summaries_read)
        assert all(s["pass_count"] == s["total_executions"] for s in summaries_read)

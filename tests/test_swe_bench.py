"""Tests for SWE-Bench integration module."""

import json
import tempfile
from pathlib import Path

import pytest

from compymac.swe_bench import (
    SWEBenchDashboard,
    SWEBenchDataset,
    SWEBenchResult,
    SWEBenchTask,
    TestResults,
)


class TestSWEBenchTask:
    """Tests for SWEBenchTask dataclass."""

    def test_create_task(self):
        """Test creating a basic task."""
        task = SWEBenchTask(
            instance_id="django__django-12345",
            repo="django/django",
            version="abc123",
            problem_statement="Fix the bug in the model",
        )
        assert task.instance_id == "django__django-12345"
        assert task.repo == "django/django"
        assert task.version == "abc123"
        assert task.difficulty == "medium"  # default

    def test_task_to_dict(self):
        """Test serialization to dict."""
        task = SWEBenchTask(
            instance_id="flask__flask-100",
            repo="pallets/flask",
            version="def456",
            problem_statement="Fix routing issue",
            difficulty="easy",
        )
        data = task.to_dict()
        assert data["instance_id"] == "flask__flask-100"
        assert data["repo"] == "pallets/flask"
        assert data["difficulty"] == "easy"

    def test_task_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "instance_id": "requests__requests-500",
            "repo": "psf/requests",
            "version": "ghi789",
            "problem_statement": "Fix timeout handling",
            "fail_to_pass": ["test_timeout"],
            "pass_to_pass": ["test_basic"],
        }
        task = SWEBenchTask.from_dict(data)
        assert task.instance_id == "requests__requests-500"
        assert task.fail_to_pass == ["test_timeout"]
        assert task.pass_to_pass == ["test_basic"]

    def test_task_roundtrip(self):
        """Test serialization roundtrip."""
        original = SWEBenchTask(
            instance_id="pytest__pytest-999",
            repo="pytest-dev/pytest",
            version="jkl012",
            problem_statement="Fix fixture issue",
            hints_text="Check conftest.py",
            fail_to_pass=["test_fixture"],
            pass_to_pass=["test_basic", "test_other"],
            difficulty="hard",
        )
        data = original.to_dict()
        restored = SWEBenchTask.from_dict(data)
        assert restored.instance_id == original.instance_id
        assert restored.hints_text == original.hints_text
        assert restored.fail_to_pass == original.fail_to_pass
        assert restored.difficulty == original.difficulty


class TestTestResults:
    """Tests for TestResults dataclass."""

    def test_all_pass(self):
        """Test when all tests pass."""
        results = TestResults(
            fail_to_pass={"test1": True, "test2": True},
            pass_to_pass={"test3": True, "test4": True},
        )
        assert results.all_fail_to_pass_passed
        assert results.all_pass_to_pass_passed

    def test_partial_pass(self):
        """Test when some tests fail."""
        results = TestResults(
            fail_to_pass={"test1": True, "test2": False},
            pass_to_pass={"test3": True, "test4": True},
        )
        assert not results.all_fail_to_pass_passed
        assert results.all_pass_to_pass_passed

    def test_empty_fail_to_pass(self):
        """Test with empty fail_to_pass."""
        results = TestResults(
            fail_to_pass={},
            pass_to_pass={"test1": True},
        )
        assert not results.all_fail_to_pass_passed  # Empty returns False
        assert results.all_pass_to_pass_passed


class TestSWEBenchResult:
    """Tests for SWEBenchResult dataclass."""

    def test_create_result(self):
        """Test creating a result."""
        result = SWEBenchResult(
            instance_id="django__django-12345",
            resolved=True,
            partial=False,
            failed=False,
            fail_to_pass_results={"test1": True},
            pass_to_pass_results={"test2": True},
            patch_generated="diff --git a/file.py",
            tool_calls_made=10,
            tokens_used=5000,
            time_elapsed_sec=120.5,
            trace_id="abc-123",
        )
        assert result.resolved
        assert result.tool_calls_made == 10

    def test_result_roundtrip(self):
        """Test serialization roundtrip."""
        original = SWEBenchResult(
            instance_id="flask__flask-100",
            resolved=False,
            partial=True,
            failed=False,
            fail_to_pass_results={"test1": True, "test2": False},
            pass_to_pass_results={"test3": True},
            patch_generated="some patch",
            tool_calls_made=25,
            tokens_used=10000,
            time_elapsed_sec=300.0,
            trace_id="def-456",
            error_log="Some warning",
        )
        data = original.to_dict()
        restored = SWEBenchResult.from_dict(data)
        assert restored.instance_id == original.instance_id
        assert restored.partial == original.partial
        assert restored.error_log == original.error_log


class TestSWEBenchDataset:
    """Tests for SWEBenchDataset loader."""

    def test_load_empty_dataset(self):
        """Test loading when no dataset exists."""
        dataset = SWEBenchDataset(dataset_path=None)
        tasks = dataset.load()
        assert tasks == []

    def test_load_from_file(self):
        """Test loading from a JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "instance_id": "test__test-1",
                        "repo": "test/test",
                        "version": "abc",
                        "problem_statement": "Fix bug",
                    },
                    {
                        "instance_id": "test__test-2",
                        "repo": "test/test",
                        "version": "def",
                        "problem_statement": "Fix another bug",
                    },
                ],
                f,
            )
            f.flush()

            dataset = SWEBenchDataset(dataset_path=Path(f.name))
            tasks = dataset.load()
            assert len(tasks) == 2
            assert tasks[0].instance_id == "test__test-1"

    def test_get_by_id(self):
        """Test getting task by ID."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "instance_id": "test__test-1",
                        "repo": "test/test",
                        "version": "abc",
                        "problem_statement": "Fix bug",
                    },
                ],
                f,
            )
            f.flush()

            dataset = SWEBenchDataset(dataset_path=Path(f.name))
            task = dataset.get_by_id("test__test-1")
            assert task is not None
            assert task.instance_id == "test__test-1"

            missing = dataset.get_by_id("nonexistent")
            assert missing is None


class TestSWEBenchDashboard:
    """Tests for SWEBenchDashboard."""

    def test_empty_report(self):
        """Test generating report with no results."""
        dashboard = SWEBenchDashboard()
        report = dashboard.generate_report()
        assert report.total_tasks == 0
        assert report.resolve_rate == 0.0

    def test_generate_report(self):
        """Test generating report with results."""
        results = [
            SWEBenchResult(
                instance_id="django__django-1",
                resolved=True,
                partial=False,
                failed=False,
                fail_to_pass_results={},
                pass_to_pass_results={},
                patch_generated="",
                tool_calls_made=10,
                tokens_used=1000,
                time_elapsed_sec=60.0,
                trace_id="1",
            ),
            SWEBenchResult(
                instance_id="django__django-2",
                resolved=False,
                partial=True,
                failed=False,
                fail_to_pass_results={},
                pass_to_pass_results={},
                patch_generated="",
                tool_calls_made=20,
                tokens_used=2000,
                time_elapsed_sec=120.0,
                trace_id="2",
            ),
            SWEBenchResult(
                instance_id="flask__flask-1",
                resolved=False,
                partial=False,
                failed=True,
                fail_to_pass_results={},
                pass_to_pass_results={},
                patch_generated="",
                tool_calls_made=5,
                tokens_used=500,
                time_elapsed_sec=30.0,
                trace_id="3",
            ),
        ]
        dashboard = SWEBenchDashboard(results)
        report = dashboard.generate_report()

        assert report.total_tasks == 3
        assert report.resolved == 1
        assert report.partial == 1
        assert report.failed == 1
        assert report.resolve_rate == pytest.approx(1 / 3)
        assert report.avg_tool_calls == pytest.approx(35 / 3)

    def test_breakdown_by_repo(self):
        """Test breakdown by repository."""
        results = [
            SWEBenchResult(
                instance_id="django__django-1",
                resolved=True,
                partial=False,
                failed=False,
                fail_to_pass_results={},
                pass_to_pass_results={},
                patch_generated="",
                tool_calls_made=10,
                tokens_used=1000,
                time_elapsed_sec=60.0,
                trace_id="1",
            ),
            SWEBenchResult(
                instance_id="django__django-2",
                resolved=True,
                partial=False,
                failed=False,
                fail_to_pass_results={},
                pass_to_pass_results={},
                patch_generated="",
                tool_calls_made=10,
                tokens_used=1000,
                time_elapsed_sec=60.0,
                trace_id="2",
            ),
        ]
        dashboard = SWEBenchDashboard(results)
        report = dashboard.generate_report()

        assert "django" in report.by_repo
        assert report.by_repo["django"]["resolved"] == 2

    def test_save_and_load_results(self):
        """Test saving and loading results."""
        results = [
            SWEBenchResult(
                instance_id="test__test-1",
                resolved=True,
                partial=False,
                failed=False,
                fail_to_pass_results={"t1": True},
                pass_to_pass_results={"t2": True},
                patch_generated="patch",
                tool_calls_made=10,
                tokens_used=1000,
                time_elapsed_sec=60.0,
                trace_id="abc",
            ),
        ]
        dashboard = SWEBenchDashboard(results)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = Path(f.name)

        dashboard.save_results(path)

        new_dashboard = SWEBenchDashboard()
        new_dashboard.load_results(path)

        assert len(new_dashboard.results) == 1
        assert new_dashboard.results[0].instance_id == "test__test-1"
        assert new_dashboard.results[0].resolved

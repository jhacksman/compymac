"""Tests for Gap 6 Phase 1: Structured Agent Handoffs."""


from compymac.workflows.agent_handoffs import (
    AgentArtifactType,
    HandoffManager,
    HandoffValidationStatus,
    HandoffValidator,
    ProblemStatement,
    StructuredHandoff,
)


class TestAgentArtifactType:
    """Tests for AgentArtifactType enum."""

    def test_all_types_exist(self):
        assert AgentArtifactType.PROBLEM_STATEMENT.value == "problem_statement"
        assert AgentArtifactType.EXECUTION_PLAN.value == "execution_plan"
        assert AgentArtifactType.FILE_TARGETS.value == "file_targets"
        assert AgentArtifactType.PATCH_PLAN.value == "patch_plan"
        assert AgentArtifactType.CODE_CHANGE.value == "code_change"
        assert AgentArtifactType.TEST_PLAN.value == "test_plan"
        assert AgentArtifactType.TEST_RESULT.value == "test_result"
        assert AgentArtifactType.FAILURE_ANALYSIS.value == "failure_analysis"
        assert AgentArtifactType.REVIEW_FEEDBACK.value == "review_feedback"
        assert AgentArtifactType.PR_DESCRIPTION.value == "pr_description"
        assert AgentArtifactType.REFLECTION.value == "reflection"


class TestProblemStatement:
    """Tests for ProblemStatement dataclass."""

    def test_to_dict(self):
        ps = ProblemStatement(
            summary="Fix bug in login",
            root_cause_hypothesis="Session timeout",
            affected_components=["auth", "session"],
            constraints=["no breaking changes"],
            success_criteria=["tests pass"],
        )
        result = ps.to_dict()
        assert result["summary"] == "Fix bug in login"
        assert result["root_cause_hypothesis"] == "Session timeout"
        assert result["affected_components"] == ["auth", "session"]
        assert result["constraints"] == ["no breaking changes"]
        assert result["success_criteria"] == ["tests pass"]

    def test_from_dict(self):
        data = {
            "summary": "Test summary",
            "root_cause_hypothesis": "Test hypothesis",
            "affected_components": ["comp1"],
            "constraints": [],
            "success_criteria": ["criterion1"],
        }
        ps = ProblemStatement.from_dict(data)
        assert ps.summary == "Test summary"
        assert ps.root_cause_hypothesis == "Test hypothesis"
        assert ps.affected_components == ["comp1"]


class TestStructuredHandoff:
    """Tests for StructuredHandoff dataclass."""

    def test_creates_handoff_id(self):
        handoff = StructuredHandoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": []},
        )
        assert handoff.handoff_id != ""
        assert len(handoff.handoff_id) == 12

    def test_to_dict(self):
        handoff = StructuredHandoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test"}]},
        )
        result = handoff.to_dict()
        assert result["from_agent"] == "planner"
        assert result["to_agent"] == "executor"
        assert result["artifact_type"] == "execution_plan"
        assert result["content"]["steps"][0]["description"] == "Test"
        assert result["validation_status"] == "pending"

    def test_from_dict(self):
        data = {
            "handoff_id": "abc123",
            "from_agent": "executor",
            "to_agent": "reflector",
            "artifact_type": "test_result",
            "content": {"passed": True, "output": "OK"},
            "validation_status": "passed",
            "validation_errors": [],
        }
        handoff = StructuredHandoff.from_dict(data)
        assert handoff.handoff_id == "abc123"
        assert handoff.from_agent == "executor"
        assert handoff.to_agent == "reflector"
        assert handoff.artifact_type == AgentArtifactType.TEST_RESULT
        assert handoff.content["passed"] is True


class TestHandoffValidator:
    """Tests for HandoffValidator."""

    def test_validate_valid_execution_plan(self):
        validator = HandoffValidator()
        handoff = StructuredHandoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test step"}]},
        )
        is_valid, errors = validator.validate(handoff)
        assert is_valid is True
        assert errors == []
        assert handoff.validation_status == HandoffValidationStatus.PASSED

    def test_validate_missing_required_field(self):
        validator = HandoffValidator()
        handoff = StructuredHandoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={},  # Missing 'steps'
        )
        is_valid, errors = validator.validate(handoff)
        assert is_valid is False
        assert any("steps" in e for e in errors)
        assert handoff.validation_status == HandoffValidationStatus.FAILED

    def test_validate_empty_steps(self):
        validator = HandoffValidator()
        handoff = StructuredHandoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": []},  # Empty steps
        )
        is_valid, errors = validator.validate(handoff)
        assert is_valid is False
        assert any("at least one step" in e for e in errors)

    def test_validate_invalid_transition(self):
        validator = HandoffValidator()
        handoff = StructuredHandoff(
            from_agent="executor",
            to_agent="planner",  # Invalid: executor can't hand off to planner
            artifact_type=AgentArtifactType.TEST_RESULT,
            content={"passed": True, "output": "OK"},
        )
        is_valid, errors = validator.validate(handoff)
        assert is_valid is False
        assert any("Invalid transition" in e for e in errors)

    def test_validate_test_result(self):
        validator = HandoffValidator()
        handoff = StructuredHandoff(
            from_agent="executor",
            to_agent="reflector",
            artifact_type=AgentArtifactType.TEST_RESULT,
            content={"passed": True, "output": "All tests passed"},
        )
        is_valid, errors = validator.validate(handoff)
        assert is_valid is True
        assert errors == []

    def test_validate_failure_analysis(self):
        validator = HandoffValidator()
        handoff = StructuredHandoff(
            from_agent="executor",
            to_agent="reflector",
            artifact_type=AgentArtifactType.FAILURE_ANALYSIS,
            content={
                "failure_type": "test_failure",
                "error_message": "AssertionError: expected 1, got 2",
            },
        )
        is_valid, errors = validator.validate(handoff)
        assert is_valid is True
        assert errors == []


class TestHandoffManager:
    """Tests for HandoffManager."""

    def test_create_handoff(self):
        manager = HandoffManager()
        handoff = manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test"}]},
        )
        assert handoff.from_agent == "planner"
        assert handoff.to_agent == "executor"
        assert handoff.validation_status == HandoffValidationStatus.PASSED

    def test_create_handoff_without_validation(self):
        manager = HandoffManager()
        handoff = manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={},  # Invalid but validation skipped
            validate=False,
        )
        assert handoff.validation_status == HandoffValidationStatus.PENDING

    def test_get_handoffs_for_agent(self):
        manager = HandoffManager()
        manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test"}]},
        )
        manager.create_handoff(
            from_agent="executor",
            to_agent="reflector",
            artifact_type=AgentArtifactType.TEST_RESULT,
            content={"passed": True, "output": "OK"},
        )

        executor_handoffs = manager.get_handoffs_for_agent("executor")
        assert len(executor_handoffs) == 1
        assert executor_handoffs[0].from_agent == "planner"

        reflector_handoffs = manager.get_handoffs_for_agent("reflector")
        assert len(reflector_handoffs) == 1
        assert reflector_handoffs[0].from_agent == "executor"

    def test_get_handoffs_from_agent(self):
        manager = HandoffManager()
        manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test"}]},
        )
        manager.create_handoff(
            from_agent="planner",
            to_agent="manager",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test2"}]},
        )

        planner_handoffs = manager.get_handoffs_from_agent("planner")
        assert len(planner_handoffs) == 2

    def test_get_latest_handoff(self):
        manager = HandoffManager()
        manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "First"}]},
        )
        manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Second"}]},
        )

        latest = manager.get_latest_handoff(AgentArtifactType.EXECUTION_PLAN)
        assert latest is not None
        assert latest.content["steps"][0]["description"] == "Second"

    def test_get_validation_stats(self):
        manager = HandoffManager()
        manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test"}]},
        )
        manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={},  # Invalid - will fail validation
        )

        stats = manager.get_validation_stats()
        assert stats["total_handoffs"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["pass_rate"] == 0.5

    def test_clear_history(self):
        manager = HandoffManager()
        manager.create_handoff(
            from_agent="planner",
            to_agent="executor",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={"steps": [{"index": 0, "description": "Test"}]},
        )
        assert len(manager.handoff_history) == 1

        manager.clear_history()
        assert len(manager.handoff_history) == 0

"""
AgentLoop - Turn-based agent execution against a Harness.

This module implements the core agent loop that:
1. Receives user input
2. Sends context to LLM
3. Parses tool calls from LLM response
4. Executes tools through the Harness
5. Feeds results back to LLM
6. Repeats until task complete or max steps reached

The loop is harness-agnostic - it works with Simulator, LocalHarness, or ReplayHarness.

Supports optional TraceContext for complete execution capture including:
- Every main loop iteration (even pure reasoning with no tools)
- Every LLM request/response
- Every tool call (delegated to Harness)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from compymac.harness import EventLog, EventType, Harness
from compymac.llm import LLMClient
from compymac.types import Message, ToolCall, ToolResult

if TYPE_CHECKING:
    from compymac.memory import MemoryManager
    from compymac.storage.run_store import RunStore
    from compymac.trace_store import TraceContext, TraceStore
    from compymac.workflows.ci_integration import CIIntegration
    from compymac.workflows.failure_recovery import FailureRecovery
    from compymac.workflows.swe_loop import SWEWorkflow

logger = logging.getLogger(__name__)

# Guided-Structured Templates (arxiv:2509.18076)
# These templates guide the model through deliberate step-by-step reasoning before tool selection.
# Key insight: Free-form Chain-of-Thought is "insufficient and sometimes counterproductive" for
# structured function-calling tasks. Curriculum-inspired templates improve tool calling accuracy.
GUIDED_TOOL_SELECTION_TEMPLATE = """Before responding, follow this structured reasoning process:

## Step 1: Intent Analysis
What is the user asking for? Identify the core request and any constraints.

## Step 2: Tool Selection
Review the available tools. Which tool(s) are relevant to this request?
- List each potentially relevant tool
- For each tool, explain why it matches or doesn't match the user's intent

## Step 3: Parameter Extraction
For the selected tool(s), identify the required parameters:
- What values should each parameter have?
- Are there any implicit values that need to be inferred?

## Step 4: Execution Plan
State your plan: "I will call [tool_name] with [parameters] to [achieve goal]"

## Step 5: Execute
Now make the tool call(s) as planned. You MUST call at least one tool.

IMPORTANT: Do NOT respond with text only. You MUST make a tool call to complete this request."""

# Stronger template for retry after tool_choice violation
GUIDED_TOOL_SELECTION_RETRY_TEMPLATE = """CRITICAL: Your previous response did not include a tool call. This is REQUIRED.

You MUST call a tool. Follow this exact process:

1. TOOL SELECTION: The user's request requires using one of your available tools.
   Look at the tools provided and select the most appropriate one.

2. PARAMETER MAPPING: Map the user's request to the tool's parameters.

3. EXECUTE NOW: Make the tool call immediately. Do not explain, do not apologize.
   Just call the tool with the appropriate parameters.

OUTPUT FORMAT: Your response MUST be a tool call, not text. Example:
{"name": "tool_name", "arguments": {"param": "value"}}

Make the tool call NOW."""


@dataclass
class AgentConfig:
    """Configuration for the agent loop."""
    max_steps: int = 50
    max_tool_calls_per_step: int = 10
    system_prompt: str = ""
    stop_on_error: bool = False
    use_memory: bool = False  # Enable smart memory management
    memory_compression_threshold: float = 0.80  # Compress when utilization exceeds this
    memory_keep_recent_turns: int = 4  # Number of recent turns to always keep
    trace_base_path: Path | None = None  # Base path for trace storage (enables tracing if set)
    summarize_tool_output: bool = True  # Enable tool output summarization to reduce context
    # Action-gated dialogue protocol (MUD-style)
    action_gated: bool = False  # If True, agent must call a tool every turn (no prose-only responses)
    max_invalid_moves: int = 5  # Max consecutive turns without tool calls before failing
    require_complete_tool: bool = False  # If True, agent must call 'complete' tool to finish
    # ACI-style grounding (SWE-agent research)
    force_complete_on_last_step: bool = False  # If True, inject "must call complete" on last step
    grounding_context: dict | None = None  # Context to re-inject every turn (repo_path, cwd, etc.)
    use_active_toolset: bool = False  # If True, use harness.get_active_tool_schemas() instead of get_tool_schemas()
    # Hierarchical tool menu system (reduces context size by only showing relevant tools)
    use_menu_system: bool = False  # If True, use harness.get_menu_tool_schemas() for hierarchical tool discovery
    # Gap 1: Session persistence (enables pause/resume)
    enable_persistence: bool = False  # If True, save run state after each step
    persistence_dir: str = "~/.compymac/runs"  # Directory for run storage
    run_id: str | None = None  # Optional run ID for resuming (auto-generated if None)
    # Gap 3: SWE Workflow Closure (full SWE loop orchestration)
    use_swe_workflow: bool = False  # If True, enable SWE workflow orchestration
    swe_task_description: str = ""  # Task description for workflow
    swe_repo_path: str = ""  # Repository path for workflow
    swe_max_iterations: int = 5  # Max iterations before failing
    # Guided-Structured Templates (arxiv:2509.18076) - improves tool calling compliance
    use_guided_templates: bool = False  # If True, inject structured reasoning templates before tool calls
    guided_template_retry: bool = True  # If True, retry with stronger template on tool_choice violation


@dataclass
class AgentState:
    """Current state of the agent."""
    messages: list[Message] = field(default_factory=list)
    step_count: int = 0
    tool_call_count: int = 0
    is_complete: bool = False
    final_response: str = ""


class AgentLoop:
    """
    Turn-based agent loop that executes against a Harness.

    The loop follows this pattern:
    1. User provides input
    2. Agent sends context to LLM
    3. LLM returns either text response or tool calls
    4. If tool calls: execute through Harness, add results to context, goto 2
    5. If text response: return to user (or continue if not final)
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
        trace_context: "TraceContext | None" = None,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.config = config or AgentConfig()
        self.state = AgentState()
        self._event_log = self.harness.get_event_log()
        self._memory_manager: "MemoryManager | None" = None  # noqa: UP037
        self._trace_context: "TraceContext | None" = trace_context  # noqa: UP037
        self._trace_store: "TraceStore | None" = None  # noqa: UP037
        self._run_store: "RunStore | None" = None  # noqa: UP037
        self._run_id: str | None = self.config.run_id
        self._task_description: str = ""

        # Gap 1: Initialize run store for session persistence
        if self.config.enable_persistence:
            from compymac.storage.run_store import RunStore
            self._run_store = RunStore(self.config.persistence_dir)
            if not self._run_id:
                import uuid
                self._run_id = str(uuid.uuid4())

        # Initialize tracing if base path is configured
        if self.config.trace_base_path and not self._trace_context:
            from compymac.trace_store import TraceContext, create_trace_store
            self._trace_store, _ = create_trace_store(self.config.trace_base_path)
            self._trace_context = TraceContext(self._trace_store)

        # Pass trace context to harness if available
        if self._trace_context:
            self.harness.set_trace_context(self._trace_context)

        # Initialize memory manager if enabled
        if self.config.use_memory:
            from compymac.config import ContextConfig
            from compymac.memory import MemoryManager
            self._memory_manager = MemoryManager(
                config=ContextConfig.from_env(),
                llm_client=llm_client,
                keep_recent_turns=self.config.memory_keep_recent_turns,
                compression_threshold=self.config.memory_compression_threshold,
            )

        # Gap 3: Initialize SWE workflow orchestration if enabled
        self._swe_workflow: "SWEWorkflow | None" = None  # noqa: UP037
        self._failure_recovery: "FailureRecovery | None" = None  # noqa: UP037
        self._ci_integration: "CIIntegration | None" = None  # noqa: UP037
        if self.config.use_swe_workflow:
            from compymac.workflows.ci_integration import CIIntegration
            from compymac.workflows.failure_recovery import FailureRecovery
            from compymac.workflows.swe_loop import SWEWorkflow
            self._swe_workflow = SWEWorkflow(
                task_description=self.config.swe_task_description,
                repo_path=Path(self.config.swe_repo_path) if self.config.swe_repo_path else Path.cwd(),
                max_iterations=self.config.swe_max_iterations,
            )
            self._failure_recovery = FailureRecovery()
            self._ci_integration = CIIntegration(
                repo_path=Path(self.config.swe_repo_path) if self.config.swe_repo_path else None
            )
            logger.info(f"[SWE_WORKFLOW] Initialized workflow for task: {self.config.swe_task_description[:50]}...")

        # Initialize with system prompt if provided
        if self.config.system_prompt:
            self.state.messages.append(Message(
                role="system",
                content=self.config.system_prompt,
            ))

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.state.messages.append(Message(role="user", content=content))

    def add_system_message(self, content: str) -> None:
        """Add a system message to the conversation (injected as user message with system prefix)."""
        self.state.messages.append(Message(role="user", content=f"[SYSTEM]: {content}"))

    def run_step(self) -> tuple[str | None, list[ToolResult]]:
        """
        Run a single step of the agent loop with optional trace capture.

        Returns (text_response, tool_results).
        - If LLM returns text: (text, [])
        - If LLM returns tool calls: (None, [results])
        """
        self.state.step_count += 1

        # Gap 3: Inject SWE workflow stage prompt if workflow is active
        if self._swe_workflow:
            from compymac.workflows.swe_loop import WorkflowStatus
            if self._swe_workflow.status != WorkflowStatus.COMPLETE:
                stage_prompt = self._swe_workflow.get_stage_prompt()
                self.state.messages.append(Message(
                    role="user",
                    content=f"[SWE_WORKFLOW_STAGE: {self._swe_workflow.current_stage.value}]\n{stage_prompt}",
                ))
                logger.info(f"[SWE_WORKFLOW] Stage: {self._swe_workflow.current_stage.value}")

        self._event_log.log_event(
            EventType.AGENT_TURN_START,
            tool_call_id=f"step_{self.state.step_count}",
            step=self.state.step_count,
        )

        # Start agent turn span if tracing is enabled
        turn_span_id: str | None = None
        if self._trace_context:
            from compymac.trace_store import SpanKind
            turn_span_id = self._trace_context.start_span(
                kind=SpanKind.AGENT_TURN,
                name=f"agent_turn_{self.state.step_count}",
                actor_id="agent_loop",
                attributes={
                    "step_count": self.state.step_count,
                    "message_count": len(self.state.messages),
                },
            )

        # Get tool schemas from harness
        # Priority: menu system > active toolset > phase filtering > all tools
        if self.config.use_menu_system and hasattr(self.harness, 'get_menu_tool_schemas'):
            tools = self.harness.get_menu_tool_schemas()
        elif self.config.use_active_toolset and hasattr(self.harness, 'get_active_tool_schemas'):
            tools = self.harness.get_active_tool_schemas()
        elif hasattr(self.harness, 'get_phase_filtered_tool_schemas'):
            tools = self.harness.get_phase_filtered_tool_schemas()
        else:
            tools = self.harness.get_tool_schemas()

        # Call LLM
        self._event_log.log_event(
            EventType.LLM_REQUEST,
            tool_call_id=f"step_{self.state.step_count}",
            message_count=len(self.state.messages),
        )

        # Process messages through memory manager if enabled
        messages_to_send = self.state.messages
        if self._memory_manager:
            messages_to_send = self._memory_manager.process_messages(self.state.messages)
            # Update state with compressed messages if compression occurred
            if len(messages_to_send) < len(self.state.messages):
                self.state.messages = messages_to_send
                self._event_log.log_event(
                    EventType.OUTPUT_TRUNCATION,  # Reuse truncation event type
                    tool_call_id=f"step_{self.state.step_count}",
                    original_count=len(self.state.messages),
                    compressed_count=len(messages_to_send),
                    memory_state=str(self._memory_manager.get_memory_state().facts.to_dict()),
                )

        # Convert Message objects to dicts for API serialization
        messages_for_api = [msg.to_dict() for msg in messages_to_send]

        # Guided-Structured Templates (arxiv:2509.18076): Inject structured reasoning template
        # This guides the model through deliberate step-by-step reasoning before tool selection
        if self.config.use_guided_templates and tools:
            # Inject the guided template as a system message before the LLM call
            guided_message = {
                "role": "user",
                "content": f"[TOOL_GUIDANCE]: {GUIDED_TOOL_SELECTION_TEMPLATE}"
            }
            messages_for_api.append(guided_message)
            logger.debug("[GUIDED_TEMPLATES] Injected structured reasoning template")

        # Menu State Injection: Make current menu state salient to the agent
        # This addresses the discoverability problem where agents don't know they need to navigate
        # See docs/BROWSER_TOOL_DESIGN.md for rationale
        if self.config.use_menu_system and hasattr(self.harness, 'get_menu_manager'):
            menu_manager = self.harness.get_menu_manager()
            current_mode = menu_manager.current_mode
            if current_mode is None:
                # At ROOT - remind agent to select a mode
                available_modes = menu_manager.get_available_modes()
                menu_state_message = {
                    "role": "system",
                    "content": (
                        f"[MENU_STATE: ROOT] You are at the ROOT menu level. "
                        f"Only navigation tools are available. To access domain tools, "
                        f"call menu_enter(mode=\"<mode>\") with one of: {', '.join(available_modes)}. "
                        f"Use menu_list() to see mode descriptions."
                    )
                }
                messages_for_api.append(menu_state_message)
                logger.debug(f"[MENU_STATE] Injected ROOT state reminder, available modes: {available_modes}")
            else:
                # In a mode - show current mode
                menu_state_message = {
                    "role": "system",
                    "content": (
                        f"[MENU_STATE: {current_mode}] You are in '{current_mode}' mode. "
                        f"Mode tools are available. Call menu_exit() to return to ROOT and switch modes."
                    )
                }
                messages_for_api.append(menu_state_message)
                logger.debug(f"[MENU_STATE] Injected mode state: {current_mode}")

        # Start LLM call span if tracing is enabled
        llm_span_id: str | None = None
        llm_input_artifact_hash: str | None = None
        if self._trace_context:
            from compymac.trace_store import SpanKind

            # Store LLM input as artifact
            llm_input_data = json.dumps({
                "messages": messages_for_api,
                "tools": tools,
            }).encode()
            llm_input_artifact = self._trace_context.store_artifact(
                data=llm_input_data,
                artifact_type="llm_input",
                content_type="application/json",
                metadata={"step": self.state.step_count},
            )
            llm_input_artifact_hash = llm_input_artifact.artifact_hash

            llm_span_id = self._trace_context.start_span(
                kind=SpanKind.LLM_CALL,
                name="llm_chat",
                actor_id="llm_client",
                attributes={
                    "message_count": len(messages_for_api),
                    "has_tools": bool(tools),
                },
                input_artifact_hash=llm_input_artifact_hash,
            )

        # In action-gated mode, force tool calling to prevent intermittent text responses
        # This aligns the API contract with the agent loop's requirement that every turn
        # must include a tool call (no prose-only responses allowed)
        tool_choice = None
        if self.config.action_gated and tools:
            tool_choice = "required"

        response = self.llm_client.chat(
            messages=messages_for_api,
            tools=tools if tools else None,
            tool_choice=tool_choice,
        )

        # End LLM call span if tracing is enabled
        if self._trace_context and llm_span_id:
            from compymac.trace_store import SpanStatus

            # Store LLM output as artifact (including token usage for total capture)
            llm_output_data = json.dumps({
                "content": response.content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in (response.tool_calls or [])
                ],
                "usage": response.usage.to_dict(),
                "finish_reason": response.finish_reason,
            }).encode()
            llm_output_artifact = self._trace_context.store_artifact(
                data=llm_output_data,
                artifact_type="llm_output",
                content_type="application/json",
                metadata={"step": self.state.step_count},
            )

            self._trace_context.end_span(
                status=SpanStatus.OK,
                output_artifact_hash=llm_output_artifact.artifact_hash,
            )

        self._event_log.log_event(
            EventType.LLM_RESPONSE,
            tool_call_id=f"step_{self.state.step_count}",
            has_tool_calls=bool(response.tool_calls),
            content_length=len(response.content) if response.content else 0,
        )

        # Add assistant message to history
        # Convert ToolCall objects to dicts for serialization
        tool_calls_as_dicts = None
        if response.tool_calls:
            tool_calls_as_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments if isinstance(tc.arguments, str) else json.dumps(tc.arguments),
                    }
                }
                for tc in response.tool_calls
            ]

        self.state.messages.append(Message(
            role="assistant",
            content=response.content or "",
            tool_calls=tool_calls_as_dicts,
        ))

        # If no tool calls, this is a reasoning step - end turn span and return
        if not response.tool_calls:
            # Guided-Structured Templates: Retry with stronger template on tool_choice violation
            # This implements the curriculum-inspired retry mechanism from arxiv:2509.18076
            if (self.config.use_guided_templates and
                self.config.guided_template_retry and
                self.config.action_gated and
                tools and
                not getattr(self, '_guided_retry_attempted', False)):

                logger.warning("[GUIDED_TEMPLATES] Tool choice violation detected, retrying with stronger template")
                self._guided_retry_attempted = True

                # Add the stronger retry template
                retry_message = Message(
                    role="user",
                    content=f"[TOOL_GUIDANCE_RETRY]: {GUIDED_TOOL_SELECTION_RETRY_TEMPLATE}"
                )
                self.state.messages.append(retry_message)

                # Recursive retry - will return from the retry attempt
                return self.run_step()

            # Reset retry flag for next step
            self._guided_retry_attempted = False

            self._event_log.log_event(
                EventType.AGENT_TURN_END,
                tool_call_id=f"step_{self.state.step_count}",
                has_tool_calls=False,
            )

            # End agent turn span if tracing is enabled
            if self._trace_context and turn_span_id:
                from compymac.trace_store import SpanStatus
                self._trace_context.end_span(
                    status=SpanStatus.OK,
                )

            return response.content, []

        # Reset retry flag on successful tool call
        self._guided_retry_attempted = False

        # Execute tool calls through harness (harness handles its own tracing)
        tool_results = []
        for tool_call in response.tool_calls:
            self.state.tool_call_count += 1

            # Execute through harness
            result = self.harness.execute(tool_call)
            tool_results.append(result)

            # Summarize tool output if enabled to reduce context bloat
            content_for_message = result.content
            if self.config.summarize_tool_output and result.content:
                from compymac.memory import ToolOutputSummarizer
                original_len = len(result.content)
                content_for_message = ToolOutputSummarizer.summarize(
                    tool_call.name, result.content
                )
                if len(content_for_message) < original_len:
                    logger.debug(
                        f"Summarized {tool_call.name} output: "
                        f"{original_len} -> {len(content_for_message)} chars"
                    )

            # Add tool result to messages
            self.state.messages.append(Message(
                role="tool",
                content=content_for_message,
                tool_call_id=result.tool_call_id,
            ))

            # Check for errors
            if not result.success and self.config.stop_on_error:
                logger.warning(f"Tool call failed: {result.error}")

        self._event_log.log_event(
            EventType.AGENT_TURN_END,
            tool_call_id=f"step_{self.state.step_count}",
            has_tool_calls=True,
            tool_call_count=len(tool_results),
        )

        # End agent turn span if tracing is enabled
        if self._trace_context and turn_span_id:
            from compymac.trace_store import SpanStatus
            self._trace_context.end_span(
                status=SpanStatus.OK,
            )

        return None, tool_results

    def run(self, user_input: str) -> str:
        """
        Run the agent loop until completion or max steps.

        Returns the final text response from the agent.

        In action-gated mode (config.action_gated=True):
        - Agent must call a tool every turn (prose-only responses are invalid)
        - If config.require_complete_tool=True, agent must call 'complete' tool to finish
        - Invalid moves trigger a corrective message and retry (up to max_invalid_moves)

        ACI-style grounding (based on SWE-agent research):
        - If config.force_complete_on_last_step=True, inject "must call complete" on last step
        - If config.grounding_context is set, re-inject context every turn
        """
        self.add_user_message(user_input)
        invalid_move_count = 0

        while self.state.step_count < self.config.max_steps:
            # ACI-style: Check if this is the last step and inject forced complete message
            steps_remaining = self.config.max_steps - self.state.step_count
            if self.config.force_complete_on_last_step and steps_remaining == 1:
                self.state.messages.append(Message(
                    role="user",
                    content=(
                        '{"status": "FINAL_TURN", "instruction": "This is your LAST turn. '
                        'You MUST call complete() now with your final answer. No other action is allowed."}'
                    ),
                ))
            text_response, tool_results = self.run_step()

            # Gap 3: Advance SWE workflow on successful tool execution (before completion check)
            if self._swe_workflow and tool_results:
                from compymac.workflows.swe_loop import StageResult, WorkflowStage, WorkflowStatus
                all_successful = all(r.success for r in tool_results)
                any_failed = any(not r.success for r in tool_results)

                if all_successful:
                    old_stage = self._swe_workflow.current_stage
                    stage_result = StageResult(
                        stage=old_stage,
                        success=True,
                        message=f"Stage {old_stage.value} completed successfully",
                        artifacts={"tool_results": [r.tool_call_id for r in tool_results]},
                    )
                    self._swe_workflow.advance(stage_result)
                    new_stage = self._swe_workflow.current_stage
                    if old_stage != new_stage:
                        logger.info(f"[SWE_WORKFLOW] Advanced: {old_stage.value} -> {new_stage.value}")

                    # Phase 3: CI Integration - detect PR creation and poll CI
                    if old_stage == WorkflowStage.PR and new_stage == WorkflowStage.CI:
                        pr_url = self._detect_pr_url_from_results(tool_results)
                        if pr_url and self._ci_integration:
                            self._handle_ci_stage(pr_url)

                    # Phase 4: Validation Integration - run tests/lint in VALIDATE stage
                    if old_stage == WorkflowStage.MODIFY and new_stage == WorkflowStage.VALIDATE:
                        self._handle_validation_stage()

                elif any_failed and self._failure_recovery:
                    failed_results = [r for r in tool_results if not r.success]
                    for result in failed_results:
                        error_msg = result.error or result.content
                        failure_type = self._failure_recovery.detect_failure(error_msg)
                        if failure_type:
                            recovery_action = self._failure_recovery.get_recovery_action(failure_type, error_msg)
                            self._failure_recovery.record_failure(
                                failure_type=failure_type,
                                message=error_msg,
                                context=f"stage:{self._swe_workflow.current_stage.value}",
                            )
                            self.state.messages.append(Message(
                                role="user",
                                content=f"[SWE_WORKFLOW_RECOVERY] {recovery_action.description}",
                            ))
                            logger.info(f"[SWE_WORKFLOW] Recovery suggested: {recovery_action.action_type}")

                if self._swe_workflow.status == WorkflowStatus.COMPLETE:
                    logger.info("[SWE_WORKFLOW] Workflow completed successfully")

            # Check if 'complete' tool was called (signals task completion)
            complete_called = False
            complete_answer = ""
            for _result in tool_results:
                # Check if this was a 'complete' tool call
                if hasattr(self.harness, '_completion_signaled') and self.harness._completion_signaled:
                    complete_called = True
                    complete_answer = getattr(self.harness, '_completion_answer', text_response or "")
                    # Reset the flag for potential future runs
                    self.harness._completion_signaled = False
                    logger.info(f"[COMPLETE_DEBUG] complete_called=True, action_gated={self.config.action_gated}, require_complete_tool={self.config.require_complete_tool}")
                    break

            # In action-gated mode with require_complete_tool, only finish on 'complete' call
            if self.config.action_gated and self.config.require_complete_tool:
                logger.info(f"[COMPLETE_DEBUG] Checking termination: complete_called={complete_called}, action_gated={self.config.action_gated}, require_complete_tool={self.config.require_complete_tool}")
                if complete_called:
                    self.state.is_complete = True
                    self.state.final_response = complete_answer
                    return complete_answer

                # If no tool calls at all, this is an invalid move
                if text_response is not None and not tool_results:
                    invalid_move_count += 1
                    logger.warning(f"Invalid move {invalid_move_count}/{self.config.max_invalid_moves}: "
                                   "Agent returned text without tool call")

                    if invalid_move_count >= self.config.max_invalid_moves:
                        error_msg = (f"Failed: {invalid_move_count} consecutive invalid moves. "
                                     "Agent must call a tool each turn.")
                        self.state.final_response = error_msg
                        return error_msg

                    # Inject corrective message and continue
                    self.state.messages.append(Message(
                        role="user",
                        content=(
                            "Invalid move. You MUST choose exactly ONE action by calling a tool. "
                            "If you want to finish, call complete(final_answer=...). "
                            "Available actions: Read, Edit, bash, grep, glob, think, complete."
                        ),
                    ))
                    continue
                else:
                    # Valid tool call - reset invalid move counter
                    invalid_move_count = 0

            # Standard mode (non-action-gated) or action-gated without require_complete_tool
            elif not self.config.action_gated:
                # If we got a text response with no tool calls, we're done
                if text_response is not None and not tool_results:
                    self.state.is_complete = True
                    self.state.final_response = text_response
                    return text_response

            # Action-gated mode without require_complete_tool
            # Accept 'complete' tool OR prose-only response as completion
            else:
                if complete_called:
                    self.state.is_complete = True
                    self.state.final_response = complete_answer
                    return complete_answer

                # If no tool calls, this is an invalid move - inject corrective message
                if text_response is not None and not tool_results:
                    invalid_move_count += 1
                    logger.warning(f"Invalid move {invalid_move_count}/{self.config.max_invalid_moves}: "
                                   "Agent returned text without tool call")

                    if invalid_move_count >= self.config.max_invalid_moves:
                        error_msg = (f"Failed: {invalid_move_count} consecutive invalid moves. "
                                     "Agent must call a tool each turn.")
                        self.state.final_response = error_msg
                        return error_msg

                    # Inject corrective message and continue
                    self.state.messages.append(Message(
                        role="user",
                        content=(
                            "Invalid move. You MUST choose exactly ONE action by calling a tool. "
                            "If you want to finish, call complete(final_answer=...). "
                            "Available actions: Read, Edit, bash, grep, glob, think, complete."
                        ),
                    ))
                    continue
                else:
                    # Valid tool call - reset invalid move counter
                    invalid_move_count = 0

            # ACI-style: Re-ground the agent after tool results (SWE-agent research)
            # This helps the agent stay oriented in the task
            if self.config.grounding_context and tool_results:
                ctx = self.config.grounding_context
                steps_remaining = self.config.max_steps - self.state.step_count
                grounding_msg = json.dumps({
                    "status": "TURN_COMPLETE",
                    "repo_path": ctx.get("repo_path", ""),
                    "failing_tests": ctx.get("failing_tests", []),
                    "steps_remaining": steps_remaining,
                    "available_actions": ["Read", "Edit", "bash", "grep", "glob", "complete"],
                    "reminder": "Call complete() when tests pass. Respond ONLY with a tool call.",
                })
                self.state.messages.append(Message(
                    role="user",
                    content=grounding_msg,
                ))

            # If we hit max tool calls, stop
            if self.state.tool_call_count >= self.config.max_steps * self.config.max_tool_calls_per_step:
                logger.warning("Max tool calls reached")
                break

        # If we exit the loop without a final response, return failure in action-gated mode
        if self.config.action_gated:
            error_msg = "Failed: Max steps reached without calling complete() tool."
            self.state.final_response = error_msg
            return error_msg

        # Standard mode: return last content
        for msg in reversed(self.state.messages):
            if msg.role == "assistant" and msg.content:
                self.state.final_response = msg.content
                return msg.content

        return "Agent loop completed without final response"

    def run_with_policy(
        self,
        policy: "Policy",
        initial_input: str,
    ) -> str:
        """
        Run the agent loop with a custom policy for tool call generation.

        This is useful for testing without an LLM - the policy generates
        tool calls based on the current state.
        """
        self.add_user_message(initial_input)

        while self.state.step_count < self.config.max_steps:
            self.state.step_count += 1

            # Get tool calls from policy
            tool_calls = policy.get_tool_calls(self.state)

            if not tool_calls:
                # Policy says we're done
                response = policy.get_final_response(self.state)
                self.state.is_complete = True
                self.state.final_response = response
                return response

            # Execute tool calls
            for tool_call in tool_calls:
                result = self.harness.execute(tool_call)
                self.state.messages.append(Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                ))

        return "Policy loop completed"

    def get_state(self) -> AgentState:
        """Get the current agent state."""
        return self.state

    def reset(self) -> None:
        """Reset the agent state for a new conversation."""
        self.state = AgentState()
        if self.config.system_prompt:
            self.state.messages.append(Message(
                role="system",
                content=self.config.system_prompt,
            ))

    # Gap 1: Session persistence methods
    def save_run(self, status: str = "running") -> str | None:
        """
        Save the current run state for later resume.

        Args:
            status: Run status (running, paused, completed, failed)

        Returns:
            Run ID if saved, None if persistence not enabled
        """
        if not self._run_store or not self._run_id:
            return None

        from compymac.session import Session
        from compymac.storage.run_store import RunStatus

        # Create a Session object from current state
        session = Session(system_prompt=self.config.system_prompt)
        session.messages = self.state.messages.copy()

        # Map status string to RunStatus enum
        status_map = {
            "pending": RunStatus.PENDING,
            "running": RunStatus.RUNNING,
            "paused": RunStatus.PAUSED,
            "completed": RunStatus.COMPLETED,
            "failed": RunStatus.FAILED,
            "interrupted": RunStatus.INTERRUPTED,
        }
        run_status = status_map.get(status, RunStatus.RUNNING)

        # Save the run
        self._run_store.save_run(
            run_id=self._run_id,
            session=session,
            task_description=self._task_description,
            status=run_status,
            step_count=self.state.step_count,
            tool_calls_count=self.state.tool_call_count,
        )

        logger.debug(f"Saved run {self._run_id} with status {status}")
        return self._run_id

    def load_run(self, run_id: str) -> bool:
        """
        Load a saved run and restore state.

        Args:
            run_id: The run ID to load

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self._run_store:
            from compymac.storage.run_store import RunStore
            self._run_store = RunStore(self.config.persistence_dir)

        saved_run = self._run_store.load_run(run_id)
        if not saved_run:
            logger.warning(f"Run not found: {run_id}")
            return False

        # Restore state from saved run
        self._run_id = run_id
        self._task_description = saved_run.metadata.task_description
        self.state.messages = saved_run.session.messages.copy()
        self.state.step_count = saved_run.metadata.step_count
        self.state.tool_call_count = saved_run.metadata.tool_calls_count

        # Update status to running
        from compymac.storage.run_store import RunStatus
        self._run_store.update_status(run_id, RunStatus.RUNNING)

        logger.info(f"Loaded run {run_id}, resuming from step {self.state.step_count}")
        return True

    def pause_run(self) -> str | None:
        """
        Pause the current run for later resume.

        Returns:
            Run ID if paused, None if persistence not enabled
        """
        return self.save_run(status="paused")

    def get_run_id(self) -> str | None:
        """Get the current run ID."""
        return self._run_id

    def set_task_description(self, description: str) -> None:
        """Set the task description for the current run."""
        self._task_description = description

    def _detect_pr_url_from_results(self, tool_results: list[ToolResult]) -> str | None:
        """
        Phase 3: Detect PR URL from tool results.

        Looks for GitHub PR URLs in tool output (e.g., from git_create_pr or bash git push).
        """
        import re
        pr_pattern = r"https://github\.com/[^/]+/[^/]+/pull/\d+"

        for result in tool_results:
            content = result.content or ""
            match = re.search(pr_pattern, content)
            if match:
                pr_url = match.group(0)
                logger.info(f"[SWE_WORKFLOW] Detected PR URL: {pr_url}")
                if self._swe_workflow:
                    pr_number_match = re.search(r"/pull/(\d+)", pr_url)
                    pr_number = int(pr_number_match.group(1)) if pr_number_match else 0
                    self._swe_workflow.set_pr_info(pr_url, pr_number, "")
                return pr_url
        return None

    def _handle_ci_stage(self, pr_url: str) -> None:
        """
        Phase 3: Handle CI stage - poll CI status, parse logs, inject error summary.

        Based on research document Phase 3 requirements:
        1. Poll CI status for PR
        2. Parse CI logs for actionable errors
        3. Inject error summary into context
        4. Advance to ITERATE stage on CI failure
        """
        if not self._ci_integration or not self._swe_workflow:
            return

        from compymac.workflows.ci_integration import CIStatus
        from compymac.workflows.swe_loop import StageResult, WorkflowStage

        logger.info(f"[SWE_WORKFLOW] Polling CI for PR: {pr_url}")

        ci_status, checks = self._ci_integration.poll_status(pr_url)

        if ci_status == CIStatus.PASSED:
            self._swe_workflow.set_ci_status(passed=True, details={"checks": [c.to_dict() for c in checks]})
            self.state.messages.append(Message(
                role="user",
                content="[SWE_WORKFLOW_CI] CI passed. All checks successful.",
            ))
            logger.info("[SWE_WORKFLOW] CI passed")

        elif ci_status == CIStatus.FAILED:
            all_errors = []
            for check in checks:
                if check.status == CIStatus.FAILED and check.raw_log:
                    errors = self._ci_integration.parse_logs(check.raw_log)
                    all_errors.extend(errors)

            error_summary = self._ci_integration.summarize_errors(all_errors)
            self._swe_workflow.set_ci_status(passed=False, details={
                "checks": [c.to_dict() for c in checks],
                "errors": [e.to_dict() for e in all_errors],
            })

            self.state.messages.append(Message(
                role="user",
                content=f"[SWE_WORKFLOW_CI] CI failed.\n{error_summary}\n\nFix these errors and push a new commit.",
            ))

            stage_result = StageResult(
                stage=WorkflowStage.CI,
                success=False,
                message="CI failed - advancing to ITERATE stage",
                artifacts={"errors": [e.to_dict() for e in all_errors]},
                errors=[e.message for e in all_errors[:5]],
            )
            self._swe_workflow.advance(stage_result)
            logger.info(f"[SWE_WORKFLOW] CI failed with {len(all_errors)} errors, advancing to ITERATE")

        elif ci_status in [CIStatus.PENDING, CIStatus.RUNNING]:
            self.state.messages.append(Message(
                role="user",
                content="[SWE_WORKFLOW_CI] CI is still running. Wait for completion or check status again.",
            ))
            logger.info("[SWE_WORKFLOW] CI still running")

    def _handle_validation_stage(self) -> None:
        """
        Phase 4: Handle VALIDATE stage - run tests and lint, inject results.

        Based on research document Phase 4 requirements:
        1. Run tests using SWEWorkflow.run_tests()
        2. Run lint using SWEWorkflow.run_lint()
        3. Inject validation results into context
        """
        if not self._swe_workflow:
            return

        logger.info("[SWE_WORKFLOW] Running validation (tests + lint)")

        test_passed, test_output, test_errors = self._swe_workflow.run_tests()
        lint_passed, lint_output, lint_errors = self._swe_workflow.run_lint()

        validation_results = {
            "tests": {"passed": test_passed, "errors": test_errors},
            "lint": {"passed": lint_passed, "errors": lint_errors},
        }
        self._swe_workflow.set_validation_results(validation_results)

        validation_msg_parts = ["[SWE_WORKFLOW_VALIDATION]"]

        if test_passed:
            validation_msg_parts.append("Tests: PASSED")
        else:
            validation_msg_parts.append("Tests: FAILED\nErrors:\n" + "\n".join(test_errors[:5]))

        if lint_passed:
            validation_msg_parts.append("Lint: PASSED")
        else:
            validation_msg_parts.append("Lint: FAILED\nErrors:\n" + "\n".join(lint_errors[:5]))

        self.state.messages.append(Message(
            role="user",
            content="\n\n".join(validation_msg_parts),
        ))

        if test_passed and lint_passed:
            logger.info("[SWE_WORKFLOW] Validation passed (tests + lint)")
        else:
            logger.info(f"[SWE_WORKFLOW] Validation failed: tests={test_passed}, lint={lint_passed}")


class Policy:
    """
    Abstract policy for generating tool calls without an LLM.

    Useful for deterministic testing and replay.
    """

    def get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        """Generate tool calls based on current state. Return empty list to stop."""
        raise NotImplementedError

    def get_final_response(self, state: AgentState) -> str:
        """Generate final response when no more tool calls."""
        raise NotImplementedError


class ScriptedPolicy(Policy):
    """
    Policy that executes a predefined sequence of tool calls.

    Useful for deterministic testing.
    """

    def __init__(self, tool_calls: list[ToolCall], final_response: str = "Done"):
        self._tool_calls = list(tool_calls)
        self._index = 0
        self._final_response = final_response

    def get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        if self._index >= len(self._tool_calls):
            return []

        call = self._tool_calls[self._index]
        self._index += 1
        return [call]

    def get_final_response(self, state: AgentState) -> str:
        return self._final_response


class ReplayPolicy(Policy):
    """
    Policy that replays tool calls from an event log.

    Useful for reproducing runs from traces.
    """

    def __init__(self, event_log: EventLog):
        self._event_log = event_log
        self._tool_calls = self._extract_tool_calls()
        self._index = 0

    def _extract_tool_calls(self) -> list[ToolCall]:
        """Extract tool calls from event log."""
        calls = []
        for event in self._event_log.events:
            if event.event_type == EventType.TOOL_CALL_RECEIVED:
                calls.append(ToolCall(
                    id=event.tool_call_id,
                    name=event.data.get("tool_name", ""),
                    arguments=event.data.get("arguments", {}),
                ))
        return calls

    def get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        if self._index >= len(self._tool_calls):
            return []

        call = self._tool_calls[self._index]
        self._index += 1
        return [call]

    def get_final_response(self, state: AgentState) -> str:
        return "Replay complete"

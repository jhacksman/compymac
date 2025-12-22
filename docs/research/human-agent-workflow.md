# Human-Agent Workflow Design

## Overview

This document summarizes research on human-agent collaboration, review protocols, handoff points, and interaction patterns. These insights make CompyMac's guardrails usable in practice by designing effective human-in-the-loop workflows.

## Key Papers

### 1. LLM-Based Human-Agent Collaboration Survey (arXiv:2505.00753)

**Core Contribution**: First comprehensive survey of LLM-based human-agent systems (LLM-HAS).

**Why Human-Agent Systems?**
- Fully autonomous agents face reliability issues (hallucinations)
- Complex tasks exceed single-agent capabilities
- Safety and ethical risks require human oversight

**Core Components**:
1. **Environment & Profiling**: Context in which collaboration occurs
2. **Human Feedback**: How humans provide input to agents
3. **Interaction Types**: Patterns of human-agent communication
4. **Orchestration**: How collaboration is coordinated
5. **Communication**: Protocols for information exchange

**Key Insight**: "LLM-based human-agent systems (LLM-HAS) incorporate human-provided information, feedback, or control into the agent system to enhance system performance, reliability and safety."

**Relevance to CompyMac**: Our message_user tool and confirmation patterns implement basic human-agent interaction. This survey provides a framework for more sophisticated collaboration.

---

### 2. Plan-Then-Execute: User Trust Study (arXiv:2502.01390)

**Focus**: Empirical study of user trust and team performance with LLM agents.

**Key Findings**:
1. **Plan Visibility**: Users trust agents more when they can see the plan
2. **Execution Transparency**: Step-by-step progress builds confidence
3. **Error Handling**: How agents handle errors affects trust significantly
4. **Control Points**: Users want ability to intervene at key moments

**Trust Factors**:
- Predictability: Can user anticipate agent behavior?
- Transparency: Can user understand what agent is doing?
- Controllability: Can user intervene when needed?
- Reliability: Does agent consistently perform well?

**Relevance to CompyMac**: Our todo list provides plan visibility. We should enhance transparency around error handling and provide clear intervention points.

---

### 3. Flow: Modularized Agentic Workflow (arXiv:2501.07834)

**Core Contribution**: Framework for dynamic workflow refinement during execution.

**Key Concepts**:
- **AOV Graph**: Activity-on-vertex representation of workflows
- **Dynamic Refinement**: Adjust workflow based on execution feedback
- **Modularity**: Break workflows into parallelizable components

**Benefits**:
- Efficient concurrent execution
- Effective goal achievement
- Enhanced error tolerance

**Key Insight**: "An effective workflow adjustment is crucial in real-world scenarios, as the initial plan must adjust to unforeseen challenges and changing conditions in real time."

**Relevance to CompyMac**: Our todo system is static once created. We could enhance it with dynamic refinement based on execution results.

---

### 4. Multi-Agent Collaboration Strategies (arXiv:2505.12467)

**Focus**: Granular mechanisms governing multi-agent collaboration.

**Four Dimensions**:
1. **Agent Governance**: Centralized vs. distributed control
2. **Participation Control**: Who participates in decisions
3. **Interaction Dynamics**: How agents communicate
4. **Dialogue History Management**: How context is shared

**Key Findings**:
- Centralized governance optimizes decision quality
- Instructor-led participation reduces coordination overhead
- Ordered interaction patterns improve consistency
- Curated context summarization balances quality and efficiency

**Token-Accuracy Ratio (TAR)**: Metric for balancing decision quality and resource utilization.

**Relevance to CompyMac**: Our multi-agent architecture (Manager/Planner/Executor/Reflector) implements centralized governance. We should consider TAR when optimizing.

---

### 5. Orchestrating Human-AI Teams (arXiv:2510.02557)

**Core Contribution**: Research vision for Autonomous Manager Agent.

**Manager Agent Responsibilities**:
1. Decompose complex goals into task graphs
2. Allocate tasks to human and AI workers
3. Monitor progress
4. Adapt to changing conditions
5. Maintain transparent stakeholder communication

**Formalization**: Workflow management as Partially Observable Stochastic Game (POSG).

**Four Foundational Challenges**:
1. **Compositional Reasoning**: Hierarchical decomposition
2. **Multi-Objective Optimization**: Shifting preferences
3. **Ad Hoc Teamwork**: Coordination without prior training
4. **Governance by Design**: Compliance and ethics

**MA-Gym Benchmark Results**: GPT-5-based Manager Agents struggle to jointly optimize goal completion, constraint adherence, and workflow runtime.

**Relevance to CompyMac**: Our Manager agent faces similar challenges. The POSG formalization could inform our planning approach.

---

### 6. Multi-Agent Collaboration Mechanisms Survey (arXiv:2501.06322)

**Framework Dimensions**:
- **Actors**: Agents involved in collaboration
- **Types**: Cooperation, competition, or coopetition
- **Structures**: Peer-to-peer, centralized, or distributed
- **Strategies**: Role-based or model-based
- **Coordination Protocols**: How agents synchronize

**Key Insight**: "These LLM-based Multi-Agent Systems (MASs) enable groups of intelligent agents to coordinate and solve complex tasks collectively at scale, transitioning from isolated models to collaboration-centric approaches."

**Relevance to CompyMac**: Our architecture uses role-based strategies with centralized coordination. We could explore hybrid approaches.

---

### 7. AIssistant: Human-AI Scientific Collaboration (arXiv:2509.12282)

**Focus**: Human-AI collaboration for scientific writing.

**Three-Layer Evaluation**:
1. **Independent Human Review**: Following double-blind standards
2. **Automated LLM Review**: Scalable human review proxy
3. **Program Chair Oversight**: Final validation and acceptance

**Key Insight**: Human oversight at every stage ensures accuracy, coherence, and scholarly rigor.

**Relevance to CompyMac**: Multi-layer review could inform our verification approach. Different levels of scrutiny for different risk levels.

---

## Implications for CompyMac

### Interaction Patterns

Based on the research, effective human-agent interaction should include:

1. **Plan Visibility**: Show the plan before execution
2. **Progress Updates**: Regular status during execution
3. **Intervention Points**: Clear moments where human can redirect
4. **Error Escalation**: Automatic escalation when agent is stuck
5. **Completion Confirmation**: Human approval before declaring done

### Handoff Protocol

```python
class HandoffProtocol:
    """Protocol for human-agent handoffs."""
    
    def request_handoff(self, reason: str, context: dict) -> HandoffRequest:
        """Agent requests human intervention."""
        return HandoffRequest(
            reason=reason,
            context=context,
            options=self.generate_options(context),
            urgency=self.assess_urgency(reason)
        )
    
    def receive_handoff(self, request: HandoffRequest) -> HandoffResponse:
        """Human responds to handoff request."""
        # Options: approve, reject, modify, delegate, escalate
        pass
    
    def resume_from_handoff(self, response: HandoffResponse) -> None:
        """Agent resumes work after handoff."""
        pass
```

### Trust-Building Patterns

| Pattern | Implementation | Purpose |
|---------|---------------|---------|
| Plan Preview | Show todo list before starting | Set expectations |
| Progress Streaming | Real-time status updates | Build confidence |
| Explanation on Demand | Explain reasoning when asked | Transparency |
| Graceful Degradation | Partial results when stuck | Reliability |
| Undo Support | Ability to revert actions | Controllability |

### Intervention Points

```yaml
# When to pause for human input
intervention_points:
  - before_destructive_action:
      triggers: [file_delete, git_push, deploy]
      action: require_confirmation
      
  - on_uncertainty:
      triggers: [confidence < 0.7, multiple_valid_options]
      action: present_options
      
  - on_error:
      triggers: [tool_failure, unexpected_result]
      action: escalate_with_context
      
  - on_completion:
      triggers: [all_todos_done]
      action: request_verification
```

### Feedback Integration

How to incorporate human feedback:

1. **Immediate Correction**: Human corrects current action
2. **Plan Adjustment**: Human modifies remaining plan
3. **Preference Learning**: System learns from corrections
4. **Policy Update**: Persistent changes to agent behavior

### Communication Guidelines

Based on research findings:

1. **Be Concise**: Users prefer brief updates over verbose explanations
2. **Be Actionable**: Every message should have clear next steps
3. **Be Honest**: Acknowledge uncertainty and limitations
4. **Be Responsive**: Quick acknowledgment of human input
5. **Be Predictable**: Consistent communication patterns

---

## Metrics to Track

1. **Handoff Frequency**: How often does agent need human help?
2. **Handoff Resolution Time**: How long until human responds?
3. **Trust Score**: User-reported confidence in agent
4. **Intervention Rate**: How often do humans override agent decisions?
5. **Completion Rate**: Tasks completed without abandonment

---

## Open Questions

1. **Optimal Autonomy Level**: How much should agent do before checking with human?

2. **Feedback Timing**: When is the best time to request human input?

3. **Trust Calibration**: How do we help users develop appropriate trust (not over- or under-trust)?

4. **Asynchronous Collaboration**: How do we handle delays in human response?

---

## References

- arXiv:2505.00753 - "LLM-Based Human-Agent Collaboration and Interaction Systems: A Survey"
- arXiv:2502.01390 - "Plan-Then-Execute: An Empirical Study of User Trust and Team Performance"
- arXiv:2501.07834 - "Flow: Modularized Agentic Workflow Automation"
- arXiv:2505.12467 - "Beyond Frameworks: Unpacking Collaboration Strategies in Multi-Agent Systems"
- arXiv:2510.02557 - "Orchestrating Human-AI Teams: The Manager Agent as a Unifying Research Challenge"
- arXiv:2501.06322 - "Multi-Agent Collaboration Mechanisms: A Survey of LLMs"
- arXiv:2509.12282 - "AIssistant: An Agentic Approach for Human-AI Collaborative Scientific Work"

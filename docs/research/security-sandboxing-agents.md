# Security and Sandboxing for LLM Agents

## Overview

This document summarizes research on security, sandboxing, and capability control for LLM agents. These techniques guard against "verified but dangerous" outcomes - ensuring that even when agents complete tasks correctly, they don't cause unintended harm.

## Key Papers

### 1. CaMeL: Capability-Based Sandbox for Prompt Injection (arXiv:2505.22852)

**Core Contribution**: Capability-based sandbox to mitigate prompt injection attacks in LLM agents.

**Architecture**:
- Dual-LLM architecture separating trusted and untrusted processing
- Capability tokens that grant specific permissions
- Isolation between user intent and external data

**Limitations Identified**:
- Assumes trusted user prompt (vulnerable to initial injection)
- Omits side-channel concerns
- Performance trade-offs from dual-LLM architecture

**Proposed Enhancements**:
1. **Prompt Screening**: Filter initial inputs for injection attempts
2. **Output Auditing**: Detect instruction leakage in outputs
3. **Tiered-Risk Access**: Balance utility and control based on risk level
4. **Formally Verified IL**: Intermediate language with static guarantees

**Relevance to CompyMac**: Our tool permission system could implement capability-based access. The tiered-risk model aligns with our approach of requiring confirmation for dangerous operations.

---

### 2. Design Patterns for Prompt Injection Defense (arXiv:2506.08837)

**Core Contribution**: Principled design patterns for building AI agents with provable resistance to prompt injection.

**Key Patterns**:

1. **Data-Instruction Separation**: Never mix untrusted data with instructions in the same context
2. **Privilege Separation**: Different LLM instances for different trust levels
3. **Output Validation**: Verify outputs don't contain injected instructions
4. **Capability Restriction**: Limit what tools/actions are available based on context

**Trade-offs Analyzed**:
- Utility vs Security (more restrictions = less capability)
- Latency vs Safety (more checks = slower execution)
- Complexity vs Maintainability

**Key Insight**: "We systematically analyze these patterns, discuss their trade-offs in terms of utility and security, and illustrate their real-world applicability through a series of case studies."

**Relevance to CompyMac**: These patterns should inform our agent architecture. Particularly relevant: separating tool execution from LLM reasoning, and validating outputs before acting on them.

---

### 3. Progent: Programmable Privilege Control (arXiv:2504.11703)

**Core Contribution**: Fine-grained, programmable privilege control for LLM agents.

**Architecture**:
- Declarative policy language for specifying permissions
- Runtime enforcement of privilege boundaries
- Dynamic privilege escalation/de-escalation based on context

**Key Features**:
- Per-tool permission specifications
- Context-dependent access control
- Audit logging of privilege usage

**Relevance to CompyMac**: Our dynamic tool discovery (request_tools) could integrate with a privilege system. Agents would need to request capabilities, and the system would grant/deny based on policy.

---

### 4. Defeating Prompt Injections by Design (arXiv:2503.18813)

**Authors**: Google DeepMind team (Debenedetti, Shumailov, Carlini, et al.)

**Core Insight**: Prompt injection is fundamentally an architectural problem, not a filtering problem.

**Design Principles**:
1. **Structural Separation**: Architecture that makes injection impossible, not just difficult
2. **Minimal Trust Surface**: Reduce the amount of untrusted input that reaches the LLM
3. **Verification Over Filtering**: Verify outputs rather than trying to filter inputs

**Key Quote**: "We argue that prompt injection attacks can be defeated by design, through careful architectural choices that separate trusted and untrusted content."

**Relevance to CompyMac**: Our architecture should assume all external data is potentially malicious. Tool outputs, file contents, and web data should never be trusted to contain instructions.

---

### 5. ACE: Security Architecture for LLM-Integrated Apps (arXiv:2504.20984)

**Core Contribution**: Comprehensive security architecture for LLM-integrated application systems.

**Components**:
1. **Access Control Layer**: Who can invoke what capabilities
2. **Capability Enforcement**: What each capability can actually do
3. **Audit Trail**: Complete logging of all actions

**Security Properties**:
- Confidentiality: Prevent unauthorized data access
- Integrity: Prevent unauthorized modifications
- Availability: Prevent denial of service

**Relevance to CompyMac**: Our TraceStore provides the audit trail. We need to add access control and capability enforcement layers.

---

### 6. Securing AI Agents Against Prompt Injection (arXiv:2511.15759)

**Focus**: RAG systems and their unique vulnerabilities.

**Attack Vectors**:
1. **Document Injection**: Malicious content in retrieved documents
2. **Query Manipulation**: Crafted queries that trigger injection
3. **Context Poisoning**: Gradual corruption of agent context

**Defenses**:
1. **Content Sanitization**: Remove potential injection patterns from retrieved content
2. **Source Verification**: Only trust content from verified sources
3. **Anomaly Detection**: Detect unusual patterns in agent behavior

**Relevance to CompyMac**: Our web_search and web_get_contents tools retrieve external content. We need to sanitize this content before including it in agent context.

---

## Implications for CompyMac

### Security Architecture Principles

1. **Defense in Depth**: Multiple layers of protection, not single points of failure

2. **Least Privilege**: Agents get minimum permissions needed for current task

3. **Separation of Concerns**: Different trust levels for different operations

4. **Audit Everything**: Complete trace of all actions for post-hoc analysis

5. **Fail Secure**: When in doubt, deny access and require confirmation

### Capability Model

```python
class Capability:
    """A capability grants permission for specific operations."""
    
    tool: str           # Which tool this capability applies to
    scope: str          # What scope (files, URLs, etc.)
    operations: list    # What operations are allowed
    expiry: datetime    # When this capability expires
    audit: bool         # Whether to log usage

# Example capabilities
file_read = Capability(
    tool="Read",
    scope="/home/ubuntu/repos/compymac/**",
    operations=["read"],
    expiry=task_end,
    audit=True
)

file_write = Capability(
    tool="Edit",
    scope="/home/ubuntu/repos/compymac/src/**",
    operations=["edit"],
    expiry=task_end,
    audit=True
)

# Dangerous capability - requires explicit grant
shell_execute = Capability(
    tool="bash",
    scope="*",
    operations=["execute"],
    expiry=None,  # Must be explicitly granted per-command
    audit=True
)
```

### Trust Boundaries

| Data Source | Trust Level | Handling |
|-------------|-------------|----------|
| System prompt | Trusted | Direct use |
| User messages | Semi-trusted | Validate intent |
| Tool outputs | Untrusted | Sanitize, don't execute |
| Web content | Untrusted | Sanitize, quote |
| File contents | Untrusted | Sanitize, quote |
| LLM outputs | Untrusted | Validate before acting |

### Sanitization Strategies

1. **Quote External Content**: Wrap in clear delimiters that LLM recognizes as data, not instructions

2. **Escape Special Patterns**: Remove or escape patterns that look like instructions

3. **Length Limits**: Truncate excessively long content that might contain injection

4. **Content Type Validation**: Ensure content matches expected type (code, text, JSON, etc.)

---

## Open Questions

1. **Usability vs Security**: How do we maintain agent usefulness while enforcing strict security?

2. **Dynamic Permissions**: How do we handle tasks that legitimately need elevated permissions?

3. **Injection Detection**: Can we reliably detect injection attempts without false positives?

4. **Recovery**: What do we do when an injection is detected mid-task?

---

## References

- arXiv:2505.22852 - "Operationalizing CaMeL: Strengthening LLM Defenses for Enterprise Deployment"
- arXiv:2506.08837 - "Design Patterns for Securing LLM Agents against Prompt Injections"
- arXiv:2504.11703 - "Progent: Programmable Privilege Control for LLM Agents"
- arXiv:2503.18813 - "Defeating Prompt Injections by Design"
- arXiv:2504.20984 - "ACE: A Security Architecture for LLM-Integrated App Systems"
- arXiv:2511.15759 - "Securing AI Agents Against Prompt Injection Attacks"

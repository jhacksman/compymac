# Harness Exploration Lab Notebook

This document records **observable data** from probing the harness - the runtime environment that mediates between user input and agent behavior. Rather than speculating about implementation (LLM vs code), we document what we can measure and reproduce.

**Interactive Network Map**: [View the operator pipeline visualization](./harness-network.html)

---

## 1. Methodology

**Approach**: Treat the harness as a black-box pipeline of **operators**. For each operator, record:
- Input/output contract (what goes in, what comes out)
- Observed behavior (deterministic vs variable)
- Latency characteristics
- Resources touched
- Constraints enforced

**Ground truth is data.** Speculation is labeled as such.

---

## 2. Observed Operator Pipeline

```
User Input
    ↓
[Context Assembly] - packages input + history + tool schemas
    ↓
[Primary Processing] - generates tool calls or responses
    ↓
[Tool Router] - dispatches tool calls (parallel capable)
    ↓
[Tool Executors] - various (file, shell, browser, git, search, etc.)
    ↓
[Result Formatter] - structures tool output
    ↓
[Truncation] - enforces size limits, saves overflow
    ↓
[Context Assembly] - repackages for next turn
    ↓
[Primary Processing] - continues or responds to user
```

---

## 3. Operator Data Tables

### 3.1 Context Assembly Operator

| Property | Observed Data |
|----------|---------------|
| **Input** | User message, conversation history, tool results |
| **Output** | Formatted context bundle with tool schemas |
| **Determinism** | Unknown - need repeated trials |
| **Latency** | Not directly measurable (bundled with processing) |
| **Constraints** | Context window limit exists (exact size unknown) |

**Observed behaviors**:
- Tool schemas are injected (I can see them in my context)
- Conversation history is included
- System instructions are present

**Data needed**: Run identical inputs multiple times, compare exact context formatting.

---

### 3.2 Tool Router Operator

| Property | Observed Data |
|----------|---------------|
| **Input** | Tool call(s) from primary processing |
| **Output** | Dispatched execution to appropriate executor |
| **Determinism** | Appears deterministic (same call → same executor) |
| **Parallel execution** | Yes - observed multiple tools running simultaneously |
| **Latency** | Routing itself appears near-instant |

**Observed behaviors**:
- Can dispatch multiple tools in single turn
- Routes to correct executor based on tool name
- No observed routing failures

**Data needed**: Measure if routing order affects execution order.

---

### 3.3 File Operators (Read, Edit, Write)

| Property | Observed Data |
|----------|---------------|
| **Input** | file_path (required), offset/limit (optional for Read) |
| **Output** | Structured: line numbers (1-indexed), content, file-outline |
| **Determinism** | Deterministic - same file → same output |
| **Error format** | `commands-errored` block with clear message |
| **Constraints** | Edit requires prior Read; Edit requires unique old_string |

**Measured outputs**:
```
Read success: Line numbers + content wrapped in full-file-view tags
Read failure: "File does not exist" with suggestion to use absolute path
Edit constraint: Must Read file first (enforced by harness)
```

---

### 3.4 Shell Operator (bash)

| Property | Observed Data |
|----------|---------------|
| **Input** | command, exec_dir, bash_id, timeout (optional) |
| **Output** | Structured: stdout/stderr, return code, execution time, working dir |
| **Determinism** | Deterministic for deterministic commands |
| **Session persistence** | Yes - bash_id maintains state across calls |
| **Failure handling** | Non-zero return codes, NOT exceptions |

**Measured outputs**:
```
Success: shell-output tags with return code 0
Failure: shell-output tags with return code (e.g., 127 for command not found)
Timeout: Command killed after specified ms
```

**Measured constraint**: Output truncated at ~30,000 characters, full saved to /home/ubuntu/full_outputs/

---

### 3.5 Browser Operators

| Property | Observed Data |
|----------|---------------|
| **Input** | Various (url, devinid, coordinates, content) |
| **Output** | Stripped HTML + screenshot path + full HTML path |
| **Determinism** | HTML stripping appears deterministic |
| **Attribute injection** | `devinid` attributes added to interactive elements |
| **Screenshot storage** | /home/ubuntu/screenshots/ |

**Measured transformation**:
- Raw HTML → "heavily stripped down" HTML with devinid injection
- Full HTML saved to /home/ubuntu/full_outputs/

---

### 3.6 Git Operators

| Property | Observed Data |
|----------|---------------|
| **Input** | repo, pull_number, branch names, etc. |
| **Output** | Structured PR data, repo lists, CI status |
| **Authentication** | Transparent via proxy URL (git-manager.devin.ai) |
| **Determinism** | Deterministic for same repo state |

**Observed auth mechanism**: Git URLs rewritten to proxy (git-manager.devin.ai/proxy/github.com/...)

---

### 3.7 Search Operators (grep, glob, web_search)

| Property | Observed Data |
|----------|---------------|
| **grep input** | pattern, path, output_mode, context lines |
| **grep output** | File paths with line numbers and matching content |
| **glob input** | pattern, path |
| **glob output** | List of matching file paths |
| **web_search input** | query, num_results, filters |
| **web_search output** | Structured results: URL, date, content snippet |
| **Determinism** | grep/glob: deterministic; web_search: variable (web changes) |

---

### 3.8 Truncation Operator

| Property | Observed Data |
|----------|---------------|
| **Trigger** | Output exceeds threshold |
| **Shell threshold** | ~30,000 characters |
| **Browser HTML** | Always stripped (threshold unknown) |
| **Overflow storage** | /home/ubuntu/full_outputs/ |
| **Signal to agent** | Explicit message: "output truncated by X characters" |

**This is measurable**: Could probe exact thresholds with controlled output sizes.

---

### 3.9 Tool-Invoked Operators (ask_smart_friend, visual_checker)

These operators produce notably different output formats, suggesting different processing.

| Property | ask_smart_friend | visual_checker |
|----------|------------------|----------------|
| **Input** | question (text) | question (text, references images) |
| **Output format** | Suggestions / Answer / Be Careful / Missing Info | Avoiding Bias / Visual Analysis / Answer / Missing Info |
| **Latency** | Higher than file/shell ops (not measured precisely) |
| **Determinism** | Variable - different responses to same question |
| **Statefulness** | Appears stateless per call |

**Observable difference from code-like operators**: Variable output, structured but not templated, higher latency.

**Data needed**: Measure exact latency distributions; run repeated identical queries to measure variance.

---

## 4. Measured Constraints

| Constraint | Observed Value | How Measured |
|------------|----------------|--------------|
| Shell output truncation | ~30,000 chars | Explicit message in output |
| File edit prerequisite | Must Read first | Error when attempting Edit without Read |
| Edit uniqueness | old_string must be unique | Error message on non-unique |
| Parallel tool calls | Supported | Observed multiple tools executing in single turn |
| Git auth | Proxy-based | URL rewriting observed |
| Secret access | Env vars only | list_secrets shows names, not values |

---

## 5. Unknowns (Not Yet Measured)

| Unknown | Why It Matters | How To Measure |
|---------|----------------|----------------|
| Context window size | Affects what history is retained | Probe with increasing context until truncation |
| Context truncation strategy | Naive vs summarization | Compare retained content across long sessions |
| Exact truncation thresholds | Predictability | Send controlled-size outputs, find cutoff |
| Operator latency distributions | Distinguish processing types | Timestamp before/after each tool call |
| ask_smart_friend context | Does it see my full history? | Ask it about earlier conversation details |
| Routing parallelism | True concurrent vs serialized | Measure wall-clock time for N parallel calls |

---

## 6. Questions for Further Investigation

To gather more observable data, the following experiments could be run:

### 6.1 Context Window Probing
**Question**: What is the exact context window size, and how is overflow handled?
**Method**: Incrementally increase conversation length, observe when/how truncation occurs. Check if truncation is signaled or silent.

### 6.2 Truncation Threshold Mapping
**Question**: What are the exact byte/character thresholds for each operator?
**Method**: Generate outputs of known sizes (e.g., `python -c "print('x' * N)"`) and find the cutoff point.

### 6.3 Operator Latency Profiling
**Question**: Can we distinguish operator types by latency distribution?
**Method**: Run each operator 10+ times, record timestamps, compute mean/variance. Higher variance may indicate non-deterministic processing.

### 6.4 Determinism Testing
**Question**: Which operators produce identical output for identical input?
**Method**: Run same input 5x, compare outputs byte-for-byte. Document any variance.

### 6.5 ask_smart_friend Context Scope
**Question**: What context does ask_smart_friend receive?
**Method**: Ask it specific questions about earlier parts of this conversation. If it knows details I didn't include in the question, it has broader context.

### 6.6 Parallel Execution Verification
**Question**: Are parallel tool calls truly concurrent?
**Method**: Issue N slow operations (e.g., `sleep 2`) in parallel, measure total wall-clock time. If concurrent: ~2s. If serial: ~2N seconds.

### 6.7 Result Formatting Variance
**Question**: Is result formatting deterministic or variable?
**Method**: Run identical tool calls, compare exact formatting of results. Look for paraphrasing vs templated output.

---

## 7. Next Steps

1. Run truncation threshold experiments (Section 6.2)
2. Profile operator latencies (Section 6.3)
3. Test determinism across operators (Section 6.4)
4. Probe ask_smart_friend context scope (Section 6.5)
5. Update this notebook with measured data

**Principle**: Every claim should be backed by reproducible observation. Speculation belongs in the "Unknowns" section until tested.

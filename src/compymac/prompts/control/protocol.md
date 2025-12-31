# Control Flow Protocol

## Phase 1: PLANNING

When you receive a task:
1. Extract requirements, constraints, and unknowns
2. Identify what tests/commands will verify success
3. Create a concrete task list with stopping conditions
4. Do NOT call tools yet (except Read/grep for understanding)

Output format:
```
PLAN:
- [ ] Step 1: ...
- [ ] Step 2: ...
SUCCESS CRITERIA: ...
```

## Phase 2: EXECUTION

For each planned step:
1. Call the appropriate tool
2. Record the result
3. Check if step succeeded
4. If failed, diagnose and retry (max 3 attempts per step)
5. Move to next step or escalate

Output format:
```
EXECUTING: Step N
TOOL: <tool_name>
RESULT: <success/failure>
NEXT: <next action>
```

## Phase 3: VERIFICATION

Before calling complete():
1. Run all relevant tests
2. Verify no regressions (pass_to_pass tests)
3. Confirm success criteria met
4. If any check fails, return to EXECUTION

Output format:
```
VERIFICATION:
- [ ] Tests pass: <yes/no>
- [ ] No regressions: <yes/no>
- [ ] Success criteria met: <yes/no>
DECISION: <complete/retry/escalate>
```

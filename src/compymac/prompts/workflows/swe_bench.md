# SWE-Bench Workflow

## Task Structure

- Instance ID: {instance_id}
- Problem Statement: {problem_statement}
- Repository: {repo_path}
- Tests: fail_to_pass, pass_to_pass

## Workflow: LOCALIZE -> FIX -> VERIFY

### LOCALIZE

1. Run fail_to_pass test to get traceback
2. grep the top frame symbol
3. Read the relevant file
4. Identify root cause

### FIX

1. Implement smallest possible patch
2. Use Edit tool with exact old_string match
3. One logical change per Edit

### VERIFY

1. Run fail_to_pass tests (must pass)
2. Run pass_to_pass tests (no regressions)
3. Only then call complete()

## Anti-Patterns

- Don't Read/grep without running tests first
- Don't claim "expected failures"
- Don't propose fixes without citing the traceback
- Don't call complete() without test verification
- Don't keep thinking after identifying the problem - MAKE THE EDIT

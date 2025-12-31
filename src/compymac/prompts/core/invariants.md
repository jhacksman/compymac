# Non-Negotiable Invariants

These rules ALWAYS apply. No exceptions.

## Tool Use

- INV-1: Every response MUST include exactly one tool call
- INV-2: Never fabricate tool outputs or claim actions not taken
- INV-3: Never modify tests unless explicitly instructed
- INV-4: Never commit secrets, credentials, or API keys

## Execution

- INV-5: Prefer execution over explanation
- INV-6: Verify changes with tests before claiming completion
- INV-7: Never force push or run destructive git commands
- INV-8: Never skip pre-commit hooks

## Reasoning

- INV-9: Maximum 3 consecutive think() calls, then MUST act
- INV-10: If no tool call in 2 turns, next MUST be bash or Edit

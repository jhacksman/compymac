# Start Here - Next Session

**Date:** 2025-12-27
**Context:** Transitioning from tactical SWE-bench optimization to principled metacognitive architecture

---

## What Just Happened

Your previous session crashed while working on SWE-bench V4 validation. During that session:
- ✅ Implemented V4 evidence-based gating (prevents claiming tests passed without proof)
- ✅ Validated on 3 real SWE-bench tasks (1/3 resolution rate, no false positives)
- ✅ Identified that we were optimizing tactics without strategic architecture

## Strategic Refocus

We're shifting from "make SWE-bench pass" to "build a robust metacognitive framework."

**Why:** Production agents (Devin, Cline, Orchids) have explicit metacognitive scaffolding:
- `<think>` tools for private reasoning
- 10+ mandatory thinking scenarios
- Temptation awareness and prevention
- Principle-based guidance

CompyMac had **zero** of these. That's the gap we're filling.

---

## Your Mission

**Implement Phase 1 of the Metacognitive Architecture.**

Read these documents in order:
1. **`METACOGNITIVE_ARCHITECTURE.md`** - The design specification (read this FIRST)
2. **`ROADMAP.md`** - Your implementation plan (Phases 1-4 detailed)

## Phase 1 Task List

Your job is to implement the **core metacognitive tools**. Here's what's already done vs what you need to do:

### ✅ Already Complete (don't redo)
- `<think>` tool registered in LocalHarness (line 1129-1149)
- `_think()` method implemented (line 2117-2156)
- Tool already in BUDGET_NEUTRAL_TOOLS and PHASE_NEUTRAL_TOOLS
- V4 evidence-based gating working

### 🔨 Your Tasks (Phase 1)

**1.1 Extend SWEPhaseState for Thinking Tracking**
- File: `src/compymac/swe_workflow.py`
- Add `thinking_events` field to SWEPhaseState dataclass
- Implement `record_thinking()` method
- Implement `has_recent_thinking()` method
- Implement `get_thinking_compliance_rate()` method
- Add `get_required_thinking_scenarios()` helper function
- See ROADMAP.md Section "Phase 1, Task 1.2" for detailed spec

**1.2 Create CognitiveEvent in Trace Store**
- File: `src/compymac/trace_store.py`
- Add `CognitiveEvent` dataclass
- Extend `TraceContext` with `add_cognitive_event()` method
- Extend `TraceStore` with `store_cognitive_event()` and `get_cognitive_events()` methods
- Add database schema migration for `cognitive_events` table
- See ROADMAP.md Section "Phase 1, Task 1.3" for detailed spec

**1.3 Define Temptation Catalog**
- File: `src/compymac/temptations.py` (NEW FILE)
- Create `Temptation` enum with 8 temptations (T1-T8)
- Create `TemptationDefinition` dataclass
- Build `TEMPTATION_CATALOG` dict with all 8 definitions
- Add helper functions: `get_temptation_description()`, `get_relevant_temptations()`
- See ROADMAP.md Section "Phase 1, Task 1.4" for detailed spec

**1.4 Connect think() to Trace Store**
- File: `src/compymac/local_harness.py`
- Uncomment the TODO sections in `_think()` method (lines 2143-2153)
- Actually call `record_thinking()` and `add_cognitive_event()`
- Test that thinking events are captured

**1.5 Phase 1 Validation**
- Run `pytest tests/` to ensure nothing broke
- Manually test `think` tool (call it, check SQLite trace store has data)
- Verify thinking events recorded in SWEPhaseState
- Run 1 simple SWE-bench task to see if it works end-to-end

---

## Success Criteria

Phase 1 is complete when:
- [ ] All code from tasks 1.1-1.4 is implemented and working
- [ ] `pytest` passes (existing tests still work)
- [ ] Can call `think("test reasoning")` and see it in SQLite traces
- [ ] SWEPhaseState tracks thinking events
- [ ] Temptation catalog is complete and documented
- [ ] One SWE-bench task runs successfully with new infrastructure

---

## After Phase 1

Move to **Phase 2**: System Prompt Integration
- Rewrite SWE-bench prompts with metacognitive guidance
- Add required thinking checkpoints
- Integrate temptation awareness

See ROADMAP.md for full details.

---

## Important Notes

**Development Philosophy:**
- Test as you build (don't batch everything then test)
- Keep existing functionality working (backward compatibility)
- Use the design docs (don't improvise different approaches)
- Ask questions if specs are unclear

**Code Quality:**
- Type hints on all new functions
- Docstrings with examples
- Error handling for edge cases
- Comments explaining non-obvious choices

**Git Hygiene:**
- Commit after each major subtask
- Clear commit messages explaining WHAT and WHY
- Push to branch `claude/review-latest-pr-YACKZ`

---

## Questions?

If you encounter:
- **Unclear specs:** Ask for clarification (don't guess)
- **Design conflicts:** Propose alternative and explain why
- **Missing context:** Check METACOGNITIVE_ARCHITECTURE.md first
- **Technical blockers:** Document the blocker and propose workaround

---

## Quick Reference

**Key Files:**
- `src/compymac/swe_workflow.py` - Phase system and SWEPhaseState
- `src/compymac/local_harness.py` - Tool implementations
- `src/compymac/trace_store.py` - Event logging and persistence
- `src/compymac/temptations.py` - NEW FILE you need to create

**Existing V4 Patterns to Follow:**
- Evidence-based gating: `validate_test_evidence()` in swe_workflow.py:365
- Bash execution tracking: `record_bash_execution()` in swe_workflow.py:343
- Edit tracking: `record_file_edit()` in swe_workflow.py:356

**Resources:**
- System prompts analyzed: `/tmp/ai-prompts-repo/` (Devin, Cline, Orchids, etc.)
- Research papers: Links in METACOGNITIVE_ARCHITECTURE.md references section

---

**Good luck! You're building the foundation for truly observable AI agents.**

---

**Version:** 1.0
**Created:** 2025-12-27
**Status:** Ready for Phase 1 implementation

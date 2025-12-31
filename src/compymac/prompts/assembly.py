"""
Prompt assembly with cache optimization.

Key principle: Stable prefix + cache breakpoint + dynamic content

This module assembles modular prompt components into a complete system prompt,
optimized for KV-cache hit rates in production LLM inference.
"""

from pathlib import Path

PROMPT_DIR = Path(__file__).parent


def load_module(name: str) -> str:
    """
    Load a prompt module by name.

    Args:
        name: Module path relative to prompts directory (e.g., "core/identity")

    Returns:
        Contents of the markdown file
    """
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt module not found: {path}")
    return path.read_text()


def assemble_prompt(
    workflow: str,
    task: dict,
    tool_mask: list[str] | None = None,
    tool_schemas: str | None = None,
    include_cache_breakpoint: bool = True,
) -> str:
    """
    Assemble the full system prompt.

    Structure (cache-optimized):
    1. Stable prefix (identity, invariants, security, tools, control)
    2. Cache breakpoint marker
    3. Workflow-specific rules
    4. Tool mask
    5. Task description

    Args:
        workflow: Name of workflow (e.g., "swe_bench")
        task: Task dictionary with instance_id, problem_statement, repo_path
        tool_mask: Optional list of available tools for this task
        tool_schemas: Optional JSON schemas for tools
        include_cache_breakpoint: Whether to include cache breakpoint marker

    Returns:
        Complete assembled system prompt
    """
    sections = []

    # === STABLE PREFIX (cached) ===
    sections.append(load_module("core/identity"))
    sections.append(load_module("core/invariants"))
    sections.append(load_module("core/security"))
    sections.append(load_module("tools/registry"))
    sections.append(load_module("control/protocol"))

    # === CACHE BREAKPOINT ===
    if include_cache_breakpoint:
        sections.append("<!-- CACHE_BREAKPOINT -->")

    # === SEMI-STABLE (per workflow) ===
    sections.append(load_module(f"workflows/{workflow}"))

    # === TOOL MASK ===
    if tool_mask:
        mask_text = f"## Active Tool Mask\n\nAVAILABLE: {', '.join(tool_mask)}"
        sections.append(mask_text)

    # === TOOL SCHEMAS ===
    if tool_schemas:
        schema_section = f"## Tool Schemas\n\n{tool_schemas}"
        sections.append(schema_section)

    # === DYNAMIC (per task) ===
    task_text = format_task(task)
    sections.append(task_text)

    return "\n\n---\n\n".join(sections)


def format_task(task: dict) -> str:
    """
    Format task description for inclusion in prompt.

    Args:
        task: Dictionary with task details

    Returns:
        Formatted task section
    """
    instance_id = task.get("instance_id", "N/A")
    problem_statement = task.get("problem_statement", "No problem statement provided.")
    repo_path = task.get("repo_path", "N/A")

    return f"""## Current Task

**Instance ID:** {instance_id}

**Problem Statement:**
{problem_statement}

**Repository:** {repo_path}
"""


def get_stable_prefix() -> str:
    """
    Get just the stable prefix portion of the prompt.

    This is useful for pre-computing cache keys or for systems
    that support explicit cache breakpoints.

    Returns:
        The stable prefix that should be cached
    """
    sections = [
        load_module("core/identity"),
        load_module("core/invariants"),
        load_module("core/security"),
        load_module("tools/registry"),
        load_module("control/protocol"),
    ]
    return "\n\n---\n\n".join(sections)


def list_available_workflows() -> list[str]:
    """
    List all available workflow templates.

    Returns:
        List of workflow names (without .md extension)
    """
    workflows_dir = PROMPT_DIR / "workflows"
    if not workflows_dir.exists():
        return []
    return [f.stem for f in workflows_dir.glob("*.md")]


# Convenience function for backward compatibility with existing code
def get_swe_bench_prompt(
    instance_id: str,
    problem_statement: str,
    repo_path: str,
    tool_schemas: str | None = None,
) -> str:
    """
    Get a complete SWE-bench prompt.

    This is a convenience function for the most common use case.

    Args:
        instance_id: SWE-bench instance identifier
        problem_statement: The problem to solve
        repo_path: Path to the repository
        tool_schemas: Optional JSON schemas for tools

    Returns:
        Complete assembled prompt for SWE-bench task
    """
    task = {
        "instance_id": instance_id,
        "problem_statement": problem_statement,
        "repo_path": repo_path,
    }
    return assemble_prompt(
        workflow="swe_bench",
        task=task,
        tool_schemas=tool_schemas,
    )

"""Prompt templates for CompyMac agents."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_swe_bench_v5_prompt() -> str:
    """Load the V5 SWE-bench system prompt template.

    Returns:
        The raw prompt template with placeholders for task-specific context.
    """
    prompt_file = PROMPTS_DIR / "swe_bench_v5.md"
    return prompt_file.read_text()


__all__ = ["load_swe_bench_v5_prompt", "PROMPTS_DIR"]

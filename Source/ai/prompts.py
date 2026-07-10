"""
Dunju AI — Prompt Builder
Constructs system prompts from expert definitions.
"""

from ai.experts import get_expert_by_name

BASE_SUFFIX = """

You are part of Dunju AI — an intelligent Business AI Platform.
Core philosophy: Build. Automate. Scale.
Always aim to help users understand not only HOW to solve a problem but also WHY a solution is recommended.
Be professional, friendly, structured, and educational in all responses.
"""


def build_system_prompt(expert_name: str = "Business") -> str:
    """Build the full system prompt for a given expert name."""
    expert = get_expert_by_name(expert_name)
    if expert:
        return expert["system_prompt"] + BASE_SUFFIX
    return "You are Dunju AI Assistant. Be helpful, professional, and practical." + BASE_SUFFIX

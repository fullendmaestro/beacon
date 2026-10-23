"""Beacon Agent package."""

from beacon_agent.model import get_bedrock_model, get_model, get_vertex_model
from beacon_agent.prompt import (
    BEACON_SYSTEM_PROMPT,
    SENTINEL_SYSTEM_PROMPT,
    get_beacon_system_prompt,
    get_sentinel_system_prompt,
)

__all__ = [
    "BEACON_SYSTEM_PROMPT",
    "SENTINEL_SYSTEM_PROMPT",
    "get_beacon_system_prompt",
    "get_bedrock_model",
    "get_model",
    "get_sentinel_system_prompt",
    "get_vertex_model",
]

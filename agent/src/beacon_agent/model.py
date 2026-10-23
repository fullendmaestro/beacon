"""Model factory for Beacon agents, supporting Google Cloud Vertex AI and Amazon Bedrock."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()

logger = logging.getLogger(__name__)

# Known model name prefixes for provider resolution
_BEDROCK_PREFIXES = ("us.", "eu.", "anthropic.", "amazon.", "meta.", "cohere.", "ai21.")


def _is_bedrock_model_id(model_id: str) -> bool:
    """Return True if model_id appears to be an AWS Bedrock inference profile or model ID."""
    lower = model_id.lower()
    return any(lower.startswith(prefix) for prefix in _BEDROCK_PREFIXES) or "claude" in lower or "nova" in lower


def get_vertex_model(
    model_name: str | None = None,
    temperature: float = 0.2,
    project: str | None = None,
    location: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Instantiate a LangChain chat model backed by Google Cloud Vertex AI.

    Default configuration is driven by:
      - Model: BEACON_VERTEX_MODEL or BEACON_AGENT_MODEL (defaults to 'gemini-2.5-flash')
      - Project: GOOGLE_CLOUD_PROJECT (defaults to 'master-inn-505014-t1')
      - Location: GOOGLE_CLOUD_LOCATION (defaults to 'us-central1')
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    resolved_model = (
        model_name
        or os.getenv("BEACON_VERTEX_MODEL")
        or os.getenv("GOOGLE_MODEL")
    )
    if not resolved_model:
        agent_model_env = os.getenv("BEACON_AGENT_MODEL", "")
        # If BEACON_AGENT_MODEL points to a Bedrock model, fall back to gemini for Vertex
        if agent_model_env and not _is_bedrock_model_id(agent_model_env):
            resolved_model = agent_model_env
        else:
            resolved_model = "gemini-2.5-flash"

    resolved_project = project or os.getenv("GOOGLE_CLOUD_PROJECT", "master-inn-505014-t1")
    resolved_location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    logger.info(
        "Initializing Vertex AI model '%s' (project=%s, location=%s, temperature=%.2f)",
        resolved_model,
        resolved_project,
        resolved_location,
        temperature,
    )

    return ChatGoogleGenerativeAI(
        model=resolved_model,
        vertexai=True,
        project=resolved_project,
        location=resolved_location,
        temperature=temperature,
        **kwargs,
    )


def get_bedrock_model(
    model_name: str | None = None,
    temperature: float = 0.2,
    region_name: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Instantiate a LangChain chat model backed by Amazon Bedrock using ChatBedrockConverse.

    Default configuration is driven by:
      - Model: BEACON_BEDROCK_MODEL or BEACON_AGENT_MODEL (defaults to 'us.anthropic.claude-3-5-sonnet-20241022-v2:0')
      - Region: AWS_REGION (defaults to 'us-east-1')
      - Profile: AWS_PROFILE (optional)
      - Credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (optional, falls back to AWS CLI / SSO)
    """
    try:
        from langchain_aws import ChatBedrockConverse
    except ImportError as exc:
        raise ImportError(
            "The 'langchain-aws' package is required for Amazon Bedrock models. "
            "Install it with `pip install langchain-aws` or `uv add langchain-aws`."
        ) from exc

    resolved_model = (
        model_name
        or os.getenv("BEACON_BEDROCK_MODEL")
        or os.getenv("BEDROCK_MODEL")
    )
    if not resolved_model:
        agent_model_env = os.getenv("BEACON_AGENT_MODEL", "")
        # If BEACON_AGENT_MODEL points to a Gemini model, fall back to Claude for Bedrock
        if agent_model_env and not agent_model_env.lower().startswith("gemini"):
            resolved_model = agent_model_env
        else:
            resolved_model = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

    resolved_region = region_name or os.getenv("AWS_REGION", "us-east-1")

    bedrock_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "region_name": resolved_region,
        "temperature": temperature,
        **kwargs,
    }

    # Pass profile name if configured and not already provided
    profile = os.getenv("AWS_PROFILE")
    if profile and "credentials_profile_name" not in bedrock_kwargs:
        bedrock_kwargs["credentials_profile_name"] = profile

    # Pass explicit credentials if configured and not already provided
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_token = os.getenv("AWS_SESSION_TOKEN")
    if aws_key and "aws_access_key_id" not in bedrock_kwargs:
        bedrock_kwargs["aws_access_key_id"] = aws_key
    if aws_secret and "aws_secret_access_key" not in bedrock_kwargs:
        bedrock_kwargs["aws_secret_access_key"] = aws_secret
    if aws_token and "aws_session_token" not in bedrock_kwargs:
        bedrock_kwargs["aws_session_token"] = aws_token

    logger.info(
        "Initializing Bedrock Converse model '%s' (region=%s, temperature=%.2f)",
        resolved_model,
        resolved_region,
        temperature,
    )

    return ChatBedrockConverse(**bedrock_kwargs)


def get_model(
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.2,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Return a LangGraph/LangChain chat model based on the selected provider.

    Supported providers:
      - 'vertexai', 'vertex', 'google_vertexai': Google Cloud Vertex AI (ChatGoogleGenerativeAI)
      - 'bedrock', 'aws', 'amazon': Amazon Bedrock (ChatBedrockConverse)

    Provider resolution:
      1. Explicit `provider` argument.
      2. `BEACON_PROVIDER` or `MODEL_PROVIDER` environment variable.
      3. Defaults to 'vertexai' (local development default).
    """
    resolved_provider = (
        provider
        or os.getenv("BEACON_PROVIDER")
        or os.getenv("MODEL_PROVIDER")
        or "vertexai"
    ).strip().lower()

    if resolved_provider in {"vertexai", "vertex", "google_vertexai", "google", "gemini"}:
        return get_vertex_model(
            model_name=model_name,
            temperature=temperature,
            **kwargs,
        )

    if resolved_provider in {"bedrock", "aws", "amazon"}:
        return get_bedrock_model(
            model_name=model_name,
            temperature=temperature,
            **kwargs,
        )

    raise ValueError(
        f"Unsupported model provider: '{resolved_provider}'. "
        "Supported providers are 'vertexai' and 'bedrock'."
    )


__all__ = [
    "get_model",
    "get_vertex_model",
    "get_bedrock_model",
]

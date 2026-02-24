"""
OpenAI API integration for text rewriting.

Handles text transformation using OpenAI's API with preset prompts.
"""
from openai import OpenAI, OpenAIError
from typing import Optional
from enum import Enum


class RewriteMode(Enum):
    """Available rewrite preset modes."""
    FIX_GRAMMAR = "fix_grammar"
    PROFESSIONAL = "professional"
    CONCISE = "concise"
    FRIENDLY = "friendly"


# System prompts for each rewrite mode
SYSTEM_PROMPTS = {
    RewriteMode.FIX_GRAMMAR: (
        "You are a grammar and spelling assistant. Correct any grammar, spelling, "
        "and punctuation errors in the given text while preserving the original "
        "meaning, tone, and language. Return only the corrected text without "
        "any explanations or additional content."
    ),
    RewriteMode.PROFESSIONAL: (
        "You are a professional writing assistant. Rewrite the given text to be "
        "formal and business-appropriate while maintaining the original meaning "
        "and language. Use professional vocabulary and structure. Return only "
        "the rewritten text without any explanations or additional content."
    ),
    RewriteMode.CONCISE: (
        "You are a concise writing assistant. Shorten the given text while "
        "preserving the key meaning and information. Remove unnecessary words "
        "and redundancy while keeping the original language. Return only the "
        "shortened text without any explanations or additional content."
    ),
    RewriteMode.FRIENDLY: (
        "You are a friendly writing assistant. Rewrite the given text to have "
        "a warm, casual, and approachable tone while maintaining the original "
        "meaning and language. Return only the rewritten text without any "
        "explanations or additional content."
    ),
}

# Display names for UI
DISPLAY_NAMES = {
    RewriteMode.FIX_GRAMMAR: "Fix Grammar",
    RewriteMode.PROFESSIONAL: "Professional",
    RewriteMode.CONCISE: "Concise",
    RewriteMode.FRIENDLY: "Friendly",
}


class RewriteError(Exception):
    """Base exception for rewrite errors."""
    pass


class APIKeyError(RewriteError):
    """Raised when API key is missing or invalid."""
    pass


class NetworkError(RewriteError):
    """Raised when network request fails."""
    pass


class RateLimitError(RewriteError):
    """Raised when API rate limit is reached."""
    pass


class RewriteAPI:
    """Handles text rewriting using OpenAI's API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: Optional[str] = None):
        """
        Initialize the RewriteAPI.

        Args:
            api_key: OpenAI API key.
            model: The model to use for rewriting.
            base_url: Custom base URL for OpenAI-compatible API (optional).
        """
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = model
        self.base_url = base_url

    def set_model(self, model: str):
        """
        Update the model to use.

        Args:
            model: The model name (e.g., 'gpt-4o', 'gpt-4o-mini').
        """
        self.model = model

    def rewrite(self, text: str, mode: RewriteMode, thinking_mode: bool = False) -> str:
        """
        Rewrite text using the specified mode.

        Args:
            text: The text to rewrite.
            mode: The rewrite mode to apply.
            thinking_mode: If True, use extended thinking for more thorough rewriting.

        Returns:
            The rewritten text.

        Raises:
            RewriteError: If the rewrite fails.
        """
        if not text or not text.strip():
            return text

        try:
            print(f"API call: model={self.model}, base_url={self.base_url}, thinking_mode={thinking_mode}", flush=True)

            # Build system prompt with thinking mode enhancement
            system_prompt = SYSTEM_PROMPTS[mode]
            if thinking_mode:
                system_prompt = (
                    f"{SYSTEM_PROMPTS[mode]}\n\n"
                    "Before providing your final answer, think through this step-by-step:\n"
                    "1. Analyze the original text's structure, tone, and key points\n"
                    "2. Identify areas that need improvement based on the rewrite goal\n"
                    "3. Consider multiple ways to improve the text\n"
                    "4. Select the best approach and apply it\n"
                    "5. Return only the final rewritten text without explanations"
                )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.7,
            )
            print(f"API response type: {type(response)}, value: {response}", flush=True)

            if response is None or not response.choices:
                raise RewriteError("Empty response from API - check your model and base URL settings")

            content = response.choices[0].message.content
            if content is None:
                raise RewriteError("API returned empty content")

            return content.strip()

        except RewriteError:
            raise
        except OpenAIError as e:
            print(f"OpenAI error: {type(e).__name__}: {e}", flush=True)
            self._handle_openai_error(e)
            raise RewriteError(f"API error: {e}")
        except Exception as e:
            print(f"Unexpected API error: {type(e).__name__}: {e}", flush=True)
            raise RewriteError(f"API error: {e}")

    def _handle_openai_error(self, error: OpenAIError):
        """
        Convert OpenAI errors to appropriate RewriteError types.

        Args:
            error: The OpenAI error to handle.

        Raises:
            APIKeyError: For authentication errors.
            RateLimitError: For rate limit errors.
            NetworkError: For network-related errors.
        """
        error_message = str(error).lower()
        error_code = getattr(error, "code", None)

        if error_code in ("invalid_api_key", "401"):
            raise APIKeyError("Invalid API key - check Vox settings")
        elif error_code == "429" or "rate" in error_message:
            raise RateLimitError("OpenAI rate limit reached - please wait")
        elif "connection" in error_message or "network" in error_message:
            raise NetworkError("Network error - check your connection")
        elif "authentication" in error_message:
            raise APIKeyError("Authentication failed - check your API key")

    @staticmethod
    def get_display_name(mode: RewriteMode) -> str:
        """Get the display name for a rewrite mode."""
        return DISPLAY_NAMES[mode]

    @staticmethod
    def get_all_modes() -> list[tuple[RewriteMode, str]]:
        """Get all available rewrite modes with their display names."""
        return [(mode, DISPLAY_NAMES[mode]) for mode in RewriteMode]

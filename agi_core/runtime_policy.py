"""Explicit resource limits and model overrides, never invented quality scores."""
from dataclasses import dataclass
import json
import os


def positive_env(name, default, *, allow_zero=False):
    value = int(os.environ.get(name, default))
    if value < (0 if allow_zero else 1):
        raise ValueError(f"{name} has an invalid limit")
    return value


@dataclass(frozen=True)
class RuntimePolicy:
    max_steps: int = 128
    command_seconds: int = 3600
    stall_attempts: int = 3
    parallel_workers: int = 1
    output_chars: int = 12000
    context_chars: int = 60000
    recovery_attempts: int = 2
    request_audit: bool = True

    @classmethod
    def from_env(cls):
        audit = os.environ.get('AURORA_REQUEST_AUDIT','1')
        if audit not in {'0','1'}:
            raise ValueError('AURORA_REQUEST_AUDIT must be 0 or 1')
        return cls(
            max_steps=positive_env("AURORA_MISSION_MAX_STEPS", 128, allow_zero=True),
            command_seconds=positive_env("AURORA_COMMAND_TIMEOUT", 3600),
            stall_attempts=positive_env("AURORA_STALL_ATTEMPTS", 3),
            parallel_workers=positive_env("AURORA_PARALLEL_WORKERS", 1),
            output_chars=positive_env("AURORA_TOOL_OUTPUT_CHARS", 12000),
            context_chars=positive_env("AURORA_CONTEXT_CHARS", 60000),
            recovery_attempts=positive_env("AURORA_RECOVERY_ATTEMPTS", 2, allow_zero=True),
            request_audit=audit=='1',
        )


def validate_context_tokens(value):
    """Validate an explicit per-mission context request, never coerce JSON types."""
    if value is not None and (type(value) is not int or not 1024 <= value <= 131072):
        raise ValueError("context_tokens must be an integer from 1024 to 131072")
    return value


def model_options(context_tokens=None):
    """By default use the installed model's native settings, including context."""
    options = json.loads(os.environ.get("AURORA_MODEL_OPTIONS", "{}"))
    if not isinstance(options, dict) or any(not isinstance(v, (int, float, bool, str)) for v in options.values()):
        raise ValueError("AURORA_MODEL_OPTIONS must contain scalar Ollama options")
    if validate_context_tokens(context_tokens) is not None:
        options['num_ctx'] = context_tokens
    return options

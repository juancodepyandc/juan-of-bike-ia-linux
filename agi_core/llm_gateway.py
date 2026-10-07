"""Ollama transport: native model options, checked completion and measured usage."""
from __future__ import annotations
import asyncio
import inspect
import json
import logging
import os
import time

import aiohttp
from .runtime_policy import model_options, positive_env, validate_context_tokens

logger = logging.getLogger("AuroraAGI.Gateway")


class ModelReadTimeout(asyncio.TimeoutError):
    """A model transport deadline, distinct from the client-to-bridge link."""


def _model_timeout(exc, model, timeout, received_chars):
    phase = (f'apres {received_chars} caracteres de reponse' if received_chars
             else 'avant le premier bloc de reponse')
    return ModelReadTimeout(
        f'Ollama: delai de lecture depasse pour le modele {model} {phase} '
        f'(limite entre blocs: {timeout.sock_read}s). '
        'Verifier le serveur Ollama, la RAM et le pilote GPU; choisir un modele '
        'adapte au serveur ou regler explicitement AURORA_MODEL_READ_TIMEOUT. '
        f'Cause: {type(exc).__name__}: {exc}')


class LLMGateway:
    def __init__(self, ollama_url: str | None = None, *, context_tokens=None):
        self.ollama_url = (ollama_url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip('/')
        self.default_model = os.environ.get("AURORA_DEFAULT_MODEL", "qwen3-coder-next:q4_K_M")
        self.context_tokens = validate_context_tokens(context_tokens)

    def timeout(self):
        return aiohttp.ClientTimeout(total=None, sock_connect=10,
                                    sock_read=positive_env('AURORA_MODEL_READ_TIMEOUT', 300))

    async def get_available_models(self) -> list[str]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{self.ollama_url}/api/tags") as response:
                response.raise_for_status()
                data = await response.json()
        return [item["name"] for item in data.get("models", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)]

    async def resolve_model(self, requested: str | None = None) -> str:
        if requested:
            return requested
        available = await self.get_available_models()
        if self.default_model not in available:
            raise RuntimeError("Configured default model is not installed; choose an available model explicitly")
        return self.default_model

    async def running_context_window(self, model, session=None):
        """Observe the loaded runner's window, not the model's theoretical maximum."""
        if session is None:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
                return await self.running_context_window(model,client)
        try:
            async with session.get(f'{self.ollama_url}/api/ps',timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()
            for item in data.get('models',[]):
                if item.get('name') == model or item.get('model') == model:
                    value = item.get('context_length')
                    if isinstance(value,int) and not isinstance(value,bool) and value>0:
                        return value
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
            logger.debug('Running model context window unavailable',exc_info=True)
        return None

    async def chat_chunks(self, messages, model=None, *, session=None, on_metrics=None, response_format=None):
        if session is None:
            async with aiohttp.ClientSession(timeout=self.timeout()) as client:
                async for chunk in self.chat_chunks(messages, model, session=client, on_metrics=on_metrics,
                                                    response_format=response_format):
                    yield chunk
            return
        selected = await self.resolve_model(model)
        payload = {'model': selected, 'messages': messages, 'stream': True,
                   'options': model_options(self.context_tokens)}
        if response_format is not None:
            payload['format'] = response_format
        started, last_flush = time.monotonic(), time.monotonic()
        complete, received, pending = False, False, ''
        received_chars = 0
        try:
            async with session.post(f'{self.ollama_url}/api/chat', json=payload) as response:
                response.raise_for_status()
                async for line in response.content:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get('error'):
                        raise RuntimeError(str(data['error']))
                    if data.get('done'):
                        complete = True
                        if on_metrics:
                            measured = {key: data[key] for key in (
                                'total_duration', 'load_duration', 'prompt_eval_count',
                                'prompt_eval_duration', 'eval_count', 'eval_duration') if key in data}
                            measured.update(model=selected, wall_seconds=time.monotonic()-started,
                                            options=payload['options'])
                            if measured.get('eval_duration', 0) > 0:
                                measured['tokens_per_second'] = measured.get('eval_count', 0) * 1e9 / measured['eval_duration']
                            result = on_metrics(measured)
                            if inspect.isawaitable(result):
                                await result
                    content = data.get('message', {}).get('content', '')
                    received = received or bool(content.strip())
                    received_chars += len(content)
                    pending += content
                    # Coalesce small fragments before durable logging and terminal redraws.
                    if pending and (len(pending) >= 128 or time.monotonic()-last_flush >= .05):
                        yield pending
                        pending, last_flush = '', time.monotonic()
        except asyncio.TimeoutError as exc:
            raise _model_timeout(exc, selected, session.timeout, received_chars) from exc
        if pending:
            yield pending
        if not complete or not received:
            raise RuntimeError('Model stream ended without a complete answer')

    async def generate_stream(self, system_prompt: str, user_prompt: str, on_token, model=None, *, response_format=None) -> str:
        answer = ''
        async for chunk in self.chat_chunks([
            {'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}
        ], model, response_format=response_format):
            answer += chunk
            result = on_token(chunk)
            if inspect.isawaitable(result):
                await result
        return answer.strip()

    async def generate(self, system_prompt: str, user_prompt: str, model=None, *, response_format=None) -> str:
        return await self.generate_stream(system_prompt, user_prompt, lambda _: None, model, response_format=response_format)

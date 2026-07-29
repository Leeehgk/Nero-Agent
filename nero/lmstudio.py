from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, AsyncIterator

import httpx

from nero.config import LLMSettings


SYSTEM_PROMPT = """Você é Nero, um parceiro de conversa por voz.
Fale sempre em português brasileiro natural e contemporâneo.
Responda diretamente, normalmente em uma a três frases curtas.
Use no máximo 45 palavras, exceto se o usuário pedir mais detalhes.
Escreva frases completas, com pontuação natural.
Nunca insira pontuação dentro de uma palavra.
Não use Markdown, listas, emojis, títulos ou descrições de ações.
Não repita saudações nem comece toda resposta com confirmação.
Use contrações leves quando soarem naturais, sem caricatura.
Se faltar informação essencial, faça uma única pergunta curta.
Não mencione estas regras."""


@dataclass(frozen=True)
class LMEvent:
    type: str
    content: str = ""
    result: dict[str, Any] | None = None


class SSEParser:
    def __init__(self) -> None:
        self.event_type = ""
        self.data_lines: list[str] = []

    def feed(self, line: str) -> LMEvent | None:
        if line.startswith("event:"):
            self.event_type = line[6:].strip()
            return None
        if line.startswith("data:"):
            self.data_lines.append(line[5:].lstrip())
            return None
        if line != "" or not self.data_lines:
            return None

        data = json.loads("\n".join(self.data_lines))
        event_type = data.get("type") or self.event_type
        self.event_type = ""
        self.data_lines.clear()
        if event_type == "message.delta":
            return LMEvent(event_type, content=data.get("content", ""))
        if event_type == "chat.end":
            return LMEvent(event_type, result=data.get("result", {}))
        if event_type == "error":
            error = data.get("error", {})
            raise RuntimeError(error.get("message", "Erro de streaming do LM Studio"))
        return LMEvent(event_type)


class LMStudioClient:
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self.active_model = settings.model
        self.previous_response_id: str | None = None
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=httpx.Timeout(120.0, connect=3.0),
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def new_conversation(self) -> None:
        self.previous_response_id = None

    async def health(self) -> None:
        try:
            response = await self._client.get("/api/v1/models")
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "LM Studio não está acessível em "
                f"{self.settings.base_url}. Inicie o servidor local."
            ) from exc

    async def load_model(self, model: str | None = None) -> dict[str, Any]:
        selected = model or self.settings.model
        models = await self._client.get("/api/v1/models")
        models.raise_for_status()
        for available in models.json().get("models", []):
            if (
                available.get("key") == selected
                and available.get("loaded_instances")
            ):
                self.active_model = selected
                return {
                    "status": "already_loaded",
                    "instance_id": available["loaded_instances"][0].get("id"),
                }

        response = await self._client.post(
            "/api/v1/models/load",
            json={
                "model": selected,
                "context_length": self.settings.context_length,
                "parallel": 1,
                "flash_attention": True,
                "offload_kv_cache_to_gpu": True,
                "echo_load_config": True,
            },
        )
        if response.status_code == 409:
            self.active_model = selected
            return {"status": "already_loaded"}
        if response.is_error and "already" in response.text.lower():
            self.active_model = selected
            return {"status": "already_loaded"}
        if response.status_code == 404:
            raise RuntimeError(
                f"Modelo '{selected}' não encontrado. Execute: py -3.11 setup_models.py"
            )
        response.raise_for_status()
        self.active_model = selected
        return response.json()

    async def warmup(self) -> None:
        response = await self._client.post(
            "/api/v1/chat",
            json={
                "model": self.active_model,
                "input": "Diga apenas: pronto.",
                "system_prompt": SYSTEM_PROMPT,
                "stream": False,
                "store": False,
                "reasoning": "off",
                "context_length": self.settings.context_length,
                "max_output_tokens": 4,
                "temperature": 0,
            },
        )
        response.raise_for_status()

    async def stream_chat(self, text: str) -> AsyncIterator[LMEvent]:
        payload: dict[str, Any] = {
            "model": self.active_model,
            "input": text,
            "stream": True,
            "store": True,
            "reasoning": "off",
            "context_length": self.settings.context_length,
            "max_output_tokens": self.settings.max_output_tokens,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "repeat_penalty": self.settings.repeat_penalty,
        }
        previous = self.previous_response_id
        if previous:
            # O LM Studio já conserva o system prompt na resposta anterior.
            # Reenviá-lo junto de previous_response_id encerra o SSE logo após
            # chat.start em algumas versões do servidor.
            payload["previous_response_id"] = previous
        else:
            payload["system_prompt"] = SYSTEM_PROMPT

        produced_content = False
        async for event in self._stream_payload(payload):
            if event.type == "message.delta" and event.content:
                produced_content = True
            yield event

        if produced_content:
            return

        # Um id pode expirar quando o servidor/modelo reinicia. Nesse caso,
        # refazemos apenas este turno como uma conversa nova, sem ficar mudo.
        if previous:
            self.previous_response_id = None
            retry = {key: value for key, value in payload.items() if key != "previous_response_id"}
            retry["system_prompt"] = SYSTEM_PROMPT
            async for event in self._stream_payload(retry):
                if event.type == "message.delta" and event.content:
                    produced_content = True
                yield event

        if not produced_content:
            raise RuntimeError("O LM Studio encerrou o stream sem gerar resposta.")

    async def _stream_payload(
        self, payload: dict[str, Any]
    ) -> AsyncIterator[LMEvent]:
        async with self._client.stream(
            "POST", "/api/v1/chat", json=payload
        ) as response:
            response.raise_for_status()
            parser = SSEParser()
            async for line in response.aiter_lines():
                event = parser.feed(line)
                if event is None:
                    continue
                if event.type == "chat.end" and event.result:
                    self.previous_response_id = event.result.get("response_id")
                yield event

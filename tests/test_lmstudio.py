import asyncio
import json
from pathlib import Path

import httpx

from nero.config import load_settings
from nero.lmstudio import LMStudioClient, SSEParser


def test_sse_parser_reads_delta_and_end() -> None:
    parser = SSEParser()
    assert parser.feed("event: message.delta") is None
    assert parser.feed('data: {"type":"message.delta","content":"Olá"}') is None
    delta = parser.feed("")
    assert delta is not None
    assert delta.content == "Olá"

    parser.feed("event: chat.end")
    parser.feed(
        'data: {"type":"chat.end","result":{"response_id":"resp_1","stats":{}}}'
    )
    end = parser.feed("")
    assert end is not None
    assert end.result["response_id"] == "resp_1"


def test_load_model_reuses_existing_instance() -> None:
    async def scenario() -> None:
        settings = load_settings(Path("settings.toml")).llm
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.method)
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "key": settings.model,
                            "loaded_instances": [{"id": settings.model}],
                        }
                    ]
                },
            )

        client = LMStudioClient(settings)
        await client.close()
        client._client = httpx.AsyncClient(
            base_url=settings.base_url,
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.load_model()
            assert result["status"] == "already_loaded"
            assert calls == ["GET"]
        finally:
            await client.close()

    asyncio.run(scenario())


def test_continuation_omits_duplicate_system_prompt() -> None:
    async def scenario() -> None:
        settings = load_settings(Path("settings.toml")).llm

        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert payload["previous_response_id"] == "resp_old"
            assert "system_prompt" not in payload
            body = (
                'event: message.delta\n'
                'data: {"type":"message.delta","content":"Continuo ouvindo."}\n\n'
                'event: chat.end\n'
                'data: {"type":"chat.end","result":{"response_id":"resp_new"}}\n\n'
            )
            return httpx.Response(200, content=body.encode())

        client = LMStudioClient(settings)
        await client.close()
        client._client = httpx.AsyncClient(
            base_url=settings.base_url,
            transport=httpx.MockTransport(handler),
        )
        client.previous_response_id = "resp_old"
        try:
            content = ""
            async for event in client.stream_chat("Você me escuta?"):
                content += event.content
            assert content == "Continuo ouvindo."
            assert client.previous_response_id == "resp_new"
        finally:
            await client.close()

    asyncio.run(scenario())

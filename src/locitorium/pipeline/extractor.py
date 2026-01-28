from __future__ import annotations

from locitorium.clients.ollama import OllamaClient
from locitorium.prompts.extract import ExtractOutput, build_prompt


def _dedupe_mentions(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


async def extract_mentions(
    client: OllamaClient, text: str, max_mentions: int, tag: str
) -> list[str]:
    prompt = build_prompt(text)
    schema = ExtractOutput.model_json_schema()
    data = await client.generate(prompt=prompt, schema=schema, tag=tag)
    parsed = ExtractOutput.model_validate(data)
    mentions = _dedupe_mentions([m.mention for m in parsed.mentions])
    return mentions[:max_mentions]

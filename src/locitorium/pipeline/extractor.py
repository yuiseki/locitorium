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


def _filter_mentions(text: str, mentions: list[str]) -> list[str]:
    text_fold = text.casefold()
    filtered: list[str] = []
    for mention in mentions:
        if mention in text or mention.casefold() in text_fold:
            filtered.append(mention)
    return filtered


async def extract_mentions(
    client: OllamaClient, text: str, max_mentions: int, tag: str
) -> list[str]:
    prompt = build_prompt(text)
    schema = ExtractOutput.model_json_schema()
    data = await client.generate(prompt=prompt, schema=schema, tag=tag)
    parsed = ExtractOutput.model_validate(data)
    mentions = _dedupe_mentions([m.mention for m in parsed.mentions])
    mentions = _filter_mentions(text, mentions)
    return mentions[:max_mentions]

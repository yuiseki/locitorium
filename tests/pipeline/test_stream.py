import asyncio
import json

from locitorium.pipeline import stream
from locitorium.pipeline.stream import StreamOptions, resolve_records, split_text


def _pred(doc_id, results):
    return {
        "doc_id": doc_id,
        "model_info": {"llm_model": "gvt-llm"},
        "results": results,
        "metrics": {"total_s": 0.1},
    }


def _result(mention_id, mention, status, osm_id=None):
    selected = None
    if osm_id is not None:
        selected = {
            "osm_type": "relation",
            "osm_id": osm_id,
            "lat": "35.77",
            "lon": "140.0",
            "bbox": ["0", "1", "2", "3"],
            "display_name": "鎌ケ谷市, 千葉県, 日本",
            "country_code": "JP",
        }
    return {
        "mention_id": mention_id,
        "mention": mention,
        "status": status,
        "selected": selected,
        "candidates": [],
    }


class StubResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class StubClient:
    """Stands in for httpx.AsyncClient; records every query it is asked."""

    def __init__(self, payloads=None, error=None):
        self.payloads = list(payloads or [])
        self.error = error
        self.queries = []

    async def get(self, url, params=None):
        self.queries.append((url, params))
        if self.error is not None:
            raise self.error
        payload = self.payloads.pop(0) if self.payloads else _pred("d", [])
        return StubResponse(payload)

    async def aclose(self):
        return None


def _collect(records, options, client, **kwargs):
    async def _run():
        return [
            row
            async for row in resolve_records(
                records, options, client=client, **kwargs
            )
        ]

    return asyncio.run(_run())


def test_identifiers_are_carried_to_every_row():
    records = [
        {"segment_id": "seg-1", "body": "鎌ヶ谷市と船橋市"},
        {"segment_id": "seg-2", "body": "松戸市"},
    ]
    client = StubClient(
        [
            _pred(
                "doc-a",
                [
                    _result("doc-a:0", "鎌ヶ谷市", "resolved", 2679943),
                    _result("doc-a:1", "船橋市", "resolved", 123),
                ],
            ),
            _pred("doc-b", [_result("doc-b:0", "松戸市", "resolved", 456)]),
        ]
    )
    options = StreamOptions(text_field="body", id_field="segment_id")

    rows = _collect(records, options, client)

    assert [row["input_id"] for row in rows] == ["seg-1", "seg-1", "seg-2"]
    assert [row["mention"] for row in rows] == ["鎌ヶ谷市", "船橋市", "松戸市"]
    assert rows[0]["osm_id"] == 2679943
    assert rows[0]["lat"] == 35.77
    assert rows[0]["doc_id"] == "doc-a"
    assert rows[0]["llm_model"] == "gvt-llm"


def test_missing_identifier_falls_back_to_line_number():
    client = StubClient([_pred("d", [_result("d:0", "Tokyo", "resolved", 1)])])
    rows = _collect([{"text": "Tokyo"}], StreamOptions(), client)
    assert rows[0]["input_id"] == "line:1"


def test_unresolved_statuses_are_not_dropped():
    records = [
        {"id": "a", "text": "Alex Pretti"},
        {"id": "b", "text": "no place here"},
        {"id": "c", "text": ""},
    ]
    client = StubClient(
        [
            _pred("d1", [_result("d1:0", "Alex Pretti", "no_candidate")]),
            _pred("d2", []),
        ]
    )
    rows = _collect(records, StreamOptions(), client)

    statuses = {row["input_id"]: row["status"] for row in rows}
    assert statuses == {
        "a": "no_candidate",
        "b": stream.STATUS_NO_MENTION,
        "c": stream.STATUS_MISSING_TEXT,
    }
    assert len(rows) == 3


def test_server_error_becomes_a_row():
    client = StubClient(error=RuntimeError("boom"))
    rows = _collect([{"id": "a", "text": "Tokyo"}], StreamOptions(), client)
    assert rows[0]["status"] == stream.STATUS_SERVER_ERROR
    assert "boom" in rows[0]["error"]


def test_too_long_input_errors_by_default_without_calling_server():
    client = StubClient()
    options = StreamOptions(max_chars=10)
    rows = _collect([{"id": "a", "text": "x" * 40}], options, client)

    assert client.queries == []
    assert rows[0]["status"] == stream.STATUS_INPUT_TOO_LONG
    assert "40 chars" in rows[0]["error"]


def test_too_long_input_can_be_split_into_chunks():
    client = StubClient(
        [
            _pred("d1", [_result("d1:0", "鎌ヶ谷市", "resolved", 1)]),
            _pred("d2", [_result("d2:0", "船橋市", "resolved", 2)]),
        ]
    )
    options = StreamOptions(max_chars=12, on_too_long="split")
    text = "鎌ヶ谷市に行った。" + "船橋市に行った。"
    rows = _collect([{"id": "a", "text": text}], options, client)

    assert len(client.queries) == 2
    assert [row["chunk_index"] for row in rows] == [0, 1]
    assert all(row["input_id"] == "a" for row in rows)


def test_too_long_input_can_be_truncated():
    client = StubClient([_pred("d1", [_result("d1:0", "Tokyo", "resolved", 1)])])
    options = StreamOptions(max_chars=5, on_too_long="truncate")
    rows = _collect([{"id": "a", "text": "Tokyo and Osaka"}], options, client)

    assert len(client.queries) == 1
    assert client.queries[0][1]["q"] == "Tokyo"
    assert rows[0]["status"] == "resolved"


def test_split_text_respects_max_chars_and_keeps_all_content():
    text = "一つ目の文です。二つ目の文です。三つ目の文です。"
    chunks = split_text(text, 10)
    assert all(len(chunk) <= 10 for chunk in chunks)
    assert "".join(chunks) == text


def test_resume_reuses_rows_without_calling_server(tmp_path):
    previous = tmp_path / "out.jsonl"
    previous.write_text(
        json.dumps({"input_id": "a", "status": "resolved", "mention": "Tokyo"}) + "\n",
        encoding="utf-8",
    )
    client = StubClient([_pred("d2", [_result("d2:0", "Osaka", "resolved", 2)])])
    records = [{"id": "a", "text": "Tokyo"}, {"id": "b", "text": "Osaka"}]

    rows = _collect(
        records,
        StreamOptions(),
        client,
        resume_rows=stream.load_resolved_rows(previous),
    )

    assert len(client.queries) == 1
    assert client.queries[0][1]["q"] == "Osaka"
    assert [row["input_id"] for row in rows] == ["a", "b"]

import csv
import io
import json

from typer.testing import CliRunner

from locitorium.cli import app

runner = CliRunner()


class StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class StubAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def get(self, url, params=None):
        return StubResponse(
            {
                "doc_id": "doc-1",
                "model_info": {"llm_model": "gvt-llm"},
                "results": [
                    {
                        "mention_id": "doc-1:0",
                        "mention": params["q"],
                        "status": "resolved",
                        "selected": {
                            "osm_type": "relation",
                            "osm_id": 2679943,
                            "lat": "35.77",
                            "lon": "140.0",
                            "bbox": [],
                            "display_name": "鎌ケ谷市, 千葉県, 日本",
                            "country_code": "JP",
                        },
                        "candidates": [],
                    }
                ],
            }
        )

    async def aclose(self):
        return None


def test_resolve_reads_stdin_and_writes_jsonl(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", StubAsyncClient)
    stdin = json.dumps({"id": "seg-1", "text": "鎌ヶ谷市"}, ensure_ascii=False) + "\n"

    result = runner.invoke(app, ["resolve", "--quiet"], input=stdin)

    assert result.exit_code == 0
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert rows[0]["input_id"] == "seg-1"
    assert rows[0]["osm_id"] == 2679943


def test_resolve_exits_nonzero_when_input_too_long(monkeypatch, tmp_path):
    monkeypatch.setattr("httpx.AsyncClient", StubAsyncClient)
    in_path = tmp_path / "in.jsonl"
    in_path.write_text(
        json.dumps({"id": "seg-1", "text": "x" * 50}) + "\n", encoding="utf-8"
    )
    out_path = tmp_path / "out.jsonl"

    result = runner.invoke(
        app,
        [
            "resolve",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
            "--max-chars",
            "10",
            "--quiet",
        ],
    )

    assert result.exit_code == 1
    lines = out_path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert rows[0]["status"] == "input_too_long"
    assert rows[0]["input_id"] == "seg-1"


def test_resolve_rejects_unknown_on_too_long_mode():
    result = runner.invoke(app, ["resolve", "--on-too-long", "nope"], input="")
    assert result.exit_code != 0


def test_resolve_rejects_unknown_format():
    result = runner.invoke(app, ["resolve", "--format", "yaml"], input="")
    assert result.exit_code != 0


def test_resolve_writes_json_array(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", StubAsyncClient)
    stdin = "".join(
        json.dumps({"id": f"seg-{i}", "text": "鎌ヶ谷市"}, ensure_ascii=False) + "\n"
        for i in (1, 2)
    )

    result = runner.invoke(app, ["resolve", "--format", "json", "--quiet"], input=stdin)

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [row["input_id"] for row in payload] == ["seg-1", "seg-2"]
    assert payload[0]["osm_id"] == 2679943


def test_resolve_writes_csv(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", StubAsyncClient)
    stdin = json.dumps({"id": "seg-1", "text": "鎌ヶ谷市"}, ensure_ascii=False) + "\n"

    result = runner.invoke(app, ["resolve", "--format", "csv", "--quiet"], input=stdin)

    assert result.exit_code == 0
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert rows[0]["input_id"] == "seg-1"
    assert rows[0]["osm_id"] == "2679943"


def test_resolve_writes_geojson(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", StubAsyncClient)
    stdin = json.dumps({"id": "seg-1", "text": "鎌ヶ谷市"}, ensure_ascii=False) + "\n"

    result = runner.invoke(
        app, ["resolve", "--format", "geojson", "--quiet"], input=stdin
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["type"] == "FeatureCollection"
    assert payload["features"][0]["geometry"]["coordinates"] == [140.0, 35.77]


def test_resolve_json_output_is_complete_on_failure_rows(monkeypatch, tmp_path):
    """A failing record must not leave an unterminated JSON document."""
    monkeypatch.setattr("httpx.AsyncClient", StubAsyncClient)
    in_path = tmp_path / "in.jsonl"
    in_path.write_text(
        json.dumps({"id": "seg-1", "text": "x" * 50}) + "\n", encoding="utf-8"
    )
    out_path = tmp_path / "out.json"

    result = runner.invoke(
        app,
        [
            "resolve",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
            "--format",
            "json",
            "--max-chars",
            "10",
            "--quiet",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload[0]["status"] == "input_too_long"

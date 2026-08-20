import csv
import io
import json

from locitorium.pipeline.output import (
    FORMAT_CSV,
    FORMAT_GEOJSON,
    FORMAT_JSON,
    FORMAT_JSONL,
    OUTPUT_FORMATS,
    ROW_FIELDS,
    STREAMING_FORMATS,
    open_writer,
)


def _row(**overrides):
    row = {field: None for field in ROW_FIELDS}
    row.update(
        {
            "input_id": "seg-1",
            "chunk_index": 0,
            "doc_id": "doc-1",
            "mention_id": "doc-1:0",
            "mention": "鎌ヶ谷市",
            "status": "resolved",
            "osm_type": "relation",
            "osm_id": 2679943,
            "lat": 35.77,
            "lon": 140.0,
            "display_name": "鎌ケ谷市, 千葉県, 日本",
            "country_code": "JP",
            "llm_model": "gvt-llm",
        }
    )
    row.update(overrides)
    return row


def _render(output_format, rows, include_candidates=False):
    handle = io.StringIO()
    writer = open_writer(output_format, handle, include_candidates=include_candidates)
    for row in rows:
        writer.write(row)
    writer.close()
    return handle.getvalue()


def test_jsonl_writes_one_object_per_line():
    text = _render(FORMAT_JSONL, [_row(), _row(input_id="seg-2")])
    lines = text.splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["input_id"] == "seg-1"
    assert json.loads(lines[1])["input_id"] == "seg-2"


def test_json_writes_a_single_array():
    text = _render(FORMAT_JSON, [_row(), _row(input_id="seg-2")])
    payload = json.loads(text)
    assert isinstance(payload, list)
    assert [item["input_id"] for item in payload] == ["seg-1", "seg-2"]
    assert payload[0]["osm_id"] == 2679943


def test_json_is_valid_when_there_are_no_rows():
    assert json.loads(_render(FORMAT_JSON, [])) == []


def test_csv_writes_header_and_fixed_columns():
    text = _render(FORMAT_CSV, [_row(), _row(input_id="seg-2", status="no_mention")])
    reader = csv.DictReader(io.StringIO(text))
    assert reader.fieldnames == list(ROW_FIELDS)
    rows = list(reader)
    assert rows[0]["display_name"] == "鎌ケ谷市, 千葉県, 日本"
    assert rows[0]["lat"] == "35.77"
    assert rows[1]["status"] == "no_mention"
    # Unset values become empty cells rather than the string "None".
    assert rows[1]["error"] == ""
    assert "\r" not in text


def test_csv_keeps_candidates_as_a_json_cell():
    row = _row()
    row["candidates"] = [{"osm_id": 1}]
    text = _render(FORMAT_CSV, [row], include_candidates=True)
    parsed = list(csv.DictReader(io.StringIO(text)))[0]
    assert json.loads(parsed["candidates"]) == [{"osm_id": 1}]


def test_geojson_writes_a_feature_collection():
    text = _render(FORMAT_GEOJSON, [_row(), _row(input_id="seg-2")])
    payload = json.loads(text)
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 2
    feature = payload["features"][0]
    assert feature["geometry"] == {"type": "Point", "coordinates": [140.0, 35.77]}
    assert feature["properties"]["input_id"] == "seg-1"
    assert "lat" not in feature["properties"]
    assert feature["id"] == "doc-1:0"


def test_geojson_keeps_rows_without_coordinates():
    text = _render(
        FORMAT_GEOJSON,
        [_row(status="no_mention", mention=None, mention_id=None, lat=None, lon=None)],
    )
    payload = json.loads(text)
    feature = payload["features"][0]
    assert feature["geometry"] is None
    assert feature["properties"]["status"] == "no_mention"
    assert "id" not in feature


def test_geojson_is_valid_when_there_are_no_rows():
    payload = json.loads(_render(FORMAT_GEOJSON, []))
    assert payload == {"type": "FeatureCollection", "features": []}


def test_streaming_formats_are_a_subset_of_the_known_formats():
    assert STREAMING_FORMATS <= set(OUTPUT_FORMATS)
    assert FORMAT_JSON not in STREAMING_FORMATS
    assert FORMAT_GEOJSON not in STREAMING_FORMATS

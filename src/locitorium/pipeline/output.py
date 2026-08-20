"""Output formats for resolved rows.

The rows produced by :mod:`locitorium.pipeline.stream` are flat records
with a fixed schema, which makes them cheap to render in more than one
shape. Only formats that are awkward to reproduce with downstream tools
are offered here:

- ``jsonl`` (default): one row per line, streams, pipe friendly.
- ``json``: a single JSON array, for ``jq`` in one pass or for tools that
  want to read the whole result as one document.
- ``csv``: the fixed column set with a header, for spreadsheets. Getting
  the header, the column order and the quoting right by hand is more work
  than it looks.
- ``geojson``: a ``FeatureCollection`` of ``Point`` features, because the
  point of resolution is coordinates and every map tool reads GeoJSON.

Every writer emits one output record per input row, including rows whose
status is not ``resolved``; nothing disappears because of the format.
``json`` and ``geojson`` are written incrementally (so memory stays flat)
but the document is only well-formed once the writer is closed.
"""

from __future__ import annotations

import csv
import json
from typing import Any, TextIO

FORMAT_JSONL = "jsonl"
FORMAT_JSON = "json"
FORMAT_CSV = "csv"
FORMAT_GEOJSON = "geojson"

OUTPUT_FORMATS = (FORMAT_JSONL, FORMAT_JSON, FORMAT_CSV, FORMAT_GEOJSON)

# Formats whose output stays valid when the run is interrupted, and which
# a reader can therefore consume line by line while it is being written.
STREAMING_FORMATS = frozenset({FORMAT_JSONL, FORMAT_CSV})

# Column order for the tabular format; mirrors stream._base_row().
ROW_FIELDS = (
    "input_id",
    "chunk_index",
    "doc_id",
    "mention_id",
    "mention",
    "status",
    "osm_type",
    "osm_id",
    "lat",
    "lon",
    "display_name",
    "country_code",
    "llm_model",
    "error",
)


class JsonlWriter:
    """One JSON object per line."""

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle

    def write(self, row: dict[str, Any]) -> None:
        self._handle.write(json.dumps(row, ensure_ascii=False))
        self._handle.write("\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.flush()


class JsonWriter:
    """A single JSON array holding every row."""

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle
        self._started = False

    def write(self, row: dict[str, Any]) -> None:
        if self._started:
            self._handle.write(",\n")
        else:
            self._handle.write("[\n")
            self._started = True
        self._handle.write("  " + json.dumps(row, ensure_ascii=False))

    def close(self) -> None:
        if self._started:
            self._handle.write("\n]\n")
        else:
            self._handle.write("[]\n")
        self._handle.flush()


class CsvWriter:
    """Comma separated values with a header row."""

    def __init__(self, handle: TextIO, include_candidates: bool = False) -> None:
        fields = list(ROW_FIELDS)
        if include_candidates:
            fields.append("candidates")
        self._include_candidates = include_candidates
        self._handle = handle
        self._writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            lineterminator="\n",
            extrasaction="ignore",
        )
        self._writer.writeheader()

    def write(self, row: dict[str, Any]) -> None:
        out = {key: row.get(key) for key in ROW_FIELDS}
        if self._include_candidates:
            out["candidates"] = json.dumps(
                row.get("candidates") or [], ensure_ascii=False
            )
        self._writer.writerow(out)
        self._handle.flush()

    def close(self) -> None:
        self._handle.flush()


class GeoJsonWriter:
    """A ``FeatureCollection`` with one feature per row.

    Rows without coordinates keep a ``null`` geometry rather than being
    dropped, so a GeoJSON run can still be compared against a JSONL one.
    """

    _HEAD = '{"type": "FeatureCollection", "features": [\n'

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle
        self._started = False

    @staticmethod
    def _feature(row: dict[str, Any]) -> dict[str, Any]:
        lat = row.get("lat")
        lon = row.get("lon")
        geometry: dict[str, Any] | None = None
        if lat is not None and lon is not None:
            geometry = {"type": "Point", "coordinates": [lon, lat]}
        properties = {
            key: value for key, value in row.items() if key not in {"lat", "lon"}
        }
        feature: dict[str, Any] = {"type": "Feature"}
        if row.get("mention_id"):
            feature["id"] = row["mention_id"]
        feature["geometry"] = geometry
        feature["properties"] = properties
        return feature

    def write(self, row: dict[str, Any]) -> None:
        if self._started:
            self._handle.write(",\n")
        else:
            self._handle.write(self._HEAD)
            self._started = True
        self._handle.write("  " + json.dumps(self._feature(row), ensure_ascii=False))

    def close(self) -> None:
        if not self._started:
            self._handle.write(self._HEAD)
        else:
            self._handle.write("\n")
        self._handle.write("]}\n")
        self._handle.flush()


def open_writer(
    output_format: str,
    handle: TextIO,
    include_candidates: bool = False,
) -> JsonlWriter | JsonWriter | CsvWriter | GeoJsonWriter:
    """Return the writer for ``output_format``."""
    if output_format == FORMAT_JSONL:
        return JsonlWriter(handle)
    if output_format == FORMAT_JSON:
        return JsonWriter(handle)
    if output_format == FORMAT_CSV:
        return CsvWriter(handle, include_candidates=include_candidates)
    if output_format == FORMAT_GEOJSON:
        return GeoJsonWriter(handle)
    raise ValueError(f"unknown output format: {output_format!r}")

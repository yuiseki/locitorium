from locitorium.models.schema import GoldDoc, PredDoc


def test_gold_schema_parses_and_normalizes_country_code():
    doc = GoldDoc.model_validate(
        {
            "doc_id": "d1",
            "text": "Text",
            "mentions": [
                {
                    "mention_id": "d1:0",
                    "mention": "Japan",
                    "iso_country": "jp",
                }
            ],
        }
    )
    assert doc.mentions[0].iso_country == "JP"


def test_pred_schema_parses_and_allows_null_country_code():
    doc = PredDoc.model_validate(
        {
            "doc_id": "d1",
            "model_info": {
                "ollama_model": "m",
                "nominatim_base_url": "https://example.com",
                "config_hash": "abc",
            },
            "results": [
                {
                    "mention_id": "d1:0",
                    "mention": "Tokyo",
                    "status": "resolved",
                    "selected": {
                        "osm_type": "relation",
                        "osm_id": 1,
                        "lat": "35.0",
                        "lon": "139.0",
                        "bbox": ["0", "1", "2", "3"],
                        "display_name": "Tokyo",
                        "country_code": None,
                        "confidence": 0.9,
                    },
                    "candidates": [],
                }
            ],
        }
    )
    assert doc.results[0].selected is not None

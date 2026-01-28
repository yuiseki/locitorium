from locitorium.eval.metrics import topk_accuracy
from locitorium.models.schema import GoldDoc, PredDoc


def test_topk_metrics_basic():
    gold = [
        GoldDoc.model_validate(
            {
                "doc_id": "d1",
                "text": "Text",
                "mentions": [
                    {
                        "mention_id": "d1:0",
                        "mention": "Japan",
                        "iso_country": "JP",
                    }
                ],
            }
        )
    ]

    preds = [
        PredDoc.model_validate(
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
                        "mention": "Japan",
                        "status": "resolved",
                        "selected": {
                            "osm_type": "relation",
                            "osm_id": 1,
                            "lat": "35",
                            "lon": "139",
                            "bbox": ["0", "1", "2", "3"],
                            "display_name": "Japan",
                            "country_code": "JP",
                            "confidence": 0.8,
                        },
                        "candidates": [
                            {
                                "rank": 1,
                                "osm_type": "relation",
                                "osm_id": 1,
                                "display_name": "Japan",
                                "lat": "35",
                                "lon": "139",
                                "bbox": ["0", "1", "2", "3"],
                                "country_code": "JP",
                                "category": None,
                                "place_rank": None,
                                "importance": None,
                            }
                        ],
                    }
                ],
            }
        )
    ]

    metrics = topk_accuracy(gold, preds, 3)
    assert metrics["top1"] == 1.0
    assert metrics["topk"] == 1.0

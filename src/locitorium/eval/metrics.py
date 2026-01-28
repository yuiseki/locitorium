from __future__ import annotations

from collections import defaultdict

from locitorium.models.schema import GoldDoc, PredDoc


def _index_predictions(preds: list[PredDoc]) -> dict[str, dict[str, dict]]:
    by_doc: dict[str, dict[str, dict]] = {}
    for doc in preds:
        by_doc[doc.doc_id] = {r.mention_id: r.model_dump() for r in doc.results}
    return by_doc


def topk_accuracy(gold: list[GoldDoc], preds: list[PredDoc], k: int) -> dict[str, float]:
    pred_index = _index_predictions(preds)

    total = 0
    top1 = 0
    topk = 0

    per_country_total = defaultdict(int)
    per_country_top1 = defaultdict(int)
    per_country_topk = defaultdict(int)

    for doc in gold:
        pred_doc = pred_index.get(doc.doc_id, {})
        for mention in doc.mentions:
            total += 1
            per_country_total[mention.iso_country] += 1

            pred = pred_doc.get(mention.mention_id)
            if not pred:
                continue

            selected = pred.get("selected")
            if pred.get("status") == "resolved" and selected:
                if selected.get("country_code") == mention.iso_country:
                    top1 += 1
                    per_country_top1[mention.iso_country] += 1

            candidates = pred.get("candidates", [])[:k]
            if any(c.get("country_code") == mention.iso_country for c in candidates):
                topk += 1
                per_country_topk[mention.iso_country] += 1

    macro_top1 = 0.0
    macro_topk = 0.0
    if per_country_total:
        macro_top1 = sum(
            per_country_top1[c] / per_country_total[c] for c in per_country_total
        ) / len(per_country_total)
        macro_topk = sum(
            per_country_topk[c] / per_country_total[c] for c in per_country_total
        ) / len(per_country_total)

    return {
        "mentions": total,
        "top1": top1 / total if total else 0.0,
        "topk": topk / total if total else 0.0,
        "macro_top1": macro_top1,
        "macro_topk": macro_topk,
    }

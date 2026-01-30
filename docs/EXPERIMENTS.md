# Experiments

## Experiment: Phase 0 model benchmark (<=10B, top-10 docs)

### Goal
- data/phase0/dataset.jsonl の先頭10件を 10B 以下の各モデルで処理し、速度と性能のバランスが良いモデルのランキングを作る。

### Scope
- Dataset: `data/phase0/dataset.jsonl` の先頭10件のみ
- Pipeline: Phase 0 の通常パイプライン（mention抽出 -> Nominatim候補 -> 候補選択）
- Models: パラメータ数 10B 以下 + `completion` 能力を持つモデル（embedding-only等は除外、gemma系はライセンス都合で除外、embed系も除外）

### Assumptions / Constraints
- Ollama/Nominatim のエンドポイントは `src/locitorium/config.py` のデフォルトを使用。
  - 変更が必要な場合は AppConfig の `ollama_base_url` / `nominatim_base_url` を調整。
- 速度計測は 10件の合計時間で評価し、1件あたり平均秒数も算出する。
- 予測は `runs/` 配下に保存し、再現性のため `runs/{run_id}` を固定する。
- Pythonの一括実行はタイムアウトしやすいため、モデルごとに手動実行する。

### Environment (Record)
- Date: 2026-01-30
- Repo: `https://github.com/yuiseki/locitorium`
- Run ID: `runs/phase0_10b_top10_20260130`
- Ollama Base URL: `src/locitorium/config.py` の既定値
- Nominatim Base URL: `src/locitorium/config.py` の既定値
- CLI: `uv run locitorium ...`

### Reproducibility Checklist
- [x] `uv sync` で依存関係を揃える
- [x] `tmp/phase0_10.jsonl` を生成（入力固定）
- [x] `runs/{run_id}/models.txt` を保存（モデル固定）
- [x] 全モデルを順番に実行し `predictions_*.jsonl` を保存
- [x] `scripts/aggregate_bench.py` で集計（結果固定）

### Preparation
1) 10件サブセットを作成
```bash
head -n 10 data/phase0/dataset.jsonl > tmp/phase0_10.jsonl
```

2) 10B以下モデルの抽出（capabilities=completion を優先、gemma系・embed系は除外）
```bash
# モデル一覧
ollama list

# 10B以下のモデル候補を抽出（parameters <= 10B かつ completion あり）
python3 - <<'PY'
import re
import subprocess

# 例: ここは `ollama list` の NAME を貼り付けてもOK
names = subprocess.check_output(['bash', '-lc', "ollama list | awk 'NR>1{print $1}'"]).decode().split()

models = []
for name in names:
    out = subprocess.check_output(['bash', '-lc', f"ollama show {name} 2>/dev/null || true"]).decode()
    if not out.strip():
        continue
    # parameters: 4.3B など
    m = re.search(r"parameters\s+(\d+(?:\.\d+)?)B", out)
    if not m:
        continue
    params = float(m.group(1))
    name_l = name.lower()
    if params <= 10 and "gemma" not in name_l and "embed" not in name_l:
        if "completion" in out:
            models.append(name)

print("\n".join(sorted(set(models))))
PY
```

3) 実験用 run_id の決定（例: `runs/phase0_10b_top10_20260130`）

### Execution
1) ベンチマーク実行（モデルごとに手動実行）
```bash
run_id=runs/phase0_10b_top10_20260130
mkdir -p "$run_id"

# models.txt に抽出結果を保存しておくと再現しやすい
# 例: pythonスクリプトの出力をリダイレクト
python3 - <<'PY' > "$run_id/models.txt"
import re
import subprocess
names = subprocess.check_output(['bash', '-lc', "ollama list | awk 'NR>1{print $1}'"]).decode().split()
models = []
for name in names:
    out = subprocess.check_output(['bash', '-lc', f"ollama show {name} 2>/dev/null || true"]).decode()
    if not out.strip():
        continue
    m = re.search(r"parameters\s+(\d+(?:\.\d+)?)B", out)
    if not m:
        continue
    params = float(m.group(1))
    name_l = name.lower()
    if params <= 10 and "completion" in out and "gemma" not in name_l and "embed" not in name_l:
        models.append(name)
print("\n".join(sorted(set(models))))
PY

# ベンチ本体（合計時間計測）
# Pythonで一括実行するとタイムアウトしやすいため、モデルごとに個別実行する。
# 例:
model=$(head -n 1 "$run_id/models.txt")
/usr/bin/time -p \
  uv run locitorium run \
  tmp/phase0_10.jsonl \
  "$run_id/predictions_$(echo "$model" | tr '/:' '__').jsonl" \
  --model "$model"

# 次のモデルは手動で model を差し替えて実行する。
```

2) 評価（Top-1/Top-5）
```bash
# 予測ファイルごとにスコア算出
for f in "$run_id"/predictions_*.jsonl; do
  echo "=== $f ==="
  uv run locitorium eval tmp/phase0_10.jsonl "$f" --k 5
done
```

3) 速度指標の算出（例: wall time / 10件）
- `/usr/bin/time -p` の `real` を採用。
- `avg_sec_per_doc = real / 10`。

4) 集計（Top-1/Top-5 + metrics平均）
```bash
uv run python scripts/aggregate_bench.py \
  --gold tmp/phase0_10.jsonl \
  --preds-dir "$run_id" \
  --models "$run_id/models.txt" \
  --k 5
```

### Ranking Method
- Accuracy: `top1` を主指標（補助として `topk`）。
- Speed: `avg_sec_per_doc`（小さいほど良い）。
- Balanced Score（例）:
  - 正規化: `norm_top1 = top1 / max_top1`, `norm_speed = min_avg_sec / avg_sec_per_doc`
  - Score = `0.7 * norm_top1 + 0.3 * norm_speed`
- 上位からランキング化。

### Output Format
- `runs/{run_id}/ranking.md` を作成し、以下の表で整理。
- `predictions_*.jsonl` の `metrics` に各文書の所要時間（total / extract / candidate / resolve）を記録する。

```text
| rank | model | params | top1 | top5 | avg_sec_per_doc | score | notes |
|------|-------|--------|------|------|-----------------|-------|-------|
| 1    | ...   | 7B     | 0.72 | 0.90 | 2.8             | 0.88  | ...   |
```

### Validation / Notes
- 10件のみなので統計的には弱い。後続で 100件版・全件版を実施する。
- Nominatim の応答速度に左右されるため、同一環境で連続実行する。
- JSON Schema 出力に失敗したモデルは `invalid_output` として記録。

## Results (2026-01-30)

Run: `runs/phase0_10b_top10_20260130`  
Ranking criteria: `top1` desc, `avg_total_s` asc, docs=10 only.  
Aggregation command:
```bash
uv run python scripts/aggregate_bench.py \
  --gold tmp/phase0_10.jsonl \
  --preds-dir runs/phase0_10b_top10_20260130 \
  --models runs/phase0_10b_top10_20260130/models.txt \
  --k 5
```
Notes:
- docs!=10 のモデルは集計から除外（途中失敗/タイムアウトの可能性）。
- gemma / embed 系はモデル抽出時点で除外。

| rank | model | top1 | top5 | avg_total_s |
| --- | --- | --- | --- | --- |
| 1 | granite3.2:8b | 1.000 | 0.900 | 3.770 |
| 2 | granite3.3:2b | 0.900 | 0.900 | 2.026 |
| 3 | granite4:1b-h | 0.900 | 0.800 | 2.120 |
| 4 | mistral:7b | 0.900 | 1.000 | 3.156 |
| 5 | ministral-3:8b | 0.900 | 0.900 | 5.456 |
| 6 | qwen3:1.7b | 0.900 | 0.900 | 15.001 |
| 7 | deepseek-r1:8b | 0.900 | 0.900 | 27.257 |
| 8 | qwen2.5vl:3b | 0.800 | 0.700 | 2.598 |
| 9 | granite3.2:2b | 0.800 | 0.800 | 2.676 |
| 10 | qwen2.5-coder:7b | 0.800 | 0.800 | 3.621 |

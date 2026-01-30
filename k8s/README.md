# k8s運用メモ (Locitorium)

前提: このリポジトリ直下で実行する。

## 起動（デプロイ）
```bash
kubectl apply -f k8s/locitorium.yaml
```

## 停止（削除）
```bash
kubectl delete -f k8s/locitorium.yaml
```

## 再起動（ローリング）
```bash
kubectl rollout restart deployment/locitorium
```

## 状態確認
```bash
kubectl rollout status deployment/locitorium
kubectl get pods -l app=locitorium -o wide
kubectl get svc locitorium
```

## ローカル疎通確認
```bash
curl -I http://127.0.0.1:8010/
```

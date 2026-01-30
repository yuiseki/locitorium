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
curl -I http://127.0.0.1:30101/
```
## containerd にローカルイメージを取り込む（sudo不要化）

`docker save | ctr images import` を sudo 無しで実行するために、containerd の gRPC ソケットを `containerd` グループに割り当てる。

```bash
# containerd グループを作成（なければ）
sudo groupadd containerd

# ユーザーを containerd グループに追加
sudo usermod -aG containerd $USER

# containerd の gRPC ソケットのグループを変更
sudo sed -i 's/^  gid = 0$/  gid = 1002/' /etc/containerd/config.toml
sudo systemctl restart containerd

# 反映確認（root:containerd になっていればOK）
ls -l /run/containerd/containerd.sock

# グループ反映（再ログインの代替）
newgrp containerd

# イメージの取り込み
 docker save locitorium-locitorium:latest | ctr -n k8s.io images import -
```

※ `gid` は `getent group containerd` の値に合わせてください。

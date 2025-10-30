# **最終実装計画：日本語特化 self-hosted Meilisearch + Docling 統合版**

> **目的**：Docker Composeで「気軽に」起動できる、日本語最適化された **Meilisearch MCP サーバー**を構築。  
> **特徴**：
> - 日本語トークナイザー（`prototype-japanese-13`）
> - **組み込み日本語UI**（`/dashboard`）
> - **Docling** で高度なPDF解析（レイアウト・テーブル・OCR）
> - JSON/PDF 自動投入
> - 1コンテナでUI完結、2コンテナで投入処理

---

## 最終アーキテクチャ

```text
┌───────────────────────┐
│     ホストファイル       │
│  ./input/json/  ←──────┤
│  ./input/pdf/   ←──────┤
│  ./data/meili/         │
│  ./logs/               │
└─────────▲─────────────┘
          │
   ┌──────┴──────┐
   │ Docker Compose │
   └──────┬──────┘
   ┌──────┴──────┐
   │ meilisearch │ ← getmeili/meilisearch:prototype-japanese-13
   │   + UI (/dashboard) ← 組み込み
   └──────┬──────┘
          │
   ┌──────┴──────┐
   │ json-ingester │ ← Watchdog + JSON → Meilisearch
   └──────┬──────┘
   ┌──────┴──────┐
   │ pdf-ingester  │ ← Watchdog + Docling → Markdown → Meilisearch
   └──────────────┘
```

---

## 機能要件 完全対応

| 機能 | 実装方法 |
|------|----------|
| 1. JSONファイル投入 | `json-ingester` が `/input/json` を監視 → 即時投入 |
| 2. PDFファイル投入 | `pdf-ingester` が `/input/pdf` を監視 → **Docling** で構造化抽出（Markdown）→ 投入 |
| 3. Index管理 | `manage_index.py` スクリプト（create / delete / list / settings） |
| 4. UIで検索 | `http://localhost:7700/dashboard`（日本語ブラウザで自動日本語化） |

---

## 最終ファイル構成

```
project/
├── docker-compose.yml
├── Dockerfile.ingester
├── requirements.txt
├── ingester.py
├── manage_index.py
├── input/
│   ├── json/        ← ここに .json ファイルを置く
│   └── pdf/         ← ここに .pdf ファイルを置く
├── data/meili/      ← Meilisearch 永続化データ（自動生成）
└── logs/            ← ログ出力（自動生成）
```

---

## 1. `docker-compose.yml`（最終版）

```yaml
version: '3.8'

services:
  meilisearch:
    image: getmeili/meilisearch:prototype-japanese-13
    container_name: meilisearch-jp
    ports:
      - "7700:7700"
    volumes:
      - ./data/meili:/meili_data
      - ./input/json:/input/json:ro
      - ./input/pdf:/input/pdf:ro
      - ./logs:/logs
    environment:
      - MEILI_MASTER_KEY=${MEILI_MASTER_KEY:-your_secure_master_key_123}
    command: >
      --experimental-enable-dashboard
      --http-addr=0.0.0.0:7700
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7700/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  json-ingester:
    build:
      context: .
      dockerfile: Dockerfile.ingester
    container_name: json-ingester
    volumes:
      - ./input/json:/input/json:ro
      - ./logs:/logs
    environment:
      - MEILISEARCH_URL=http://meilisearch:7700
      - MEILISEARCH_API_KEY=${MEILI_MASTER_KEY:-your_secure_master_key_123}
      - INDEX_NAME=documents
      - MODE=json
    depends_on:
      meilisearch:
        condition: service_healthy
    restart: unless-stopped

  pdf-ingester:
    build:
      context: .
      dockerfile: Dockerfile.ingester
    container_name: pdf-ingester
    volumes:
      - ./input/pdf:/input/pdf:ro
      - ./logs:/logs
    environment:
      - MEILISEARCH_URL=http://meilisearch:7700
      - MEILISEARCH_API_KEY=${MEILI_MASTER_KEY:-your_secure_master_key_123}
      - INDEX_NAME=documents
      - MODE=pdf
    depends_on:
      meilisearch:
        condition: service_healthy
    restart: unless-stopped
```

---

## 2. `Dockerfile.ingester`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingester.py .

CMD ["python", "ingester.py"]
```

---

## 3. `requirements.txt`

```txt
meilisearch==1.9.0
watchdog==4.0.0
docling>=2.0.0
```

---

## 4. `ingester.py`（JSON + PDF 共通）

```python
import os
import json
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from meilisearch import Client
from docling.document_converter import DocumentConverter

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/ingester.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class IngesterHandler(FileSystemEventHandler):
    def __init__(self, client, index_name, input_dir, mode):
        self.client = client
        self.index_name = index_name
        self.input_dir = Path(input_dir)
        self.mode = mode  # 'json' or 'pdf'
        self.converter = DocumentConverter() if mode == 'pdf' else None

    def on_created(self, event):
        if event.is_directory:
            return
        ext = '.json' if self.mode == 'json' else '.pdf'
        if event.src_path.lower().endswith(ext):
            time.sleep(1)  # ファイル書き込み完了待機
            self.process_file(event.src_path)

    def process_file(self, file_path):
        try:
            docs = []
            path = Path(file_path)
            if self.mode == 'pdf':
                # Docling で高度抽出（Heronモデル）
                result = self.converter.convert(file_path)
                markdown = result.document.export_to_markdown()
                doc = {
                    "id": path.stem,
                    "content": markdown,
                    "type": "pdf",
                    "source": path.name,
                    "metadata": {
                        "format": "markdown",
                        "page_count": len(result.document.pages) if hasattr(result.document, 'pages') else 0
                    }
                }
                docs.append(doc)
                logging.info(f"PDF → Markdown: {path.name} ({len(markdown)}文字)")
            else:
                # JSON 投入
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    docs = data if isinstance(data, list) else [data]

            # Meilisearch に投入
            task = self.client.index(self.index_name).add_documents(docs)
            logging.info(f"投入成功: {len(docs)}件 → index={self.index_name}, task={task['taskUid']}")
        except Exception as e:
            logging.error(f"処理失敗 {file_path}: {e}")

def main():
    url = os.getenv('MEILISEARCH_URL', 'http://localhost:7700')
    api_key = os.getenv('MEILISEARCH_API_KEY')
    index_name = os.getenv('INDEX_NAME', 'documents')
    mode = os.getenv('MODE', 'json').lower()
    input_dir = '/input/json' if mode == 'json' else '/input/pdf'

    client = Client(url, api_key)
    handler = IngesterHandler(client, index_name, input_dir, mode)

    observer = Observer()
    observer.schedule(handler, input_dir, recursive=False)
    observer.start()

    logging.info(f"{mode.upper()} Ingester 起動 → {input_dir} → index: {index_name}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    main()
```

---

## 5. `manage_index.py`（Index管理ツール）

```python
#!/usr/bin/env python3
import os
import sys
from meilisearch import Client
import argparse

def main():
    parser = argparse.ArgumentParser(description='Meilisearch Index 管理')
    sub = parser.add_subparsers(dest='cmd')

    # create
    p = sub.add_parser('create', help='インデックス作成')
    p.add_argument('name', help='インデックス名')

    # delete
    p = sub.add_parser('delete', help='インデックス削除')
    p.add_argument('name', help='インデックス名')

    # list
    sub.add_parser('list', help='インデックス一覧')

    # settings
    p = sub.add_parser('settings', help='検索可能属性設定')
    p.add_argument('name', help='インデックス名')
    p.add_argument('--searchable', nargs='+', help='例: title content')

    args = parser.parse_args()
    client = Client(os.getenv('MEILISEARCH_URL', 'http://localhost:7700'),
                    os.getenv('MEILISEARCH_API_KEY'))

    if args.cmd == 'create':
        client.create_index(args.name)
        print(f"インデックス作成: {args.name}")
    elif args.cmd == 'delete':
        client.index(args.name).delete()
        print(f"インデックス削除: {args.name}")
    elif args.cmd == 'list':
        for idx in client.get_indexes()['results']:
            print(idx['uid'])
    elif args.cmd == 'settings' and args.searchable:
        client.index(args.name).update_searchable_attributes(args.searchable)
        print(f"設定更新: {args.name} → searchable: {args.searchable}")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
```

---

## 起動手順（最終）

```bash
# 1. プロジェクトフォルダ作成
mkdir meilisearch-docling && cd meilisearch-docling

# 2. ファイル配置（上記全て）

# 3. ディレクトリ作成
mkdir -p input/json input/pdf data/meili logs

# 4. 環境変数設定（.env 推奨）
echo "MEILI_MASTER_KEY=your_strong_master_key_123456" > .env

# 5. 起動
docker compose up -d

# 6. UIアクセス
open http://localhost:7700/dashboard
# → マスターキー入力 → 日本語UI表示

# 7. ファイル投入
cp sample.pdf input/pdf/
cp data.json input/json/

# 8. ログ確認
docker compose logs -f pdf-ingester
```

---

## 動作確認ポイント

| 項目 | 確認方法 |
|------|----------|
| 日本語検索 | UIで「人工知能」と検索 → 正しくヒット |
| PDFテーブル | Doclingで抽出したMarkdownテーブルが検索対象 |
| スキャンPDF | OCR対応（Docling内蔵） |
| リアルタイム投入 | ファイル追加 → 即時ログ出力 |
| Index管理 | `python manage_index.py list` |

---

## セキュリティ・運用Tips

- `.env` で `MEILI_MASTER_KEY` 管理
- 本番では `HTTPS` + `nginx` 推奨
- 大規模PDF → `pdf-ingester` にリソース制限（`deploy.resources`）

---

## 結論：**これが最終形**

| 項目 | 採用技術 |
|------|----------|
| 検索エンジン | `getmeili/meilisearch:prototype-japanese-13` |
| UI | **組み込みダッシュボード**（日本語対応） |
| PDF抽出 | **Docling**（Heronモデル、構造保持） |
| 投入 | Watchdog + Python |
| 管理 | CLIスクリプト |
| 起動 | `docker compose up -d` |

---

**1コマンドで完結。日本語。高度PDF対応。UI付き。**

```bash
docker compose up -d && open http://localhost:7700/dashboard
```


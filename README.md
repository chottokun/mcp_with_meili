# Meilisearch MCP Server (Japanese Optimized)

Docker Composeで手軽に起動できる、日本語検索に最適化されたMeilisearch環境です。高度なPDF解析機能を持つDoclingと連携し、JSONファイルだけでなくPDFファイルの内容もシームレスに検索対象とすることができます。

## ✨ 特徴

- **日本語特化**: 日本語トークナイザーを標準搭載したMeilisearchイメージ (`getmeili/meilisearch:latest`) を採用。
- **Web UI搭載**: `/dashboard` で直感的に検索・管理ができるWeb UIを標準で有効化。
- **高度なPDF解析**: `Docling`ライブラリを使い、PDFのレイアウト、テーブル、OCR（スキャンされた文字）を認識し、構造化されたMarkdownとして抽出・投入。
- **リアルタイムファイル投入**: 指定ディレクトリにJSONやPDFファイルを置くだけで、自動的にMeilisearchにデータが投入されます。
- **シンプルな管理**: Docker Composeで全てのサービスを一括管理。インデックス操作用のPythonスクリプトも同梱。

## 🏗️ アーキテクチャ

```
.
├── input/
│   ├── json/        <-- .json ファイルをここに置く
│   └── pdf/         <-- .pdf ファイルをここに置く
│
├── docker-compose.yml (各サービスの定義)
├── ingester.py        (ファイル監視・投入スクリプト)
└── manage_index.py    (インデックス管理用CLI)
```

- **meilisearch**: 検索エンジン本体とWeb UIを提供します。
- **json-ingester**: `input/json` ディレクトリを監視し、JSONファイルをMeilisearchに投入します。
- **pdf-ingester**: `input/pdf` ディレクトリを監視し、Doclingを使ってPDFをMarkdownに変換後、Meilisearchに投入します。

## 🚀 セットアップ & 起動

### 前提条件
- Docker
- Docker Compose

### 手順

1. **リポジトリをクローン**
   ```bash
   git clone <repository_url>
   cd <repository_name>
   ```

2. **環境変数ファイルを作成**
   Meilisearchのマスターキーを設定します。`your_strong_master_key_123456` の部分は必ずユニークで安全なものに変更してください。
   ```bash
   echo "MEILI_MASTER_KEY=your_strong_master_key_123456" > .env
   ```

3. **必要なディレクトリを作成**
   ```bash
   mkdir -p input/json input/pdf logs
   ```
   ※ `data/meili` ディレクトリは初回起動時に自動で作成されます。

4. **Dockerコンテナを起動**
   ```bash
   docker compose up --build -d
   ```

## 使い方

### 1. Web UIにアクセス

ブラウザで `http://localhost:7700` を開きます。
初回アクセス時にマスターキーの入力を求められるので、`.env` ファイルで設定したキーを入力してください。

### 2. データを投入

- **JSONファイル**: `input/json/` ディレクトリに`.json`ファイルを置きます。
  - ファイルの中身は、1つのJSONオブジェクト、またはJSONオブジェクトの配列である必要があります。
- **PDFファイル**: `input/pdf/` ディレクトリに`.pdf`ファイルを置きます。

ファイルが置かれると、ingesterサービスが自動で検知し、`documents`インデックスにデータを投入します。
投入状況はログで確認できます。
```bash
# JSON投入ログの確認
docker compose logs -f json-ingester

# PDF投入ログの確認
docker compose logs -f pdf-ingester
```

### 3. インデックスの管理

付属の `manage_index.py` スクリプトを使って、インデックスの作成、削除、一覧表示、設定変更が可能です。

**例：**
```bash
# インデックスの一覧を表示
python3 manage_index.py list

# 'documents' インデックスを削除
python3 manage_index.py delete documents

# 'documents' インデックスの検索対象フィールドを設定
python3 manage_index.py settings documents --searchable content source
```

## ⚙️ 設定

設定は `docker-compose.yml` と `.env` ファイルで行います。

- `MEILI_MASTER_KEY`: (`.env`) Meilisearchのマスターキー。
- `INDEX_NAME`: (`docker-compose.yml`) データが投入されるインデックス名。
- `INPUT_DIR`: (`docker-compose.yml`) 各ingesterが監視するディレクトリ。
- `LOG_FILE_PATH`: (`docker-compose.yml`) 各ingesterのログ出力先。

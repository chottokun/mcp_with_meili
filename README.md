# Meilisearch MCP Server (Japanese Optimized)

Docker Composeで手軽に起動できる、日本語検索に最適化されたMeilisearch環境です。高度なPDF解析機能を持つDoclingと連携し、JSONファイルだけでなくPDFファイルの内容もシームレスに検索対象とすることができます。

## ✨ 特徴

- **日本語特化**: 日本語トークナイザーを標準搭載したMeilisearchイメージ (`getmeili/meilisearch:prototype-japanese-13`) を採用。
- **Web UI搭載**: 直感的に検索・管理ができるWeb UIを標準で有効化。
- **高度なPDF解析**: `Docling`ライブラリを使い、PDFのレイアウト、テーブル、OCR（スキャンされた文字）を認識し、構造化されたMarkdownとして抽出・投入。
- **リアルタイムファイル投入**: 指定ディレクトリにJSONやPDFファイルを置くだけで、自動的にMeilisearchにデータが投入されます。
- **シンプルな管理**: Docker Composeで全てのサービスを一括管理。インデックス操作用のPythonスクリプトも同梱。
- **テスト完備**: `pytest`によるユニットテストとインテグレーションテストを用意。

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
   コンテナが正常に起動したか確認します。`meilisearch-jp`が`healthy`になっていれば成功です。
   ```bash
   docker compose ps
   ```

## 使い方

### 1. データを投入する

#### サンプルJSONファイルの投入
以下のコマンドでサンプルデータを作成し、`input/json/`ディレクトリに配置します。
```bash
echo '[{"id": "doc1", "content": "これは日本語のテストです。"}, {"id": "doc2", "content": "Meilisearchは素晴らしい検索エンジンです。"}]' > input/json/sample.json
```

#### PDFファイルの投入
お手持ちのPDFファイルを`input/pdf/`ディレクトリにコピーしてください。

#### 投入状況の確認
ファイルが配置されると、各ingesterサービスが自動で検知し、`documents`インデックスにデータを投入します。
投入状況はログでリアルタイムに確認できます。
```bash
# JSON投入ログの確認
docker compose logs -f json-ingester

# PDF投入ログの確認
docker compose logs -f pdf-ingester
```

### 2. Web UIで検索する

ブラウザで `http://localhost:7700` を開きます。

初回アクセス時にマスターキーの入力を求められるので、`.env` ファイルで設定したキーを入力してください。
ダッシュボードが表示されたら、検索バーに「日本語」や「Meilisearch」と入力して、データが検索できることを確認します。

### 3. インデックスをコマンドラインで管理する

付属の `manage_index.py` スクリプトを使って、インデックスの作成、削除、一覧表示、設定変更が可能です。

**コマンド一覧:**
- `list`: インデックスの一覧を表示
- `create <index_name>`: 新しいインデックスを作成
- `delete <index_name>`: インデックスを削除
- `settings <index_name> --searchable <field1> <field2> ...`: 検索対象フィールドを設定

**実行例:**
```bash
# インデックスの一覧を表示
python3 manage_index.py list

# 'another_index' という名前で新しいインデックスを作成
python3 manage_index.py create another_index

# 'documents' インデックスの検索対象フィールドを 'content' と 'source' に設定
python3 manage_index.py settings documents --searchable content source

# 'documents' インデックスを削除
python3 manage_index.py delete documents
```

## 🧪 テストの実行

`pytest`を使用したテストが用意されています。以下のコマンドで、コンテナ内で全てのテストを実行できます。
```bash
docker compose exec json-ingester bash -c "PYTHONPATH=. pytest tests/"
```

## 🌐 外部からのアクセス

### ローカルネットワークからのアクセス
`docker-compose.yml`でポート`7700`がホストマシンに公開されているため、同じネットワーク内の他のデバイスからアクセスできます。

1.  ホストマシンのローカルIPアドレスを調べます。
    ```bash
    # Linux / macOS
    hostname -I | awk '{print $1}'
    # Windows (PowerShell)
    (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias Wi-Fi).IPAddress
    ```
2.  同じネットワーク内の他のデバイスのブラウザで `http://<ホストマシンのIPアドレス>:7700` を開きます。

**注意:** ホストマシンのファイアウォールがポート `7700` への着信接続を許可している必要があります。

### インターネット経由でのアクセス (非推奨)
ルーターのポートフォワーディング設定を行うことで、インターネットからアクセスすることも可能ですが、セキュリティリスクが非常に高いため推奨されません。
本番環境で外部公開する場合は、必ずNginxなどのリバースプロキシを前に置き、HTTPS化や認証、アクセス制限などの適切なセキュリティ対策を行ってください。

## ⚙️ 設定

主要な設定は `docker-compose.yml` と `.env` ファイルで行います。

- `MEILI_MASTER_KEY`: (`.env`) Meilisearchのマスターキー。
- `INDEX_NAME`: (`docker-compose.yml`) データが投入されるインデックス名。
- `INPUT_DIR`: (`docker-compose.yml`) 各ingesterが監視するディレクトリ。
- `LOG_FILE_PATH`: (`docker-compose.yml`) 各ingesterのログ出力先。
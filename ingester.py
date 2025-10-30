import os
import json
import time
import logging
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from meilisearch import Client
from docling.document_converter import DocumentConverter

# 環境変数からログファイルパスを取得、未設定の場合は標準出力のみ
log_file_path = os.getenv('LOG_FILE_PATH')

# ロガーの基本設定
log_format = '%(asctime)s - %(levelname)s - %(message)s'
log_level = logging.INFO
handlers = [logging.StreamHandler()]

# ログファイルパスが指定されていれば、ファイルハンドラも追加
if log_file_path:
    # ログディレクトリが存在しない場合は作成
    log_dir = os.path.dirname(log_file_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    handlers.append(logging.FileHandler(log_file_path, encoding='utf-8'))

logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=handlers
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

    # 環境変数から入力ディレクトリを取得
    input_dir = os.getenv('INPUT_DIR', '/input/json') if mode == 'json' else os.getenv('INPUT_DIR', '/input/pdf')

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

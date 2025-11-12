import os
import json
import time
import logging
from pathlib import Path
import meilisearch
from unstructured.partition.pdf import partition_pdf


def setup_logging(log_file_path):
    """ロギングを設定する"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler()
        ]
    )

def get_processed_files(processed_file_path):
    """処理済みファイルリストを取得する"""
    if not processed_file_path.exists():
        return set()
    with open(processed_file_path, 'r') as f:
        return set(line.strip() for line in f)

def add_to_processed_files(processed_file_path, filename):
    """処理済みファイルリストにファイル名を追加する"""
    with open(processed_file_path, 'a') as f:
        f.write(filename + '\n')

def process_json_file(file_path):
    """JSONファイルを処理してドキュメントリストを返す"""
    logging.info(f"Processing JSON file: {file_path.name}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def process_pdf_file(file_path):
    """PDFファイルを処理してドキュメントリストを返す"""
    logging.info(f"Processing PDF file: {file_path.name}")
    try:
        elements = partition_pdf(filename=str(file_path), strategy="hi_res")
        content = "\n\n".join([str(el) for el in elements])
        return [{
            "id": file_path.stem,
            "content": content,
            "source": file_path.name
        }]
    except Exception as e:
        logging.error(f"Failed to process PDF file {file_path.name}: {e}")
        return []

def main():
    # 環境変数から設定を読み込む
    meilisearch_url = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
    meilisearch_api_key = os.getenv("MEILISEARCH_API_KEY")
    index_name = os.getenv("INDEX_NAME", "documents")
    input_dir = Path(os.getenv("INPUT_DIR", "/input/documents"))
    log_file_path = os.getenv("LOG_FILE_PATH", "/logs/document-ingester.log")

    setup_logging(log_file_path)

    # Meilisearchクライアントの初期化
    client = meilisearch.Client(meilisearch_url, meilisearch_api_key)
    index = client.index(index_name)

    processed_file_path = input_dir / ".processed"

    while True:
        try:
            logging.info("Starting ingestion cycle...")
            processed_files = get_processed_files(processed_file_path)
            documents_to_add = []
            newly_processed_files = []

            for file_path in input_dir.glob('*'):
                if file_path.name in processed_files or file_path.name.startswith('.'):
                    continue

                documents = []
                if file_path.suffix == '.json':
                    documents = process_json_file(file_path)
                elif file_path.suffix == '.pdf':
                    documents = process_pdf_file(file_path)
                else:
                    logging.warning(f"Skipping unsupported file type: {file_path.name}")
                    continue

                if documents:
                    documents_to_add.extend(documents)
                    newly_processed_files.append(file_path.name)

            if documents_to_add:
                logging.info(f"Adding {len(documents_to_add)} documents to index '{index_name}'...")
                task = index.add_documents(documents_to_add, primary_key='id')
                client.wait_for_task(task.task_uid)
                logging.info("Documents added successfully.")

                for filename in newly_processed_files:
                    add_to_processed_files(processed_file_path, filename)
            else:
                logging.info("No new documents to ingest.")

        except Exception as e:
            logging.error(f"An error occurred during ingestion cycle: {e}")

        logging.info("Ingestion cycle finished. Waiting for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main()
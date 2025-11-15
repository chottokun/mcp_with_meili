import os
import json
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
import meilisearch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.text import partition_text
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import config

load_dotenv()

def setup_logging(log_file_path):
    """ロギングを設定する"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                        handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()])

class IngesterHandler(FileSystemEventHandler):
    def __init__(self, client, index_name, input_dir):
        self.client = client
        self.index_name = index_name
        self.index = self.client.index(index_name)
        self.input_dir = Path(input_dir)
        self.processed_file_path = self.input_dir / ".processed"

        self.model = SentenceTransformer('cl-nagoya/ruri-v3-30m')
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP
        )

        self._load_processed_files()

    def _load_processed_files(self):
        if not self.processed_file_path.exists():
            self.processed_files = set()
        else:
            with open(self.processed_file_path, 'r') as f:
                self.processed_files = set(line.strip() for line in f)

    def _add_to_processed_files(self, filename):
        with open(self.processed_file_path, 'a') as f:
            f.write(filename + '\n')
        self.processed_files.add(filename)

    def process_file(self, file_path_str):
        file_path = Path(file_path_str)
        if file_path.name in self.processed_files or file_path.name.startswith('.'):
            return

        logging.info(f"Processing file: {file_path.name}")
        documents = []
        try:
            text_to_process = ""
            if file_path.suffix == '.json':
                text_to_process = self._extract_text_from_json(file_path)
            elif file_path.suffix == '.pdf':
                text_to_process = self._extract_text_from_pdf(file_path)
            elif file_path.suffix in ['.txt', '.md']:
                text_to_process = self._extract_text_from_file(file_path)
            else:
                logging.warning(f"Skipping unsupported file type: {file_path.name}")
                return

            if text_to_process:
                documents = self._chunk_and_embed(text_to_process, file_path.name)

            if documents:
                task = self.index.add_documents(documents, primary_key='id')
                self.client.wait_for_task(task.task_uid)
                self._add_to_processed_files(file_path.name)
                logging.info(f"Successfully processed and indexed {file_path.name}")

        except Exception as e:
            logging.error(f"Failed to process {file_path.name}: {e}")

    def _extract_text_from_json(self, file_path):
        """JSONファイルから'content'キーの値をテキストとして抽出する"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # ここでは単純化のため、単一のJSONオブジェクトで'content'キーを持つことを想定
        if isinstance(data, dict) and 'content' in data:
            return data['content']
        # TODO: JSON配列やより複雑な構造に対応する場合は、ここを拡張する
        logging.warning(f"Could not extract 'content' from JSON file: {file_path.name}")
        return ""

    def _extract_text_from_pdf(self, file_path):
        elements = partition_pdf(filename=str(file_path), strategy="hi_res")
        return "\n\n".join([str(el) for el in elements])

    def _extract_text_from_file(self, file_path):
        elements = partition_text(filename=str(file_path))
        return "\n\n".join([str(el) for el in elements])

    def _chunk_and_embed(self, text, source_name):
        chunks = self.text_splitter.split_text(text)
        vectors = self.model.encode(chunks).tolist()

        documents = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            doc_id = f"{source_name}_chunk_{i:03d}"
            documents.append({
                "id": doc_id,
                "content": chunk,
                "source": source_name,
                "chunk_id": i,
                "_vectors": { "default": vector }
            })
        return documents

    def on_created(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

    def initial_scan(self):
        logging.info("Starting initial scan of the input directory...")
        for file_path in self.input_dir.glob('*'):
            self.process_file(str(file_path))
        logging.info("Initial scan finished.")

def main():
    meilisearch_url = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
    meilisearch_api_key = os.getenv("MEILI_MASTER_KEY")
    index_name = os.getenv("INDEX_NAME", "documents")
    input_dir = os.getenv("INPUT_DIR", "/input/documents")
    log_file_path = os.getenv("LOG_FILE_PATH", "/logs/document-ingester.log")

    setup_logging(log_file_path)

    client = meilisearch.Client(meilisearch_url, meilisearch_api_key)
    event_handler = IngesterHandler(client, index_name, input_dir)

    event_handler.initial_scan()

    observer = Observer()
    observer.schedule(event_handler, input_dir, recursive=False)
    observer.start()
    logging.info(f"Watching for new files in {input_dir}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()

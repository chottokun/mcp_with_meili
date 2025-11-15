import pytest
import numpy as np
from unittest.mock import MagicMock, mock_open, patch
from pathlib import Path
from ingester import IngesterHandler

TEST_INDEX_NAME = 'test_documents'
TEST_INPUT_DIR = '/test/input'

@pytest.fixture
def mock_meili_client():
    """Meilisearchクライアントのモックを返すフィクスチャ"""
    mock_client = MagicMock()
    mock_index = mock_client.index.return_value
    mock_index.add_documents.return_value = MagicMock(task_uid='123')
    return mock_client

@pytest.fixture
def handler(mock_meili_client):
    """IngesterHandlerのインスタンスを返すフィクスチャ"""
    with patch('pathlib.Path.exists', return_value=False):
        with patch('ingester.SentenceTransformer') as mock_st:
            handler_instance = IngesterHandler(mock_meili_client, TEST_INDEX_NAME, TEST_INPUT_DIR)

            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
            handler_instance.model = mock_model

            mock_splitter = MagicMock()
            mock_splitter.split_text.return_value = ["chunk1", "chunk2"]
            handler_instance.text_splitter = mock_splitter

            return handler_instance

@patch('ingester.partition_pdf')
def test_process_pdf_file_calls_chunk_and_embed(mock_partition_pdf, handler):
    """PDF処理時にチャンキングとベクトル化のメソッドが呼ばれるかテスト"""
    mock_partition_pdf.return_value = ["PDF", "Content"]
    test_file_path = Path(TEST_INPUT_DIR) / 'document.pdf'

    handler._chunk_and_embed = MagicMock(return_value=[])

    handler.process_file(str(test_file_path))

    handler._chunk_and_embed.assert_called_once_with("PDF\n\nContent", "document.pdf")

def test_process_json_file_calls_chunk_and_embed(handler):
    """JSON処理時にチャンキングとベクトル化のメソッドが呼ばれるかテスト"""
    test_file_path = Path(TEST_INPUT_DIR) / 'document.json'
    # 単一のJSONオブジェクトを想定
    json_content = '{"id": "doc1", "content": "This is a JSON content."}'

    handler._chunk_and_embed = MagicMock(return_value=[])

    with patch('builtins.open', mock_open(read_data=json_content)):
        handler.process_file(str(test_file_path))

    # JSONの'content'キーの値が渡されることを期待
    handler._chunk_and_embed.assert_called_once_with("This is a JSON content.", "document.json")


def test_chunk_and_embed_creates_correct_documents(handler):
    """チャンキングとベクトル化が正しいドキュメント構造を生成するかテスト"""
    text = "This is a long text to be chunked."
    source_name = "test.txt"

    documents = handler._chunk_and_embed(text, source_name)

    handler.text_splitter.split_text.assert_called_once_with(text)
    handler.model.encode.assert_called_once_with(["chunk1", "chunk2"])

    assert len(documents) == 2
    assert documents[0] == {
        "id": "test.txt_chunk_000",
        "content": "chunk1",
        "source": "test.txt",
        "chunk_id": 0,
        "_vectors": { "default": [0.1, 0.2, 0.3] }
    }
    assert documents[1] == {
        "id": "test.txt_chunk_001",
        "content": "chunk2",
        "source": "test.txt",
        "chunk_id": 1,
        "_vectors": { "default": [0.4, 0.5, 0.6] }
    }

def test_on_created_event_calls_process_file(handler):
    """on_createdイベントがprocess_fileを呼び出すかテスト"""
    handler.process_file = MagicMock()
    mock_event = MagicMock(is_directory=False, src_path=str(Path(TEST_INPUT_DIR) / 'new.txt'))
    handler.on_created(mock_event)
    handler.process_file.assert_called_once_with(mock_event.src_path)

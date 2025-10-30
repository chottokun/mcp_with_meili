import pytest
from unittest.mock import MagicMock, mock_open, patch
from pathlib import Path
from ingester import IngesterHandler

# テスト用の設定値
TEST_INDEX_NAME = 'test_documents'
TEST_INPUT_DIR = '/test/input'

@pytest.fixture
def mock_meili_client(mocker):
    """Meilisearchクライアントのモックを返すフィクスチャ"""
    mock_client = MagicMock()
    # index().add_documents() が辞書を返すように設定
    mock_client.index.return_value.add_documents.return_value = {'taskUid': '123'}
    return mock_client

@pytest.fixture
def mock_docling_converter(mocker):
    """Doclingコンバーターのモックを返すフィクスチャ"""
    mock_converter = MagicMock()
    # convert().document.export_to_markdown() が固定の文字列を返すように設定
    mock_converter.convert.return_value.document.export_to_markdown.return_value = "## PDF Content"
    # ページ数のモック
    type(mock_converter.convert.return_value.document).pages = mocker.PropertyMock(return_value=[1, 2])
    return mock_converter

def test_json_ingester_single_object(mock_meili_client):
    """単一のJSONオブジェクトが正しく処理されるかテスト"""
    # 1. セットアップ
    handler = IngesterHandler(mock_meili_client, TEST_INDEX_NAME, TEST_INPUT_DIR, 'json')
    test_file_path = str(Path(TEST_INPUT_DIR) / 'sample.json')
    json_content = '{"id": 1, "content": "test content"}'

    # 2. 実行
    # `open`をモックして、ファイル読み込みをシミュレート
    with patch('builtins.open', mock_open(read_data=json_content)):
        handler.process_file(test_file_path)

    # 3. 検証
    # Meilisearchクライアントのメソッドが正しい引数で呼び出されたか確認
    mock_meili_client.index.assert_called_once_with(TEST_INDEX_NAME)
    mock_meili_client.index(TEST_INDEX_NAME).add_documents.assert_called_once_with([{"id": 1, "content": "test content"}])

def test_json_ingester_array_object(mock_meili_client):
    """JSONオブジェクトの配列が正しく処理されるかテスト"""
    # 1. セットアップ
    handler = IngesterHandler(mock_meili_client, TEST_INDEX_NAME, TEST_INPUT_DIR, 'json')
    test_file_path = str(Path(TEST_INPUT_DIR) / 'samples.json')
    json_content = '[{"id": 1, "content": "test1"}, {"id": 2, "content": "test2"}]'

    # 2. 実行
    with patch('builtins.open', mock_open(read_data=json_content)):
        handler.process_file(test_file_path)

    # 3. 検証
    mock_meili_client.index.assert_called_once_with(TEST_INDEX_NAME)
    mock_meili_client.index(TEST_INDEX_NAME).add_documents.assert_called_once_with(
        [{"id": 1, "content": "test1"}, {"id": 2, "content": "test2"}]
    )

@patch('ingester.DocumentConverter')
def test_pdf_ingester(MockDoclingConverter, mock_meili_client, mock_docling_converter):
    """PDFファイルがDoclingで処理され、正しい形式で投入されるかテスト"""
    # 1. セットアップ
    # DocumentConverterのインスタンスがモックを返すように設定
    MockDoclingConverter.return_value = mock_docling_converter

    handler = IngesterHandler(mock_meili_client, TEST_INDEX_NAME, TEST_INPUT_DIR, 'pdf')
    test_file_path = str(Path(TEST_INPUT_DIR) / 'document.pdf')

    # 2. 実行
    handler.process_file(test_file_path)

    # 3. 検証
    # Doclingコンバーターが呼び出されたか確認
    mock_docling_converter.convert.assert_called_once_with(test_file_path)

    # Meilisearchクライアントに渡されたドキュメントの形式を検証
    expected_document = {
        "id": "document",
        "content": "## PDF Content",
        "type": "pdf",
        "source": "document.pdf",
        "metadata": {
            "format": "markdown",
            "page_count": 2
        }
    }
    mock_meili_client.index.assert_called_once_with(TEST_INDEX_NAME)
    mock_meili_client.index(TEST_INDEX_NAME).add_documents.assert_called_once_with([expected_document])

def test_on_created_event_fires_processing(mocker):
    """FileSystemEventHandlerのon_createdがprocess_fileを呼び出すかテスト"""
    # 1. セットアップ
    mock_client = MagicMock()
    handler = IngesterHandler(mock_client, TEST_INDEX_NAME, TEST_INPUT_DIR, 'json')
    # process_fileメソッドをスパイ（モック）する
    handler.process_file = MagicMock()

    # time.sleepをモックしてテストを高速化
    mocker.patch('time.sleep')

    # 2. 実行
    # on_createdイベントをシミュレート
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = str(Path(TEST_INPUT_DIR) / 'new_file.json')
    handler.on_created(mock_event)

    # 3. 検証
    handler.process_file.assert_called_once_with(mock_event.src_path)

import pytest
from unittest.mock import MagicMock, patch
from doc_processor import DocumentProcessor
from docling.document_converter import DocumentConverter

@pytest.fixture
def processor_no_chunking():
    """Fixture to create a DocumentProcessor instance with chunking disabled."""
    mock_converter = MagicMock(spec=DocumentConverter)
    chunking_config = {
        "enable_hierarchical_chunking": False,
        "respect_headers": False,
        "max_token_size": 256,
        "overlap_tokens": 25,
    }
    return DocumentProcessor(converter=mock_converter, chunking_config=chunking_config)

@pytest.fixture
def processor_hierarchical_chunking():
    """Fixture to create a DocumentProcessor instance with hierarchical chunking enabled."""
    mock_converter = MagicMock(spec=DocumentConverter)
    chunking_config = {
        "enable_hierarchical_chunking": True,
        "respect_headers": True,
        "max_token_size": 256,
        "overlap_tokens": 25,
    }
    return DocumentProcessor(converter=mock_converter, chunking_config=chunking_config)

def test_process_unsupported_file(processor_no_chunking):
    """Test that an unsupported file type returns None."""
    result = processor_no_chunking.process_file('test.txt')
    assert result is None

def test_process_nonexistent_file(processor_no_chunking):
    """Test that a nonexistent file returns None."""
    result = processor_no_chunking.process_file('nonexistent.pdf')
    assert result is None

@patch('pathlib.Path.exists', return_value=True)
def test_process_pdf_no_chunking(mock_exists, processor_no_chunking):
    """Test basic PDF processing without chunking returns a single document."""
    # Mock the DocumentConverter to return a dummy result
    mock_document = MagicMock()
    mock_document.export_to_markdown.return_value = "# Title\n\nSome content."
    mock_result = MagicMock()
    mock_result.document = mock_document
    processor_no_chunking.converter.convert.return_value = mock_result

    docs = processor_no_chunking.process_file('dummy.pdf')

    assert len(docs) == 1
    assert docs[0]['content'] == "# Title\n\nSome content."
    assert docs[0]['type'] == 'pdf'

@patch('pathlib.Path.exists', return_value=True)
def test_process_json(mock_exists, processor_no_chunking):
    """Test processing a simple JSON file."""
    json_data = [{"id": "doc1", "content": "content1"}, {"id": "doc2", "content": "content2"}]
    with open('test.json', 'w') as f:
        import json
        json.dump(json_data, f)

    docs = processor_no_chunking.process_file('test.json')
    assert len(docs) == 2
    assert docs[0]['id'] == 'doc1'
    assert docs[1]['id'] == 'doc2'

# New test for hierarchical chunking
@patch('pathlib.Path.exists', return_value=True)
def test_process_pdf_hierarchical_chunking(mock_exists, processor_hierarchical_chunking):
    """Test PDF processing with hierarchical chunking enabled."""
    # Mock Docling's output to simulate hierarchical structure
    mock_page1 = MagicMock()
    mock_page1.export_to_markdown.return_value = "# Section 1\nContent of section 1."
    mock_page2 = MagicMock()
    mock_page2.export_to_markdown.return_value = "## Subsection 1.1\nContent of subsection 1.1."
    mock_page3 = MagicMock()
    mock_page3.export_to_markdown.return_value = "### Sub-subsection 1.1.1\nContent of sub-subsection 1.1.1."

    mock_document = MagicMock()
    mock_document.pages = [mock_page1, mock_page2, mock_page3]
    mock_document.export_to_markdown.return_value = "# Section 1\nContent of section 1.\n## Subsection 1.1\nContent of subsection 1.1.\n### Sub-subsection 1.1.1\nContent of sub-subsection 1.1.1."

    mock_result = MagicMock()
    mock_result.document = mock_document
    processor_hierarchical_chunking.converter.convert.return_value = mock_result

    docs = processor_hierarchical_chunking.process_file('hierarchical_doc.pdf')
    assert len(docs) > 1 # Expecting multiple chunks
    assert "# Section 1" in docs[0]['content']
    assert "## Subsection 1.1" in docs[1]['content']

import pytest
import time
import os
import json
import requests
from pathlib import Path
from meilisearch import Client
from meilisearch.errors import MeilisearchApiError

# Environment variables for Meilisearch and RabbitMQ (should match docker-compose.yml)
MEILISEARCH_URL = os.getenv('MEILISEARCH_URL', 'http://localhost:7700')
MEILISEARCH_API_KEY = 'super_secret_master_key' # Use the same key as in docker-compose.yml
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')

# Define paths relative to the project root
INPUT_DIR = Path('input')
TEST_PDF_PATH = INPUT_DIR / 'test_doc.pdf'
TEST_JSON_PATH = INPUT_DIR / 'test_data.json'

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_docker_compose():
    """Starts and stops docker-compose services for integration tests."""
    # Ensure input directory exists and has correct permissions
    INPUT_DIR.mkdir(exist_ok=True)
    os.chmod(INPUT_DIR, 0o777) # Give full permissions for testing

    # Start docker-compose services
    print("\nStarting docker-compose services...")
    # Capture output to ensure no hidden errors
    result = os.system("docker compose up --build -d")
    if result != 0:
        pytest.fail(f"docker compose up failed with exit code {result}")
    time.sleep(30) # Increased sleep time

    # Wait for RabbitMQ to be healthy
    print("Waiting for RabbitMQ to be healthy...")
    for _ in range(60): # Retry for 60 seconds
        try:
            response = requests.get(f"http://{RABBITMQ_HOST}:15672/api/healthchecks/node", auth=('user', 'password'))
            if response.status_code == 200 and response.json()['status'] == 'ok':
                print("RabbitMQ is healthy.")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        pytest.fail("RabbitMQ did not become healthy in time.")

    # Wait for Meilisearch to be healthy
    print("Waiting for Meilisearch to be healthy...")
    meilisearch_client = Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)
    for i in range(60): # Retry for 60 seconds
        try:
            # Try a simpler API call first
            meilisearch_client.get_version() # Check if client can connect and get version
            print(f"Meilisearch is healthy after {i+1} seconds.")
            break
        except Exception as e:
            print(f"Meilisearch not healthy/ready yet: {e}. Retrying...")
        time.sleep(1)
    else:
        pytest.fail("Meilisearch did not become healthy in time.")

    yield

    print("\nStopping docker-compose services...")
    # os.system("docker compose down -v") # Commented out for debugging

@pytest.fixture(autouse=True)
def cleanup_input_and_meilisearch():
    """Cleans up input directory and Meilisearch index before each test."""
    # Clear input directory
    for f in INPUT_DIR.glob('*'):
        if f.is_file():
            f.unlink()

    # Clear Meilisearch index
    meilisearch_client = Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)
    try:
        # Check if the index exists before trying to delete it
        try:
            index = meilisearch_client.get_index('documents')
            index.delete()
            # Wait for the delete task to complete, if there are any tasks
            tasks_response = meilisearch_client.get_tasks()
            if tasks_response and tasks_response.results:
                # Find the task related to the index deletion
                delete_task = next((task for task in tasks_response.results if task.details and task.details.index_uid == 'documents' and task.type == 'documentDeletion'), None)
                if delete_task:
                    meilisearch_client.wait_for_task(delete_task.uid)
                    print("Meilisearch index 'documents' cleared.")
                else:
                    print("Meilisearch index 'documents' deleted, but no specific delete task found to wait for.")
            else:
                print("Meilisearch index 'documents' deleted, no tasks to wait for.")
        except MeilisearchApiError as e:
            if "index_not_found" in str(e):
                print(f"Warning: Meilisearch index 'documents' did not exist: {e}")
            else:
                raise # Re-raise other Meilisearch API errors
    except Exception as e:
        print(f"Warning: An unexpected error occurred during Meilisearch cleanup: {e}")
    time.sleep(1) # Give Meilisearch a moment


def test_pdf_ingestion_pipeline(setup_and_teardown_docker_compose, cleanup_input_and_meilisearch):
    """Tests the full PDF ingestion pipeline with hierarchical chunking."""
    # Create a dummy PDF file (simple text for now, docling will convert to markdown)
    pdf_content = "# Document Title\n\nThis is the first paragraph.\n\n## Section 1\nContent of section 1.\n\n### Subsection 1.1\nContent of subsection 1.1."
    with open(TEST_PDF_PATH, 'w') as f:
        f.write(pdf_content)
    os.chmod(TEST_PDF_PATH, 0o666) # Give full permissions for testing

    print(f"Placed dummy PDF at {TEST_PDF_PATH}. Waiting for ingestion...")
    time.sleep(20) # Increased sleep time
    meilisearch_client = Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)
    index = meilisearch_client.index('documents')

    # Wait for documents to appear in Meilisearch
    found_docs = []
    for _ in range(60): # Wait up to 60 seconds for documents to be indexed
        try:
            results = index.search('Document Title') # Search for a term in the PDF content
            if results['hits']:
                found_docs = results['hits']
                print(f"Found {len(found_docs)} documents in Meilisearch.")
                break
        except MeilisearchApiError as e:
            print(f"Meilisearch search failed: {e}. Retrying...")
        time.sleep(1)
    
    assert len(found_docs) > 1, "Expected multiple chunks to be indexed."
    assert any("# Document Title" in doc['content'] for doc in found_docs)
    assert any("## Section 1" in doc['content'] for doc in found_docs)
    assert any("### Subsection 1.1" in doc['content'] for doc in found_docs)


def test_json_ingestion_pipeline(setup_and_teardown_docker_compose, cleanup_input_and_meilisearch):
    """Tests the full JSON ingestion pipeline."""
    json_data = [
        {"id": "json_doc_1", "content": "This is the first JSON document.", "source": "test_data.json"},
        {"id": "json_doc_2", "content": "This is the second JSON document.", "source": "test_data.json"}
    ]
    with open(TEST_JSON_PATH, 'w') as f:
        json.dump(json_data, f)
    os.chmod(TEST_JSON_PATH, 0o666) # Give full permissions for testing

    print(f"Placed dummy JSON at {TEST_JSON_PATH}. Waiting for ingestion...")
    time.sleep(20) # Increased sleep time
    meilisearch_client = Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)
    index = meilisearch_client.index('documents')

    # Wait for documents to appear in Meilisearch
    found_docs = []
    for _ in range(60): # Wait up to 60 seconds for documents to be indexed
        try:
            results = index.search('first JSON document')
            if results['hits']:
                found_docs = results['hits']
                print(f"Found {len(found_docs)} documents in Meilisearch.")
                break
        except MeilisearchApiError as e:
            print(f"Meilisearch search failed: {e}. Retrying...")
        time.sleep(1)
    
    assert len(found_docs) == 2, "Expected two JSON documents to be indexed."
    assert any("json_doc_1" == doc['id'] for doc in found_docs)
    assert any("json_doc_2" == doc['id'] for doc in found_docs)
    assert all(doc['type'] == 'json' for doc in found_docs)


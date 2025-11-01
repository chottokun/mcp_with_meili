import os
import time
import json
import uuid
import requests
import pytest
from pathlib import Path

# --- Test Configuration ---
INPUT_DIR = Path("input/json")
FASTMCP_URL = "http://localhost:8000"
SEARCH_ENDPOINT = f"{FASTMCP_URL}/search/documents"
HEALTH_ENDPOINT = f"{FASTMCP_URL}/health"
AUTH_TOKEN = "super-secret-token"
MAX_WAIT_SECONDS = 30  # Max time to wait for the document to be indexed
POLL_INTERVAL = 2    # Time between search attempts

@pytest.fixture(scope="module")
def setup_services():
    """
    Fixture to wait for the services (especially FastMCP) to be ready.
    In a real CI environment, you might use a more robust tool like docker-compose-wait.
    """
    start_time = time.time()
    while time.time() - start_time < MAX_WAIT_SECONDS:
        try:
            response = requests.get(HEALTH_ENDPOINT)
            if response.status_code == 200:
                print("FastMCP service is healthy.")
                return
        except requests.ConnectionError:
            time.sleep(POLL_INTERVAL)
    pytest.fail(f"FastMCP service did not become healthy within {MAX_WAIT_SECONDS} seconds.")


def test_e2e_json_ingestion_and_search(setup_services):
    """
    Tests the full pipeline:
    1. Creates a unique JSON file in the input directory.
    2. Waits for the pipeline to process it and index it in Meilisearch.
    3. Queries the FastMCP gateway to verify the data can be retrieved.
    4. Cleans up the created file.
    """
    # 1. Prepare unique test data and file
    unique_id = str(uuid.uuid4())
    test_doc = {
        "id": unique_id,
        "content": f"This is a test document for integration test {unique_id}.",
        "author": "Pytest"
    }
    test_filepath = INPUT_DIR / f"{unique_id}.json"

    # Ensure the input directory exists
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 2. Create the test file, triggering the file-watcher
        with open(test_filepath, 'w', encoding='utf-8') as f:
            json.dump([test_doc], f)
        print(f"\\nCreated test file: {test_filepath}")

        # 3. Poll the search endpoint until the document is found
        start_time = time.time()
        document_found = False
        search_result = {}

        print(f"Polling search endpoint for ID: {unique_id}...")
        while time.time() - start_time < MAX_WAIT_SECONDS:
            try:
                headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
                payload = {"q": unique_id}

                response = requests.post(SEARCH_ENDPOINT, headers=headers, json=payload)

                if response.status_code == 200:
                    search_result = response.json()
                    if search_result.get("hits") and search_result["hits"][0]["id"] == unique_id:
                        document_found = True
                        print("Document found!")
                        break
                else:
                    print(f"Search endpoint returned status {response.status_code}: {response.text}")

            except requests.ConnectionError as e:
                print(f"Connection error while polling: {e}")

            time.sleep(POLL_INTERVAL)

        # 4. Assertions
        assert document_found, f"Document with id {unique_id} was not found after {MAX_WAIT_SECONDS}s."

        found_doc = search_result["hits"][0]
        assert found_doc["content"] == test_doc["content"]
        assert found_doc["author"] == test_doc["author"]

    finally:
        # 5. Cleanup
        if os.path.exists(test_filepath):
            os.remove(test_filepath)
            print(f"Cleaned up test file: {test_filepath}")

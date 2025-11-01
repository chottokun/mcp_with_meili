# Test Plan

This document outlines the testing strategy for the Meilisearch distributed system, following the principles of Test-Driven Development (TDD) where applicable.

## 1. Testing Levels

Our testing approach is divided into three main levels:

1.  **Unit Tests:** To verify the functionality of individual components in isolation.
2.  **Integration Tests:** To ensure that the microservices can communicate with each other and with external services like RabbitMQ and Meilisearch.
3.  **End-to-End (E2E) Tests:** To validate the complete data ingestion and query workflow from a user's perspective.

## 2. Unit Tests

Unit tests will be written using `pytest` and will focus on the business logic of each service.

-   **`doc-processor`**:
    -   Test the document processing logic for different file types (PDF, JSON).
    -   **TDD Approach for Chunking:**
        1.  Write a failing test for the hierarchical chunking logic (e.g., a test that expects a document to be split into multiple chunks based on headers).
        2.  Implement the chunking logic in `doc_processor.py` until the test passes.
        3.  Refactor and add more tests for different chunking configurations (e.g., `max_token_size`, `overlap_tokens`, `respect_headers`).
-   **`fastmcp`**:
    -   Test the authentication middleware to ensure it correctly validates and rejects tokens.
    -   Test the search endpoint to ensure it correctly forwards requests to Meilisearch and handles errors.
    -   Future tests will cover authorization, rate limiting, and logging.
-   **Other Services (`file-watcher`, `meili-ingester`)**:
    -   Unit tests will be added for any complex logic within these services, though they are primarily focused on integration.

## 3. Integration Tests

Integration tests will use `docker-compose` to spin up the necessary services and test their interactions.

-   **File Ingestion Pipeline:**
    -   A test script will:
        1.  Start the `rabbitmq`, `doc-processor`, and `meili-ingester` services.
        2.  Publish a message to the `file_events` queue in RabbitMQ.
        3.  Assert that the `doc-processor` consumes the message, processes the file, and publishes a new message to the `processed_docs` queue.
        4.  Assert that the `meili-ingester` consumes the processed document and successfully adds it to the Meilisearch index.
-   **FastMCP and Meilisearch:**
    -   A test script will:
        1.  Start the `meilisearch` and `fastmcp` services.
        2.  Send a search request to the `fastmcp` `/search` endpoint.
        3.  Assert that the request is correctly forwarded to Meilisearch and that the expected search results are returned.

## 4. End-to-End (E2E) Tests

E2E tests will simulate the full user workflow.

-   **Test Scenario:**
    1.  Use `docker-compose` to start all services.
    2.  Create a temporary test file (e.g., a PDF) and place it in the `input` directory.
    3.  The `file-watcher` service should detect the new file and trigger the ingestion pipeline.
    4.  The test will poll the `fastmcp` search endpoint until the content of the new file is searchable and the results are verified.
    5.  Clean up by removing the test file and clearing the Meilisearch index.

This E2E test will be the ultimate verification that the entire system is working as intended.

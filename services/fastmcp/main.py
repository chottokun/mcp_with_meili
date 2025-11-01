import os
import logging
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from meilisearch import Client

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Meilisearch Connection Details
MEILISEARCH_URL = os.getenv('MEILISEARCH_URL', 'http://meilisearch:7700')
MEILISEARCH_API_KEY = os.getenv('MEILISEARCH_API_KEY')

# --- Dummy Authentication ---
# In a real-world scenario, this should be a proper token validation (e.g., JWT)
# and the secret should be managed securely.
FIXED_BEARER_TOKEN = "super-secret-token"

app = FastAPI()

# Initialize Meilisearch Client
meili_client = Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Allow access to health check endpoint without authentication
    if request.url.path == "/health":
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logging.warning("Missing Authorization header.")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authorization header is missing"},
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logging.warning(f"Invalid Authorization header format: {auth_header}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid authorization header format"},
        )

    token = parts[1]
    if token != FIXED_BEARER_TOKEN:
        logging.warning("Invalid token received.")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Invalid token"},
        )

    # You could attach user info to the request state if needed
    # request.state.user = {"id": "user-123"}

    response = await call_next(request)
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint to verify service is running."""
    return {"status": "ok"}


@app.post("/search/{index_name}")
async def search_meilisearch(index_name: str, search_query: dict):
    """
    A secure gateway to Meilisearch's search endpoint.
    The request body should be a JSON object compatible with Meilisearch's search API.
    Example: {"q": "your search query", "limit": 10}
    """
    try:
        index = meili_client.index(index_name)
        search_results = index.search(search_query.get("q"), search_query)
        return search_results
    except Exception as e:
        logging.error(f"Error while searching index '{index_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

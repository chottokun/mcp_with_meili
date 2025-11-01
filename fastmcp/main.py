
import os
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from meilisearch import Client
from meilisearch.errors import MeilisearchApiError

# --- Configuration ---
MEILISEARCH_URL = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
MEILISEARCH_API_KEY = os.getenv("MEILISEARCH_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME", "documents")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
DUMMY_AUTH_TOKEN = os.getenv("DUMMY_AUTH_TOKEN", "DUMMY_SECRET_TOKEN")

# --- Meilisearch Client ---
client = Client(url=MEILISEARCH_URL, api_key=MEILISEARCH_API_KEY)

# --- FastAPI App ---
app = FastAPI(
    title="FastMCP",
    description="A secure and fast gateway for Meilisearch",
    version="0.1.0",
)

# --- Authentication Middleware ---
class UserAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not AUTH_ENABLED or request.url.path == "/health":
            response = await call_next(request)
            return response

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return Response("Authorization header is missing", status_code=401)

        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer" or token != DUMMY_AUTH_TOKEN:
                return Response("Invalid authentication credentials", status_code=401)
        except ValueError:
            return Response("Invalid authorization header format", status_code=401)

        # You could attach user info to the request state if needed
        # request.state.user_id = "dummy_user"

        response = await call_next(request)
        return response

app.add_middleware(UserAuthMiddleware)


# --- Pydantic Models ---
class SearchRequest(BaseModel):
    query: str
    index_name: str = INDEX_NAME
    # Add other Meilisearch parameters as needed, e.g., limit, offset, filter

# --- API Endpoints ---
@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

@app.post("/search")
def search(request: SearchRequest):
    """
    Forwards a search query to the Meilisearch instance.
    """
    try:
        index = client.index(request.index_name)
        search_results = index.search(request.query)
        return search_results
    except MeilisearchApiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

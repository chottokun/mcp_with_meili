import os
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import meilisearch
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

app = FastAPI()

# lru_cacheを使って、モデルとクライアントのインスタンスをキャッシュする
@lru_cache(maxsize=None)
def get_model():
    return SentenceTransformer('cl-nagoya/ruri-v3-30m')

@lru_cache(maxsize=None)
def get_meili_client():
    return meilisearch.Client(
        url=os.getenv("MEILISEARCH_URL", "http://localhost:7700"),
        api_key=os.getenv("MEILI_MASTER_KEY")
    )

class RagSearchRequest(BaseModel):
    query: str
    top_k: int = 3

class SearchResult(BaseModel):
    content: str
    source: str
    score: float

class RagSearchResponse(BaseModel):
    results: list[SearchResult]

@app.post("/rag/search", response_model=RagSearchResponse)
def rag_search(
    request: RagSearchRequest,
    model: SentenceTransformer = Depends(get_model),
    meili_client: meilisearch.Client = Depends(get_meili_client)
):
    index_name = os.getenv("INDEX_NAME", "documents")

    query_vector = model.encode(request.query).tolist()

    search_params = {
        'vector': query_vector,
        'limit': request.top_k
    }
    search_results = meili_client.index(index_name).search(request.query, search_params)

    formatted_results = [
        SearchResult(
            content=hit.get('content', ''),
            source=hit.get('source', ''),
            score=hit.get('_semanticScore', 0.0)
        )
        for hit in search_results.get('hits', [])
    ]

    return RagSearchResponse(results=formatted_results)

# fastmcp/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY ./fastmcp/requirements.txt /app/requirements.txt

# sentence-transformersのキャッシュを効率化するため、先にインストール
RUN pip install --no-cache-dir sentence-transformers

# その他の依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

COPY ./fastmcp /app

# モデルを事前にダウンロードさせる（コンテナ起動時間を短縮するため）
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('cl-nagoya/ruri-v3-30m')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

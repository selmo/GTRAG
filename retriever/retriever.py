import qdrant_client
from qdrant_client.http import models as rest
import os

# 환경변수에서 Qdrant 연결 정보 가져오기
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")

client = qdrant_client.QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def search(qvec, top_k=3, lang=None):
    flt = None
    if lang:
        flt = rest.Filter(
            must=[rest.FieldCondition(
                key="meta.lang",
                match=rest.MatchValue(value=lang)
            )]
        )
    res = client.search(
        collection_name="chunks",
        query_vector=qvec,
        limit=top_k,
        query_filter=flt,
    )
    return res
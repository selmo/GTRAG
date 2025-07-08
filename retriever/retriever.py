import qdrant_client
from qdrant_client.http import models as rest

client = qdrant_client.QdrantClient(host="qdrant", port=6333)

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

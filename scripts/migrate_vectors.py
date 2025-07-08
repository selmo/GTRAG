"""
FAISS → Qdrant 마이그레이션 스크립트
1) 기존 FAISS 인덱스 로드
2) ID & vector 추출
3) Qdrant 컬렉션 생성 후 업로드
사용:
    python scripts/migrate_vectors.py <faiss_index_path> <qdrant_host> <collection>
"""
import sys, faiss, json, qdrant_client, tqdm, numpy as np

def load_faiss(index_path: str):
    index = faiss.read_index(index_path)
    # IDMap2라면 .idmap, Flat/HNSW라면 별도 메타 필요
    vectors = index.reconstruct_n(0, index.ntotal)
    ids = list(range(index.ntotal))  # IDMap이 아닐 경우 다른 방법 필요
    return ids, vectors

def main():
    if len(sys.argv) != 4:
        print("Usage: migrate_vectors.py <faiss_index> <qdrant_host> <collection>")
        sys.exit(1)

    faiss_path, host, collection = sys.argv[1:]
    ids, vecs = load_faiss(faiss_path)
    client = qdrant_client.QdrantClient(host=host, port=6333)

    dim = vecs.shape[1]
    # ① 컬렉션 미존재시 생성
    if collection not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=collection,
            vectors_config=qdrant_client.http.models.VectorParams(
                size=dim, distance="Cosine"
            ),
        )

    # ② 업로드 (batch)
    BATCH = 1024
    for i in tqdm.tqdm(range(0, len(ids), BATCH), desc="Migrating"):
        batch_ids = ids[i : i + BATCH]
        batch_vecs = vecs[i : i + BATCH].astype(np.float32)

        client.upsert(
            collection_name=collection,
            points=[
                qdrant_client.http.models.PointStruct(
                    id=int(idx),
                    vector=vec.tolist(),
                    payload={},  # 메타 없으면 빈 dict
                )
                for idx, vec in zip(batch_ids, batch_vecs)
            ],
        )
    print("✅ Migration finished!")


if __name__ == "__main__":
    main()

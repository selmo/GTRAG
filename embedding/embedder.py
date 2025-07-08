from sentence_transformers import SentenceTransformer
import numpy as np

MODEL = SentenceTransformer("intfloat/multilingual-e5-large-instruct")

def embed_texts(texts: list[str]) -> np.ndarray:
    return MODEL.encode(
        [f"query: {t}" for t in texts],
        batch_size=32,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

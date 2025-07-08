from unstructured.partition.auto import partition
from uuid import uuid4

def parse_pdf(path: str, lang_hint="auto") -> list[dict]:
    """PDF → title‑chunk JSON"""
    elements = partition(filename=path, chunking_strategy="title")
    chunks = []
    for el in elements:
        chunks.append({
            "chunk_id": str(uuid4()),
            "content": el.text,
            "meta": {
                "title": el.metadata.text_as_html["title"],
                "source": "pdf",
                "lang": lang_hint,
            }
        })
    return chunks

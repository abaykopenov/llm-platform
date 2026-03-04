"""
Embedder — Generate embeddings via the Inference service (GPU-accelerated).
"""

from typing import List

import httpx


async def get_embeddings(
    texts: List[str],
    model: str = "bge-m3",
    inference_url: str = "http://inference:8300",
) -> List[List[float]]:
    """
    Get embeddings from the Inference service.
    POST /v1/embeddings { model, input }
    Returns list of embedding vectors.
    """
    if not texts:
        return []

    # Batch in groups of 32 to avoid payload size issues
    batch_size = 32
    all_embeddings = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            payload = {
                "model": model,
                "input": batch,
            }

            try:
                resp = await client.post(
                    f"{inference_url}/v1/embeddings",
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    batch_embeddings = [
                        item["embedding"]
                        for item in sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                    ]
                    all_embeddings.extend(batch_embeddings)
                else:
                    raise Exception(
                        f"Embedding API returned {resp.status_code}: {resp.text}"
                    )
            except httpx.ConnectError:
                raise Exception(
                    f"Cannot connect to inference service at {inference_url}. "
                    "Make sure the inference service is running."
                )

    if len(all_embeddings) != len(texts):
        raise Exception(
            f"Expected {len(texts)} embeddings, got {len(all_embeddings)}"
        )

    return all_embeddings

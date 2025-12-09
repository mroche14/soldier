"""Vector utility functions."""

import math


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Cosine similarity measures the cosine of the angle between two vectors,
    ranging from -1 (opposite) to 1 (identical).

    Args:
        vec_a: First vector
        vec_b: Second vector (must be same length as vec_a)

    Returns:
        Cosine similarity score between -1 and 1

    Raises:
        ValueError: If vectors have different lengths or are empty
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vectors must have same length: got {len(vec_a)} and {len(vec_b)}"
        )

    if len(vec_a) == 0:
        raise ValueError("Vectors cannot be empty")

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)

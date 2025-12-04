<a id="soldier.utils.vector"></a>

# soldier.utils.vector

Vector utility functions.

<a id="soldier.utils.vector.cosine_similarity"></a>

#### cosine\_similarity

```python
def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float
```

Compute cosine similarity between two vectors.

Cosine similarity measures the cosine of the angle between two vectors,
ranging from -1 (opposite) to 1 (identical).

**Arguments**:

- `vec_a` - First vector
- `vec_b` - Second vector (must be same length as vec_a)
  

**Returns**:

  Cosine similarity score between -1 and 1
  

**Raises**:

- `ValueError` - If vectors have different lengths or are empty


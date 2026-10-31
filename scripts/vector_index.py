"""Print a reviewed Atlas index definition; never modify the database."""
import argparse
import json


def definition(dimensions: int) -> dict:
    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be positive.")
    return {"fields": [
        {"type": "vector", "path": "embedding", "numDimensions": dimensions, "similarity": "cosine"},
        {"type": "filter", "path": "file_id"},
        {"type": "filter", "path": "workspace_id"},
        {"type": "filter", "path": "processing_run_id"},
    ]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dimensions", type=int, required=True, help="Use the existing embedding dimension, not a guessed value.")
    args = parser.parse_args()
    print(json.dumps(definition(args.dimensions), indent=2))

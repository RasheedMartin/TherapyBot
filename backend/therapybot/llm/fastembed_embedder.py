"""Local CPU embeddings (ONNX via FastEmbed). Text never leaves the server to be embedded."""

import os

import certifi


class FastEmbedEmbedder:
    def __init__(self, model_name: str, cache_dir: str):
        from fastembed import TextEmbedding

        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        self.model_name = model_name
        self._model = TextEmbedding(model_name, cache_dir=cache_dir)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        # query_embed applies the model's query instruction (bge uses one), embed() does not
        return next(iter(self._model.query_embed(text))).tolist()

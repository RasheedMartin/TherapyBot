"""
Test package. Tests never load the real embedding model: a deterministic bag-of-words embedder stands in,
which also makes canary words reliably retrievable in the isolation tests.
"""

from unittest import mock

from therapybot.tests.helpers import FakeEmbedder

mock.patch("therapybot.llm.get_embedder", return_value=FakeEmbedder()).start()

"""
Encryption at rest for clinical text. A leaked database dump or backup shows only ciphertext; the keys
live in the environment, not the database.

Values are stored as "enc:v1:<Fernet token>". Anything without that prefix is treated as legacy
plaintext, so existing rows keep working until a migration re-saves them encrypted.
"""

import base64
import hashlib
import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models

PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _cipher() -> MultiFernet:
    keys = list(settings.FIELD_ENCRYPTION_KEYS)
    if not keys:
        # No dedicated key yet (synthetic-data deployments): derive a stable one from SECRET_KEY
        keys = [base64.urlsafe_b64encode(hashlib.sha256(b"therapybot-field-key:" + settings.SECRET_KEY.encode()).digest())]
    return MultiFernet([Fernet(key) for key in keys])


def encrypt(plaintext: str) -> str:
    return PREFIX + _cipher().encrypt(plaintext.encode()).decode()


def decrypt(stored: str) -> str:
    if not stored.startswith(PREFIX):
        return stored  # legacy plaintext
    try:
        return _cipher().decrypt(stored[len(PREFIX):].encode()).decode()
    except InvalidToken as e:
        raise ValueError("Can't decrypt a field: wrong or missing FIELD_ENCRYPTION_KEYS") from e


class EncryptedTextField(models.TextField):
    """A TextField encrypted at rest. Can't be filtered or searched in SQL (by design)."""

    def from_db_value(self, value, expression, connection):
        return None if value is None else decrypt(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return None if value is None else encrypt(value)


class EncryptedJSONField(models.TextField):
    """JSON stored encrypted in a text column. Python values in, Python values out."""

    def from_db_value(self, value, expression, connection):
        return None if value is None else json.loads(decrypt(value))

    def to_python(self, value):
        return json.loads(decrypt(value)) if isinstance(value, str) else value

    def get_prep_value(self, value):
        return None if value is None else encrypt(json.dumps(value))

    def value_to_string(self, obj):
        return json.dumps(self.value_from_object(obj))

"""
Chiffrement/déchiffrement des secrets applicatifs.
Utilise PBKDF2 + XOR stream cipher + HMAC (standard lib only, zero deps).
"""

import hashlib
import hmac
import os
import json
import base64


_SALT_LEN = 16
_KEY_LEN = 64
_ITERATIONS = 200_000


def _derive_key(password: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password, salt, _ITERATIONS, dklen=_KEY_LEN)


def _xor_stream(data: bytes, key: bytes) -> bytes:
    extended = (key * (len(data) // len(key) + 1))[:len(data)]
    return bytes(a ^ b for a, b in zip(data, extended))


def encrypt_data(plaintext: bytes, password: str) -> bytes:
    salt = os.urandom(_SALT_LEN)
    key = _derive_key(password.encode(), salt)
    enc_key = key[:32]
    mac_key = key[32:]
    ciphertext = _xor_stream(plaintext, enc_key)
    tag = hmac.new(mac_key, salt + ciphertext, "sha256").digest()
    return base64.b64encode(salt + tag + ciphertext)


def decrypt_data(token: bytes, password: str) -> bytes:
    raw = base64.b64decode(token)
    salt = raw[:_SALT_LEN]
    tag = raw[_SALT_LEN:_SALT_LEN + 32]
    ciphertext = raw[_SALT_LEN + 32:]
    key = _derive_key(password.encode(), salt)
    enc_key = key[:32]
    mac_key = key[32:]
    expected = hmac.new(mac_key, salt + ciphertext, "sha256").digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("Integrity check failed")
    return _xor_stream(ciphertext, enc_key)


# Mot de passe de chiffrement chargé depuis l'environnement (cf. .env.example).
_APP_PASSWORD = os.environ.get("WOW_SECRETS_PASSWORD", "")


def encrypt_secrets(secrets_dict: dict) -> bytes:
    plaintext = json.dumps(secrets_dict, ensure_ascii=False).encode("utf-8")
    return encrypt_data(plaintext, _APP_PASSWORD)


def decrypt_secrets(token: bytes) -> dict:
    plaintext = decrypt_data(token, _APP_PASSWORD)
    return json.loads(plaintext.decode("utf-8"))


def load_secrets(base_dir):
    from pathlib import Path
    base = Path(base_dir)
    local_file = base / ".secrets.json"
    if local_file.exists():
        with open(local_file, "r", encoding="utf-8") as f:
            return json.load(f)
    enc_file = base / "secrets.enc"
    if enc_file.exists():
        with open(enc_file, "rb") as f:
            return decrypt_secrets(f.read())
    return {}

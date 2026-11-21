"""Hash de contraseñas con scrypt y sal aleatoria por cuenta."""

import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return "scrypt$16384$8$1$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if (algorithm, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        salt_bytes = bytes.fromhex(salt)
        expected_bytes = bytes.fromhex(expected)
        if len(salt_bytes) != 16 or len(expected_bytes) != 64:
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt_bytes,
                                n=16384, r=8, p=1)
        return hmac.compare_digest(actual, expected_bytes)
    except (TypeError, ValueError, AttributeError):
        return False

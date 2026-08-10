from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import settings


@lru_cache
def _fernet() -> Fernet:
    if not settings.encryption_key:
        raise RuntimeError("HOUSE_MANAGER_ENCRYPTION_KEY is not set")
    return Fernet(settings.encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()

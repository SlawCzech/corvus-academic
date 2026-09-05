"""Fernet-based encryption service for sensitive values such as API keys."""

from cryptography.fernet import Fernet


class SecretService:
    """Encrypts and decrypts secrets using Fernet symmetric encryption."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plain: str) -> str:
        """Encrypt a plaintext string and return a URL-safe base64 token."""
        return self._fernet.encrypt(plain.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt a Fernet token and return the original plaintext."""
        return self._fernet.decrypt(token.encode()).decode()


def get_secret_service() -> SecretService:
    """Return a SecretService initialised from the FERNET_KEY env variable."""
    from src.shared.settings import settings

    return SecretService(settings.fernet_key.encode())

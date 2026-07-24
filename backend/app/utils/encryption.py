"""
Token Encryption Utilities

Provides secure encryption/decryption for OAuth tokens stored in database.
Uses Fernet (symmetric encryption) from cryptography library.

CRITICAL SECURITY NOTES:
- Encryption key must be stored in environment variable ENCRYPTION_KEY
- Key must be 32 bytes (base64-encoded Fernet key)
- Never log encrypted tokens or decryption keys
- Tokens are encrypted at rest and only decrypted when needed for API calls
"""
import os
import base64
import logging
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Global encryption instance (lazy initialization)
_fernet_instance: Optional[Fernet] = None


def _get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable.
    
    Returns:
        bytes: Fernet encryption key (32 bytes)
    
    Raises:
        ValueError: If ENCRYPTION_KEY is not set or invalid
    """
    encryption_key_str = os.getenv("ENCRYPTION_KEY")
    
    if not encryption_key_str:
        # Generate a key from a master password if ENCRYPTION_KEY is not set
        # This is a fallback for development - production MUST set ENCRYPTION_KEY
        master_password = os.getenv("MASTER_ENCRYPTION_PASSWORD", "default-dev-password-change-in-production")
        logger.warning("⚠️  ENCRYPTION_KEY not set, using master password derivation (NOT SECURE FOR PRODUCTION)")
        
        # Derive key from password using PBKDF2
        salt = b'liquidcanvas_salt_2024'  # Fixed salt for development (change in production)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return key
    
    try:
        # ENCRYPTION_KEY should be a base64-encoded Fernet key
        key = encryption_key_str.encode()
        # Validate it's a valid Fernet key
        Fernet(key)  # This will raise ValueError if invalid
        return key
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid ENCRYPTION_KEY: {e}. "
            "ENCRYPTION_KEY must be a base64-encoded Fernet key (32 bytes). "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )


def _get_fernet() -> Fernet:
    """Get or create Fernet instance for encryption/decryption"""
    global _fernet_instance
    if _fernet_instance is None:
        key = _get_encryption_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_token(token: str) -> str:
    """
    Encrypt an OAuth token for storage in database.
    
    Args:
        token: Plain text token to encrypt
    
    Returns:
        str: Encrypted token (base64-encoded)
    
    Raises:
        ValueError: If token is empty or encryption fails
    """
    if not token or not token.strip():
        raise ValueError("Token cannot be empty")
    
    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(token.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}", exc_info=True)
        raise ValueError(f"Token encryption failed: {e}")


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an OAuth token from database.
    
    Args:
        encrypted_token: Encrypted token (base64-encoded)
    
    Returns:
        str: Decrypted plain text token
    
    Raises:
        ValueError: If decryption fails (token may be corrupted or key changed)
    """
    if not encrypted_token or not encrypted_token.strip():
        raise ValueError("Encrypted token cannot be empty")
    
    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}", exc_info=True)
        raise ValueError(
            f"Token decryption failed: {e}. "
            "This may indicate the encryption key has changed or the token is corrupted."
        )


def mask_token(token: str, visible_chars: int = 4) -> str:
    """
    Mask a token for display/logging purposes.
    
    Args:
        token: Token to mask
        visible_chars: Number of characters to show at start and end
    
    Returns:
        str: Masked token (e.g., "abcd...xyz")
    """
    if not token or len(token) <= visible_chars * 2:
        return "****"
    
    return f"{token[:visible_chars]}...{token[-visible_chars:]}"


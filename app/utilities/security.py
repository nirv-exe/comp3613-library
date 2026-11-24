import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from starlette.requests import Request

from app.config import get_settings

password_hash = PasswordHash.recommended()


def encrypt_password(password: str):
    return password_hash.hash(password)


def verify_password(plaintext_password: str, encrypted_password):
    return password_hash.verify(password=plaintext_password, hash=encrypted_password)


def create_access_token(
    data: dict,
    expires_delta: timedelta = timedelta(minutes=get_settings().jwt_access_token_expires),
):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        get_settings().secret_key,
        algorithm=get_settings().jwt_algorithm,
    )
    return encoded_jwt


def access_token_cookie_kwargs() -> dict:
    """Cookie flags that work on local http; tighten in production."""
    is_prod = get_settings().env.lower() in {"prod", "production"}
    return {
        "httponly": True,
        "samesite": "none" if is_prod else "lax",
        "secure": is_prod,
    }


def get_csrf_token(request: Request) -> str:
    """Return a session-bound token for HTML forms, creating one if needed."""
    token = request.session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token

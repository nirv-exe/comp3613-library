import secrets
from typing import Annotated

from fastapi import Depends, Form, HTTPException, Request, status


async def require_csrf_token(
    request: Request,
    csrf_token: str = Form(""),
) -> None:
    expected_token = request.session.get("csrf_token")
    if (
        not isinstance(expected_token, str)
        or not expected_token.isascii()
        or not isinstance(csrf_token, str)
        or not csrf_token.isascii()
        or not secrets.compare_digest(expected_token, csrf_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


CsrfTokenDep = Annotated[None, Depends(require_csrf_token)]

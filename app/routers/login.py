from fastapi import Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import SessionDep
from app.dependencies.csrf import CsrfTokenDep
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService
from app.utilities.flash import flash
from app.utilities.roles import dashboard_route_name
from app.utilities.security import access_token_cookie_kwargs

from . import router, templates


@router.get("/login", response_class=HTMLResponse)
async def login_view(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
    )


@router.post("/login", response_class=HTMLResponse)
async def login_action_ajax(
    db: SessionDep,
    request: Request,
    csrf: CsrfTokenDep,
    username: str = Form(),
    password: str = Form(),
):
    user_repo = UserRepository(db)
    auth_service = AuthService(user_repo)
    access_token = auth_service.authenticate_user(username, password)
    if not access_token:
        flash(request, "Incorrect username or password", "danger")
        return RedirectResponse(
            url=request.url_for("login_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user = user_repo.get_by_username(username)
    dest = dashboard_route_name(user.role) if user else "user_home_view"
    request.session.pop("csrf_token", None)
    response = RedirectResponse(
        url=request.url_for(dest),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        **access_token_cookie_kwargs(),
    )
    return response

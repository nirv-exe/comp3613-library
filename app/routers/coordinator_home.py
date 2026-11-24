from fastapi import Request
from fastapi.responses import HTMLResponse

from app.dependencies.auth import CoordinatorDep

from . import router, templates


@router.get("/coordinator", response_class=HTMLResponse, name="coordinator_home_view")
async def coordinator_home_view(request: Request, user: CoordinatorDep):
    return templates.TemplateResponse(
        request=request,
        name="coordinator.html",
        context={"user": user},
    )

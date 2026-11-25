
from fastapi import Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import CoordinatorDep
from app.dependencies.csrf import CsrfTokenDep
from app.services import bookings
from app.utilities.flash import flash

from . import router, templates


def coordinator_redirect(request: Request):
    return RedirectResponse(
        url=request.url_for("coordinator_home_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/coordinator", response_class=HTMLResponse, name="coordinator_home_view")
async def coordinator_home_view(request: Request, user: CoordinatorDep):
    booking_list = bookings.list_bookings()
    room_list = bookings.list_rooms()
    conflict_history = bookings.list_conflict_decisions()

    return templates.TemplateResponse(
        request=request,
        name="coordinator.html",
        context={
            "user": user,
            "bookings": booking_list,
            "rooms": room_list,
            "conflict_decisions": conflict_history,
        },
    )


@router.post("/coordinator/bookings/{booking_id}/approve")
async def approve_booking_action(
    request: Request,
    user: CoordinatorDep,
    csrf: CsrfTokenDep,
    booking_id: int,
):
    result = bookings.coordinator_override_accept(
        coordinator_id=user.id,
        booking_id=booking_id,
        coordinator_override=False,
    )

    if result["ok"]:
        verdict = result.get("verdict", {})
        message = f"Booking #{booking_id} approved."

        if verdict.get("reason"):
            message += f" {verdict['reason']}"

        if verdict.get("displace_ids"):
            message += (
                f" Displaced bookings: "
                f"{', '.join(map(str, verdict['displace_ids']))}."
            )

        flash(request, message)
    else:
        flash(request, result.get("error", "Approval failed."), "danger")

    return coordinator_redirect(request)


@router.post("/coordinator/bookings/{booking_id}/reject")
async def reject_booking_action(
    request: Request,
    user: CoordinatorDep,
    csrf: CsrfTokenDep,
    booking_id: int,
):
    result = bookings.coordinator_reject(
        coordinator_id=user.id,
        booking_id=booking_id,
    )

    if result["ok"]:
        flash(request, f"Booking #{booking_id} rejected.")
    else:
        flash(request, result.get("error", "Rejection failed."), "danger")

    return coordinator_redirect(request)


@router.post("/coordinator/bookings/{booking_id}/override")
async def override_booking_action(
    request: Request,
    user: CoordinatorDep,
    csrf: CsrfTokenDep,
    booking_id: int,
    override_justification: str = Form(""),
):
    justification = override_justification.strip()

    if not justification:
        flash(
            request,
            "A justification is required for an override.",
            "danger",
        )
        return coordinator_redirect(request)

    result = bookings.coordinator_override_accept(
        coordinator_id=user.id,
        booking_id=booking_id,
        override_justification=justification,
        coordinator_override=True,
    )

    if result["ok"]:
        verdict = result.get("verdict", {})
        message = f"Booking #{booking_id} approved using coordinator override."

        if verdict.get("reason"):
            message += f" {verdict['reason']}"

        if verdict.get("displace_ids"):
            message += (
                f" Displaced bookings: "
                f"{', '.join(map(str, verdict['displace_ids']))}."
            )

        flash(request, message)
    else:
        flash(
            request,
            result.get("error", "Override approval failed."),
            "danger",
        )

    return coordinator_redirect(request)


@router.post("/coordinator/bookings/{booking_id}/cancel")
async def cancel_booking_action(
    request: Request,
    user: CoordinatorDep,
    csrf: CsrfTokenDep,
    booking_id: int,
):
    result = bookings.cancel_booking(
        actor_id=user.id,
        booking_id=booking_id,
    )

    if result["ok"]:
        flash(request, f"Booking #{booking_id} cancelled successfully.")
    else:
        flash(request, result.get("error", "Cancellation failed."), "danger")

    return coordinator_redirect(request)

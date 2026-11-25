from datetime import date, datetime

from fastapi import Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import LecturerDep
from app.dependencies.csrf import CsrfTokenDep
from app.services import bookings
from app.services import rooms as room_service
from app.utilities.flash import flash

from . import router, templates


@router.get("/lecturer", response_class=HTMLResponse, name="lecturer_home_view")
async def lecturer_home_view(
    request: Request,
    user: LecturerDep,
    room_id: int | None = None,
    date_filter: str | None = None,
):
    rooms = bookings.list_rooms()
    if room_id is None and rooms:
        room_id = rooms[0]["id"]

    today = datetime.now().astimezone().date().isoformat()
    selected_date = date_filter or today
    try:
        if date.fromisoformat(selected_date).isoformat() != selected_date:
            selected_date = today
    except ValueError:
        selected_date = today

    room_names = {room["id"]: room["name"] for room in rooms}
    all_bookings = bookings.list_bookings()
    lecturer_bookings = [
        {
            "id": booking["id"],
            "course_code": booking["course_code"],
            "room_name": room_names.get(booking["room_id"], "Unknown room"),
            "preferred_date": booking["preferred_date"],
            "start_time": booking["start_time"],
            "end_time": booking["end_time"],
            "headcount": booking["headcount"],
            "status": booking["status"],
            "can_cancel": booking["status"] in {"pending", "accepted"},
            "confirmation_url": (
                request.url_for(
                    "lecturer_confirmation_view",
                    code=booking["confirmation_code"],
                )
                if booking["status"] == "accepted"
                and booking["confirmation_code"]
                else None
            ),
        }
        for booking in all_bookings
        if booking["lecturer_id"] == user.id
    ]
    lecturer_bookings.sort(
        key=lambda booking: (
            booking["preferred_date"],
            booking["start_time"],
            booking["id"],
        ),
        reverse=True,
    )

    booked_slots = [
        {
            "start_time": booking["start_time"],
            "end_time": booking["end_time"],
            "status": booking["status"],
        }
        for booking in all_bookings
        if booking["room_id"] == room_id
        and booking["preferred_date"] == selected_date
        and booking["status"] in {"accepted", "pending"}
    ]
    booked_slots.sort(key=lambda slot: slot["start_time"])

    return templates.TemplateResponse(
        request=request,
        name="lecturer.html",
        context={
            "user": user,
            "rooms": rooms,
            "selected_room_id": room_id,
            "selected_date": selected_date,
            "booked_slots": booked_slots,
            "my_bookings": lecturer_bookings,
        },
    )


@router.post("/lecturer/bookings", name="lecturer_booking_create")
async def lecturer_booking_create(
    request: Request,
    user: LecturerDep,
    csrf: CsrfTokenDep,
    room_id: str = Form(""),
    course_code: str = Form(""),
    headcount: str = Form(""),
    preferred_date: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    resources: str = Form(""),
):
    try:
        parsed_room_id = int(room_id)
        if parsed_room_id <= 0:
            raise ValueError
    except ValueError:
        flash(request, "Select a valid workshop room.", "danger")
        return RedirectResponse(
            url=request.url_for("lecturer_home_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        parsed_headcount = int(headcount)
        if parsed_headcount <= 0:
            raise ValueError
    except ValueError:
        flash(request, "Headcount must be a positive whole number.", "danger")
        return RedirectResponse(
            url=request.url_for("lecturer_home_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    result = bookings.request_booking(
        int(user.id),
        room_id=parsed_room_id,
        course_code=course_code,
        headcount=parsed_headcount,
        preferred_date=preferred_date,
        start_time=start_time,
        end_time=end_time,
        resources=resources,
    )
    if not result.get("ok"):
        flash(request, result.get("error", "Booking request failed."), "danger")
    else:
        flash(
            request,
            "Booking request submitted. It is pending coordinator review.",
            "success",
        )

    return RedirectResponse(
        url=request.url_for("lecturer_home_view").include_query_params(
            room_id=parsed_room_id,
            date_filter=preferred_date,
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/lecturer/bookings/{booking_id}/cancel",
    name="lecturer_booking_cancel",
)
async def lecturer_booking_cancel(
    booking_id: int,
    request: Request,
    user: LecturerDep,
    csrf: CsrfTokenDep,
):
    booking = next(
        (
            item
            for item in bookings.list_bookings()
            if item["id"] == booking_id and item["lecturer_id"] == user.id
        ),
        None,
    )
    if booking is None:
        raise HTTPException(status_code=404, detail="booking not found")

    if booking["status"] not in {"pending", "accepted"}:
        flash(request, "This booking can no longer be cancelled.", "danger")
        return RedirectResponse(
            url=request.url_for("lecturer_home_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    result = bookings.cancel_booking(int(user.id), booking_id)
    if not result.get("ok"):
        flash(request, result.get("error", "Booking cancellation failed."), "danger")
    else:
        flash(request, "Booking cancelled.", "success")

    return RedirectResponse(
        url=request.url_for("lecturer_home_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/lecturer/confirmations/{code}",
    response_class=HTMLResponse,
    name="lecturer_confirmation_view",
)
async def lecturer_confirmation_view(
    code: str,
    request: Request,
    user: LecturerDep,
):
    result = bookings.get_confirmation(code)
    if not result.get("ok") or result["booking"]["lecturer_id"] != user.id:
        raise HTTPException(status_code=404, detail="confirmation not found")

    booking = result["booking"]
    rooms = {room["id"]: room for room in room_service.list_rooms()}
    room = rooms.get(booking["room_id"])
    return templates.TemplateResponse(
        request=request,
        name="confirmation.html",
        context={
            "user": user,
            "booking": booking,
            "room_name": room["name"] if room else "Unknown room",
            "share_url": request.url_for(
                "lecturer_confirmation_view",
                code=booking["confirmation_code"],
            ),
        },
    )

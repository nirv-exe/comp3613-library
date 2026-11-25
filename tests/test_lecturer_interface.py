import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import get_session
from app.main import app
from app.models.booking import Booking
from app.models.room import Room
from app.models.user import User
from app.services import bookings
from app.services import rooms as room_service
from app.utilities.security import create_access_token, encrypt_password

LECTURER_ID = 1
OTHER_LECTURER_ID = 2
COORDINATOR_ID = 3
BOOKING_DATE = "2099-03-15"


@pytest.fixture
def lecturer_client(test_engine, monkeypatch):
    def override_session():
        with Session(test_engine) as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(bookings, "default_engine", test_engine)
    monkeypatch.setattr(room_service, "default_engine", test_engine)
    monkeypatch.setattr(
        bookings,
        "get_user",
        lambda user_id: {
            "id": user_id,
            "role": {
                LECTURER_ID: "lecturer",
                OTHER_LECTURER_ID: "lecturer",
                COORDINATOR_ID: "coordinator",
            }.get(user_id, ""),
        },
    )

    password = encrypt_password("test-password")
    with Session(test_engine) as session:
        session.add_all(
            [
                User(
                    id=LECTURER_ID,
                    username="lecturer",
                    email="lecturer@example.com",
                    password=password,
                    role="lecturer",
                ),
                User(
                    id=OTHER_LECTURER_ID,
                    username="other",
                    email="other@example.com",
                    password=password,
                    role="lecturer",
                ),
                User(
                    id=COORDINATOR_ID,
                    username="coordinator",
                    email="coordinator@example.com",
                    password=password,
                    role="coordinator",
                ),
            ]
        )
        first_room = Room(name="Workshop A", capacity=12)
        default_room = Room(name="Workshop B", capacity=None)
        session.add_all([first_room, default_room])
        session.commit()
        session.refresh(first_room)
        session.refresh(default_room)
        session.add_all(
            [
                Booking(
                    lecturer_id=LECTURER_ID,
                    room_id=first_room.id,
                    course_code="OWN-COMP3613",
                    headcount=10,
                    preferred_date=BOOKING_DATE,
                    start_time="09:00",
                    end_time="10:00",
                    resources="Projector",
                    status="accepted",
                    confirmation_code="CONF-OWN",
                    created_at="2099-01-01T10:00:00+00:00",
                ),
                Booking(
                    lecturer_id=OTHER_LECTURER_ID,
                    room_id=first_room.id,
                    course_code="PRIVATE-COURSE",
                    headcount=9,
                    preferred_date=BOOKING_DATE,
                    start_time="11:00",
                    end_time="12:00",
                    resources="Private resource details",
                    status="accepted",
                    confirmation_code="CONF-PRIVATE",
                    created_at="2099-01-02T10:00:00+00:00",
                ),
                Booking(
                    lecturer_id=OTHER_LECTURER_ID,
                    room_id=first_room.id,
                    course_code="PENDING-PRIVATE-COURSE",
                    headcount=8,
                    preferred_date=BOOKING_DATE,
                    start_time="12:00",
                    end_time="13:00",
                    resources="Private pending details",
                    status="pending",
                    created_at="2099-01-03T10:00:00+00:00",
                ),
                Booking(
                    lecturer_id=LECTURER_ID,
                    room_id=default_room.id,
                    course_code="REJECTED-COMP",
                    headcount=5,
                    preferred_date=BOOKING_DATE,
                    start_time="14:00",
                    end_time="15:00",
                    resources="Whiteboard",
                    status="rejected",
                    confirmation_code="CONF-REJECTED",
                    created_at="2099-01-04T10:00:00+00:00",
                ),
            ]
        )
        session.commit()

    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def _login(client: TestClient, user_id: int = LECTURER_ID) -> None:
    role = "coordinator" if user_id == COORDINATOR_ID else "lecturer"
    client.cookies.set(
        "access_token",
        create_access_token({"sub": str(user_id), "role": role}),
    )


def _csrf_token(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def test_lecturer_dashboard_requires_lecturer_role(lecturer_client):
    assert lecturer_client.get("/lecturer").status_code == 401

    _login(lecturer_client, COORDINATOR_ID)
    assert lecturer_client.get("/lecturer").status_code == 403


def test_dashboard_shows_room_capacity_and_non_private_booked_slots(lecturer_client):
    _login(lecturer_client)

    response = lecturer_client.get(
        "/lecturer",
        params={"room_id": 1, "date_filter": BOOKING_DATE},
    )

    assert response.status_code == 200
    assert "Workshop A" in response.text
    assert "Effective capacity: 12" in response.text
    assert "Workshop B" in response.text
    assert "Effective capacity: 30" in response.text
    assert "09:00" in response.text
    assert "11:00" in response.text
    assert "12:00" in response.text
    assert "Pending" in response.text
    assert "PRIVATE-COURSE" not in response.text
    assert "CONF-PRIVATE" not in response.text
    assert "Private resource details" not in response.text


def test_booking_submission_is_pending_and_capacity_errors_are_shown(
    lecturer_client,
):
    _login(lecturer_client)
    token = _csrf_token(lecturer_client.get("/lecturer"))
    form = {
        "csrf_token": token,
        "room_id": "1",
        "course_code": "COMP2605",
        "headcount": "13",
        "preferred_date": "2099-03-18",
        "start_time": "09:00",
        "end_time": "10:00",
        "resources": "Projector",
    }

    rejected = lecturer_client.post(
        "/lecturer/bookings",
        data=form,
        follow_redirects=True,
    )
    assert rejected.status_code == 200
    assert "room capacity exceeded" in rejected.text

    form["headcount"] = "10"
    accepted_request = lecturer_client.post(
        "/lecturer/bookings",
        data=form,
        follow_redirects=True,
    )

    assert accepted_request.status_code == 200
    assert "Booking request submitted. It is pending coordinator review." in accepted_request.text
    assert "COMP2605" in accepted_request.text
    assert "Pending" in accepted_request.text
    assert "CONF-OWN" in accepted_request.text
    assert accepted_request.text.count("View confirmation") == 1


def test_booking_validation_feedback_and_csrf_protection(lecturer_client):
    _login(lecturer_client)
    token = _csrf_token(lecturer_client.get("/lecturer"))
    form = {
        "csrf_token": token,
        "room_id": "1",
        "course_code": "COMP2605",
        "headcount": "0",
        "preferred_date": "2099-03-18",
        "start_time": "09:00",
        "end_time": "10:00",
        "resources": "Projector",
    }

    invalid = lecturer_client.post(
        "/lecturer/bookings",
        data=form,
        follow_redirects=True,
    )
    missing_csrf = lecturer_client.post(
        "/lecturer/bookings",
        data={key: value for key, value in form.items() if key != "csrf_token"},
    )

    assert "headcount must be a positive integer" in invalid.text
    assert missing_csrf.status_code == 403


def test_my_bookings_are_owner_filtered_and_cancellation_is_owner_checked(
    lecturer_client,
):
    _login(lecturer_client)
    dashboard = lecturer_client.get("/lecturer")
    token = _csrf_token(dashboard)

    assert "OWN-COMP3613" in dashboard.text
    assert "PRIVATE-COURSE" not in dashboard.text
    assert "CONF-PRIVATE" not in dashboard.text

    other_booking = next(
        booking
        for booking in bookings.list_bookings()
        if booking["lecturer_id"] == OTHER_LECTURER_ID
    )
    response = lecturer_client.post(
        f"/lecturer/bookings/{other_booking['id']}/cancel",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert "forbidden" in response.text


def test_successful_and_unsuccessful_cancellation(lecturer_client, test_engine):
    _login(lecturer_client)
    dashboard = lecturer_client.get("/lecturer")
    token = _csrf_token(dashboard)

    own = next(
        booking
        for booking in bookings.list_bookings()
        if booking["lecturer_id"] == LECTURER_ID
        and booking["status"] == "accepted"
    )
    response = lecturer_client.post(
        f"/lecturer/bookings/{own['id']}/cancel",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert "Booking cancelled." in response.text
    assert "Cancelled" in response.text
    with Session(test_engine) as session:
        cancelled = session.get(Booking, own["id"])
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.confirmation_code is None

    rejected_booking = next(
        booking
        for booking in bookings.list_bookings()
        if booking["lecturer_id"] == LECTURER_ID
        and booking["status"] == "rejected"
    )
    unsuccessful = lecturer_client.post(
        f"/lecturer/bookings/{rejected_booking['id']}/cancel",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert "booking cannot be cancelled" in unsuccessful.text


def test_confirmation_is_owner_only_and_requires_accepted_booking(
    lecturer_client,
):
    _login(lecturer_client)

    valid = lecturer_client.get("/lecturer/confirmations/CONF-OWN")
    other_owner = lecturer_client.get("/lecturer/confirmations/CONF-PRIVATE")
    rejected = lecturer_client.get("/lecturer/confirmations/CONF-REJECTED")

    assert valid.status_code == 200
    assert "CONF-OWN" in valid.text
    assert "OWN-COMP3613" in valid.text
    assert "Workshop A" in valid.text
    assert "2099-03-15" in valid.text
    assert "Projector" in valid.text
    assert "/lecturer/confirmations/CONF-OWN" in valid.text
    assert other_owner.status_code == 404
    assert rejected.status_code == 404


def test_cancellation_form_requires_csrf_token(lecturer_client):
    _login(lecturer_client)
    own = next(
        booking
        for booking in bookings.list_bookings()
        if booking["lecturer_id"] == LECTURER_ID
        and booking["status"] == "accepted"
    )

    response = lecturer_client.post(
        f"/lecturer/bookings/{own['id']}/cancel",
        data={},
    )

    assert response.status_code == 403

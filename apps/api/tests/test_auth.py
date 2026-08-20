"""Auth flow: register a school, log in/out, rotate refresh tokens, /me.
Also the constant-time fundamentals: duplicate email, wrong password,
and the password-reset request/confirm path."""
from itertools import count

from .conftest import active_school_id, register_school


def test_register_school_and_me(client):
    data = register_school(client)
    assert data["access_token"]
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == "admin@test.edu"
    assert len(body["memberships"]) == 1
    # The founding membership carries the global catalog permission codes.
    perms = body["memberships"][0]["permissions"]
    assert "results.view" in perms
    assert "students.create" in perms


def test_duplicate_email_rejected(client):
    register_school(client, email="dup@test.edu")
    r = client.post(
        "/api/auth/register-school",
        json={
            "school_name": "Other School",
            "school_type": "primary",
            "admin_email": "dup@test.edu",
            "admin_full_name": "Someone Else",
            "password": "Str0ng!Pass",
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


def test_login_wrong_password(client):
    register_school(client, email="login@test.edu")
    r = client.post(
        "/api/auth/login",
        json={"email": "login@test.edu", "password": "Wrong!Pass1"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "ERR_AUTH_FAILED"


def test_login_logout_flow(client):
    register_school(client, email="flow@test.edu")
    r = client.post(
        "/api/auth/login",
        json={"email": "flow@test.edu", "password": "Str0ng!Pass"},
    )
    assert r.status_code == 200
    # Logout clears cookies; subsequent /auth/me must fail.
    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_refresh_rotation(client):
    register_school(client, email="rot@test.edu")
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_missing_school_header_unauth(client):
    register_school(client)
    # A user without an X-School-Id header cannot operate in any tenant.
    r = client.get("/api/schools/me")
    assert r.status_code == 401


def test_password_reset_unknown_email_is_neutral(client):
    r = client.post("/api/auth/passwords/reset", json={"email": "nobody@test.edu"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "If that email exists" in body["message"]
    assert body["reset_token"] is None


def test_password_reset_confirms_and_revokes_sessions(client):
    register_school(client, email="reset@test.edu", password="OldPass!23")
    # Still authenticated from registration.
    assert client.get("/api/auth/me").status_code == 200

    r = client.post("/api/auth/passwords/reset", json={"email": "reset@test.edu"})
    assert r.status_code == 200, r.text
    token = r.json()["reset_token"]
    assert token

    confirm = client.post(
        "/api/auth/passwords/reset/confirm",
        json={"token": token, "new_password": "NewPass!23"},
    )
    assert confirm.status_code == 200, confirm.text

    # Refresh sessions are revoked. The short-lived access JWT can still
    # answer /me until it expires; rotation must not mint a new pair.
    assert client.post("/api/auth/refresh").status_code == 401

    # Token is single-use.
    reused = client.post(
        "/api/auth/passwords/reset/confirm",
        json={"token": token, "new_password": "Another!23"},
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "ERR_TOKEN_EXPIRED"

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "reset@test.edu", "password": "OldPass!23"},
        ).status_code
        == 401
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "reset@test.edu", "password": "NewPass!23"},
    )
    assert login.status_code == 200, login.text
    assert client.get("/api/auth/me").status_code == 200


def test_password_reset_invalid_token(client):
    r = client.post(
        "/api/auth/passwords/reset/confirm",
        json={"token": "not-a-real-token", "new_password": "NewPass!23"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "ERR_TOKEN_EXPIRED"
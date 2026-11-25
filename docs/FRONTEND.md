# Shared front-end foundation

The server-rendered UI uses FastAPI, Jinja templates, the existing FastStart JWT
cookie, and StackRoom's shared `app/static/css/app.css`. The JSON API remains
under `/api` and continues to use bearer tokens; HTML page authentication uses
the `access_token` cookie.

## Shared routes and helpers

| Purpose | Route / helper |
| --- | --- |
| Lecturer dashboard | `GET /lecturer` (`lecturer_home_view`) |
| Coordinator dashboard | `GET /coordinator` (`coordinator_home_view`) |
| Administrator dashboard | `GET /admin` (`admin_home_view`) |
| Legacy dashboard entry | `GET /app` (`user_home_view`); redirects recognized roles to their dashboard |
| Login destination | `dashboard_route_name(role)` in `app/utilities/roles.py` |
| Authenticated user | `AuthDep` in `app/dependencies/auth.py` |
| Role checks | `LecturerDep` is lecturer-only; `CoordinatorDep` permits coordinators and administrators; `AdminDep` is administrator-only |
| CSRF validation | `CsrfTokenDep` in `app/dependencies/csrf.py` |
| CSRF field | `{% include "csrf_field.html" %}` in every HTML form |

`csrf_token(request)` is registered as a Jinja global and creates a random token
stored in the signed session. Every HTML `POST` handler must declare
`csrf: CsrfTokenDep`. Tokens are rotated after a successful sign-in. Do not apply
this form dependency to `/api` JSON endpoints. The Jinja environment enables
automatic escaping for HTML, HTM, and XML templates. Preserve that default when
adding templates that render user-submitted values.

Administrators may use coordinator functionality through the coordinator
dashboard and its coordinator-authorized handlers. Keep coordinator workflows
in the coordinator router and template; do not duplicate them in the
administrator interface. Administrator-only operations must continue to use
`AdminDep`, and lecturer-only operations must continue to use `LecturerDep`.

## Extension boundaries

- Add lecturer UI to `app/routers/lecturer_home.py` and
  `app/templates/lecturer.html`.
- Add coordinator UI to `app/routers/coordinator_home.py` and
  `app/templates/coordinator.html`.
- Add administrator room UI to `app/routers/admin_home.py` and
  `app/templates/admin.html`.
- Extend `authenticated-base.html` only for navigation shared by roles.
- Keep shared visual primitives in `app/static/css/app.css`; avoid role-specific
  style blocks in templates.

All three dashboard templates extend `authenticated-base.html`. Use the
existing StackRoom CSS variables, Bootstrap `.btn` and `.form-control`
components, and `.app-table` for data tables. Use `.status-indicator` with a
modifier such as `--pending`, `--accepted`, `--rejected`, or `--cancelled` for
status labels. Use Bootstrap `.alert` with `.feedback-message` for user-facing
feedback. Keep features scoped to the role-owned router and template; do not
change booking business logic or the `/api` contract from dashboard work.

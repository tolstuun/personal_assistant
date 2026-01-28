# Decision 005: Admin Web UI for Security Digest

**Date:** 2026-01-28
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The Security Digest system needs a way to manage:
- Categories (content groupings)
- Sources (where to fetch content from)

Currently there's no UI — management would require direct database access. We need a simple admin interface that:
1. Is password protected (single admin user)
2. Provides CRUD operations for categories and sources
3. Shows an overview dashboard
4. Works without JavaScript frameworks (simple, fast, maintainable)

## Solution

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend | FastAPI | Already in use, async, fast |
| Frontend | HTMX + Tailwind CSS | No build step, minimal JS, modern UX |
| Auth | Cookie-based session | Simple, secure enough for admin |
| Templates | Jinja2 | Built into FastAPI/Starlette |

### Architecture

```
src/admin/
├── __init__.py
├── app.py              # FastAPI app mounted at /admin
├── auth.py             # Password auth middleware
├── routes/
│   ├── __init__.py
│   ├── dashboard.py    # GET /admin/
│   ├── categories.py   # CRUD /admin/categories
│   └── sources.py      # CRUD /admin/sources
├── templates/
│   ├── base.html       # Layout with Tailwind
│   ├── login.html      # Login form
│   ├── dashboard.html  # Overview page
│   ├── categories/
│   │   ├── list.html
│   │   ├── form.html   # Create/edit form
│   │   └── _row.html   # HTMX partial for table row
│   └── sources/
│       ├── list.html
│       ├── form.html
│       └── _row.html
└── static/
    └── (Tailwind via CDN)
```

### Authentication

Simple password-based auth:
1. Password stored in `config/admin.yaml`
2. Login form at `/admin/login`
3. Session cookie after successful login
4. Middleware checks cookie on all admin routes

```yaml
# config/admin.example.yaml
admin:
  password: ${ADMIN_PASSWORD:-changeme}
  session_secret: ${ADMIN_SESSION_SECRET:-change-this-secret}
  session_expiry_hours: 24
```

### Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | /admin/login | Login form |
| POST | /admin/login | Authenticate |
| GET | /admin/logout | Clear session |
| GET | /admin/ | Dashboard |
| GET | /admin/categories | List categories |
| GET | /admin/categories/new | New category form |
| POST | /admin/categories | Create category |
| GET | /admin/categories/{id}/edit | Edit form |
| PUT | /admin/categories/{id} | Update category |
| DELETE | /admin/categories/{id} | Delete category |
| GET | /admin/sources | List sources |
| GET | /admin/sources/new | New source form |
| POST | /admin/sources | Create source |
| GET | /admin/sources/{id}/edit | Edit form |
| PUT | /admin/sources/{id} | Update source |
| DELETE | /admin/sources/{id} | Delete source |

### HTMX Patterns

Using HTMX for dynamic updates without full page reloads:

```html
<!-- Delete button with confirmation -->
<button hx-delete="/admin/categories/123"
        hx-confirm="Delete this category?"
        hx-target="closest tr"
        hx-swap="outerHTML">
    Delete
</button>

<!-- Inline edit -->
<button hx-get="/admin/categories/123/edit"
        hx-target="closest tr"
        hx-swap="outerHTML">
    Edit
</button>
```

### Security Considerations

1. **Password hashing**: Store hashed password, compare with bcrypt
2. **CSRF protection**: Include token in forms
3. **Session security**: HttpOnly, Secure cookies
4. **Rate limiting**: Limit login attempts

### Integration

Mount admin app as sub-application in main.py:

```python
from src.admin.app import admin_app

app.mount("/admin", admin_app)
```

## How to Test

### Prerequisites
```bash
docker-compose up -d postgres
cp config/admin.example.yaml config/admin.yaml
# Edit config/admin.yaml with your password
```

### Run Tests
```bash
pytest tests/admin/ -v
```

### Manual Testing
```bash
python run.py
# Visit http://localhost:8000/admin/
# Login with configured password
```

## Alternatives Considered

1. **React/Vue SPA** — Overkill, adds build complexity
2. **Django Admin** — Would require adding Django as dependency
3. **Streamlit** — Good for data apps, but separate process
4. **No UI (CLI only)** — Poor UX for non-technical owner

## Decision

Implement FastAPI + HTMX + Tailwind admin UI as described. This provides:
- Simple, maintainable codebase
- Modern UX without JS framework complexity
- Consistent with existing FastAPI stack
- Easy to extend for future admin needs

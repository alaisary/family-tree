# Family Tree

A Django app for a family tree. No accounts, no login — anyone who opens the
site can browse the tree and add, edit, or delete people straight from the page.

![Demo](screenshot.gif)

## Quick start (Docker)

Requires Docker.

```sh
docker compose up --build
```

This starts Postgres + the web app, applies migrations automatically, and serves
the app at http://localhost:8000.

### Add the first person

Open http://localhost:8000/ and enter the ancestor's name (the "الجد" prompt on an
empty tree). After that, click any person to open their card and use:

- **ابن / ابنة** — add a son or daughter
- **تعديل** — edit their details (name, birth/death year, phone, photo, …)
- **تعيين الأم** — link a mother
- **حذف** — delete a leaf node (no children)

The toolbar also exports the whole tree to CSV or SVG.

## Local development (without Docker)

```sh
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
npm install && npm run build:css
python manage.py migrate
python manage.py runserver
```

Without `DATABASE_URL`, a local `db.sqlite3` is used automatically.

## Configuration

Copy `.env.example` to `.env`. Key variables:

| Variable | Notes |
|----------|-------|
| `SECRET_KEY` | required when `DEBUG=False` |
| `DEBUG` | `True` for dev, `False` for production |
| `SITE_NAME` | name shown across the UI (defaults to `شجرة العائلة`) |
| `ALLOWED_HOSTS` | comma-separated hostnames (required in production) |
| `CSRF_TRUSTED_ORIGINS` | full origins, e.g. `https://tree.example.com` |
| `DATABASE_URL` | `postgres://user:pass@host:5432/name` (falls back to sqlite) |
| `SECURE_HARDENING` | `True` only once served over HTTPS |

## Tests

```sh
python manage.py test
```

Health check: `GET /healthz/`.

## License

[MIT](LICENSE) © 2026 Khalid Alharthi

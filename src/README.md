# owncryptofolio — developer guide

User documentation lives in [`../wiki/`](../wiki/) (German, English in `wiki/en/`). Code,
comments and this guide are English. Comments cite design decisions as "ADR 0026" and the like;
those records are the maintainer's notes and not part of this repository.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI app, SQLAlchemy, Alembic migrations, pytest |
| `backend/app/bootstrap/` | First-start chain: wait for DB, create it, migrate, keys (ADR 0030) |
| `backend/app/modules/<name>/` | One folder per module, registered in `app/main.py` |
| `frontend/` | React + Vite + TypeScript, Tailwind mapped to design tokens |
| `frontend/src/styles/tokens.css` | The three styles × light/dark (ADR 0031) |
| `frontend/src/i18n/locales/` | `de.json`, `en.json` — every visible text |
| `Dockerfile` | Production image: one container, port 8080, volume `/data` |

## Development

```bash
# backend — Python 3.13 via uv
cd src/backend
cp .env.example .env          # set DATABASE_URL and TEST_DATABASE_URL
uv sync
uv run uvicorn app.main:app --reload --port 8000

# frontend — in a second shell
cd src/frontend
npm install
npm run dev                   # http://<container>:5173, proxies /api to :8000
```

On the very first start the backend creates the database if missing, migrates, writes
keys to `.data/secrets/keys.json` and logs a **setup code**. Open the UI and follow the
setup wizard.

Only one port has to be reachable from outside in development: **5173** (Vite forwards
`/api` to the backend). Alternatively `npm run build` and open the backend on 8000, which
serves `frontend/dist` itself.

## Checks

```bash
cd src/backend  && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd src/frontend && npm test && npm run lint && npm run build
```

Backend tests need `TEST_DATABASE_URL`; that database is wiped by every run.

## Translations

Every visible text goes through a key (`t('settings.appearance.title')`), never a literal.

- Add a key to **both** `de.json` and `en.json`; `npm test` fails when a key or a
  `{{placeholder}}` is missing in one language.
- Backend errors are codes (`auth.invalid_password`) translated under `errors.*`.
- New language: add `locales/<code>.json`, register it in `src/i18n/index.ts` and in the
  backend registry `general.language` (`app/modules/settings/registry.py`).

## Styles

Components use only token utilities (`bg-surface`, `text-muted`, `rounded-card`, …).
A new style is one more `[data-style='…']` block per mode in `tokens.css` plus its key in
the settings registry and the locale files — no component changes.

## Container

```bash
# from the repository root (the licences go into the image)
docker build -f src/Dockerfile -t owncryptofolio --build-arg APP_VERSION=$(git describe --tags --always) .
docker run -p 8080:8080 -v ./data:/data \
  -e DATABASE_URL=postgresql+psycopg://user:pass@host:5432/owncryptofolio owncryptofolio
```

Only `DATABASE_URL` is required. The container listens on **8080** (not root, so no
port 80/443); map it to any host port. HTTPS belongs in a reverse proxy in front of it —
session cookies honour `X-Forwarded-Proto`.

## Releases

GitHub Actions run the checks above and a trial image build on every push and pull request
(`.github/workflows/ci.yml`). A tag `v1.2.3.4` builds the image for amd64 and arm64, pushes it
to `ghcr.io/vanixxx/owncryptofolio` (`:1.2.3.4` and `:latest`) and opens a release with that
version's changelog section (`release.yml`). Dependabot proposes updates monthly.

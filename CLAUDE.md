# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Internal tool for running a print-on-demand t-shirt shop through Printify +
Shopify: upload artwork, pick a Printify blueprint (product) and print
provider, choose which variants (sizes/colors) to sell and position the
artwork on the print area, then create a **draft** product on Printify —
nothing is published or sold until a human reviews it in Printify and pushes
it to Shopify themselves.

- **Backend**: FastAPI + SQLAlchemy + SQLite, `backend/`
- **Frontend**: React + Vite, built to static files and served by Nginx, `frontend/`
- **Printify API**: the [Catalog](https://developers.printify.com/#catalog) and
  [Products](https://developers.printify.com/#products) REST endpoints, called
  from `backend/app/services/printify_client.py`

SQLite was chosen so there's nothing extra to install; models are written so
switching to Postgres later is just a `DATABASE_URL` change (see `Settings`
in `backend/app/config.py`).

This app is deployed and running live (systemd unit `adhd-designs`, gunicorn
behind Nginx per `DEPLOY.md`) — changes to `backend/` require restarting that
service (`sudo systemctl restart adhd-designs`) to take effect, and changes
to `frontend/` require `npm run build` to regenerate `frontend/dist/` (no
restart needed, Nginx serves it directly as static files).

## Commands

Backend (from `backend/`, venv already created at `backend/.venv`):

```bash
.venv/bin/uvicorn app.main:app --reload      # dev server, http://127.0.0.1:8000
.venv/bin/pip install -r requirements.txt    # after pulling dependency changes
```

There is no test suite or linter configured for the backend yet.

Frontend (from `frontend/`):

```bash
npm run dev      # Vite dev server on :5173, proxies /api and /uploads to :8000 (see vite.config.js)
npm run build    # production build -> frontend/dist/, what Nginx serves
npm run lint      # Oxlint, config in .oxlintrc.json
```

Sanity check after a backend change:

```bash
curl http://127.0.0.1:8000/api/health   # -> {"status":"ok"}
```

First-run / after any backend restart with an empty DB, the catalog must be
synced before blueprints show up in the UI:

```bash
curl -X POST http://127.0.0.1:8000/api/catalog/sync
```

## Architecture

### The shirt-creation pipeline (why the routers are shaped this way)

1. `POST /api/designs/upload` (`routers/designs.py`) stores the raw artwork
   file on disk under `UPLOAD_DIR` with a UUID filename, reads its pixel
   dimensions with Pillow, and records a `Design` row. The DB never stores
   image bytes, only the path.
2. `POST /api/catalog/sync` (`routers/catalog.py`) pulls the **full**
   blueprint list from Printify into the `blueprints` table. Print providers
   and variant catalogs are deliberately **not** synced up front — there are
   thousands of blueprint × provider combinations — and are instead synced
   lazily, per-blueprint and per-provider, the first time a user browses to
   them (`GET .../print-providers`, `GET .../variants`), caching as they go.
3. `POST /api/products` (`routers/products.py`) is where the actual
   Printify product gets created. For each print-area placement it:
   - re-fetches the live variant catalog (not the cached copy) to get exact
     per-variant print-area pixel dimensions,
   - composites the artwork onto a transparent canvas exactly matching
     that print area's pixel size via `compose_print_area`
     (`services/image_processing.py`), applying the user's position/scale/
     rotation **itself in Pillow**,
   - uploads the composited PNG to Printify (`POST /uploads/images.json`),
   - and always tells Printify to place that upload at `x=0.5, y=0.5,
     scale=1, angle=0` — full-bleed, no further transform — because the
     transform is already baked into the pixels. This sidesteps needing to
     reverse-engineer exactly how Printify's own `scale` field relates an
     uploaded image's native resolution to the print area (it's not simply
     "1.0 = fills the print area" when the source image isn't pre-sized).
     If you need to change how placement is expressed, change it in
     `compose_print_area` and keep the four values sent to Printify fixed —
     in particular keep `angle` a Python `int`. Printify's product-create
     endpoint rejects a float `angle` with `8150 Validation failed:
     ...angle must be an integer` (confirmed live: every draft created
     before the placement rework failed with exactly this, since the old
     code forwarded `placement.angle`, a Pydantic float defaulting to
     `0.0`). `x`/`y`/`scale` accept floats fine.
   - On failure, a `Product` row with `status="failed"` and the Printify
     error body is still written, so failed attempts are visible via
     `GET /api/products`.

### Raw-JSON caching pattern

`Blueprint`, `PrintProvider`, and `VariantCatalog` (`models.py`) each store
the *entire* raw Printify API response in a `raw: JSON` column, not just the
fields the app currently uses. `services/catalog_parser.py` is the only
place that reads specific fields out of that raw JSON (`blueprint_summary`,
`print_provider_summary`, `variant_catalog_summary`, `placeholders_for_variant`).
This split exists specifically so that if Printify changes a field name,
the fix is contained to `catalog_parser.py` and doesn't require a re-sync —
the raw payloads already on disk are still there to re-parse against.
`variant_catalog_summary` also collapses print areas across variants by
picking the *largest* instance of each `position`, since different
sizes of the same blueprint can have differently-sized print areas.

### Placement data flow (frontend ↔ backend)

`Placement` (`schemas.py`) is `{position, x, y, scale, angle}` where `x`/`y`
are 0..1 fractions of the print area (0.5/0.5 = centered) and `scale` is
relative to "artwork scaled to fit entirely inside the print area at its own
aspect ratio" (so `scale=1` reproduces the original always-centered/fit
default). `frontend/src/PlacementEditor.jsx` is a from-scratch drag/rotate/
scale editor (pointer events + CSS, no canvas library) that mirrors this
exact math client-side for a WYSIWYG preview: it computes the same
`baseFit = min(areaWidth/designWidth, areaHeight/designHeight)` the backend
does, so what's dragged in the browser matches what `compose_print_area`
renders server-side. Currently only a single placement (one print position)
is supported end-to-end; `ProductCreateRequest.placements` accepts a list,
so multi-position editing is additive, not a breaking change, if it's
needed later.

### Settings / environment

`backend/app/config.py`'s `Settings` reads `backend/.env` (see
`.env.example`). `DATABASE_URL` and `UPLOAD_DIR` **must be absolute paths**
once running under systemd — the working directory is not what you'd expect
otherwise (see `DEPLOY.md`).

## Known gaps

- `catalog_parser.py` reads Printify's `placeholders[].width` / `.height`
  field names as documented; worth checking the raw response of a real
  `/api/catalog/sync` + variant fetch against what's expected if blueprints
  ever come back with no usable print areas — that would mean Printify
  changed the shape silently.
- No automated tests for either side yet.

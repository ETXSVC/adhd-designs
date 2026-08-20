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

### Browsing the catalog: pagination and categories

`GET /api/catalog/blueprints` takes `limit`/`offset`/`q`/`category` and
defaults to `limit=50` — the frontend must paginate (`App.jsx`'s "Load
more" button, tracking `blueprintsHasMore`/offset via `blueprints.length`)
rather than assuming one call returns the whole catalog. This was a real
bug once already: the frontend called the endpoint with no limit/offset at
all, so browsing silently showed only the first 50 of ~2060 blueprints even
though `/api/catalog/sync` had correctly pulled all of them into SQLite.
If blueprints ever seem to be "missing" again, check the frontend's
pagination first, not the sync.

Printify's `/catalog/blueprints.json` has no category/taxonomy field —
`category` on `Blueprint` (and the `GET /api/catalog/categories` endpoint
used for the filter pills in `App.jsx`) is a heuristic derived purely from
matching keywords against each blueprint's title, in `guess_category` /
`CATEGORY_RULES` (`services/catalog_parser.py`). Rule order matters (more
specific categories must be checked before broader ones that would
false-positive on a substring, e.g. "Hoodies & Sweatshirts" before
"T-Shirts & Tops" since "sweatshirt" contains "shirt"). It's tuned against
the live catalog (~2060 blueprints) to keep the "Other" bucket under ~20%,
not to be exhaustive — expect a long tail of niche products to land in
"Other", and improve `CATEGORY_RULES` incrementally if a category you care
about is under-represented, rather than trying to cover everything at
once. `category` is computed in `blueprint_summary` and written on every
`POST /api/catalog/sync`, so **re-run sync once after deploying a
`CATEGORY_RULES` change** to backfill it onto already-synced rows — there's
no separate backfill script.

### Schema changes without Alembic

There's no migration framework here (SQLite, intentionally small app).
`Base.metadata.create_all()` in `main.py` only creates tables that don't
exist yet — it silently does nothing for a new column on an existing
table. `database.run_light_migrations()`, also called from `main.py` right
after `create_all`, is the pattern for that instead: inspect the table,
and if a column is missing, run a guarded `ALTER TABLE ... ADD COLUMN`.
It's idempotent (checks column presence before altering) so it's safe to
run on every startup. Follow this same pattern for the next schema change
rather than reaching for Alembic. New columns go in the `_LIGHT_MIGRATIONS`
list in `database.py` — append, never edit a row that's already shipped.

### AI-generated title/description/tags

`services/ai_metadata.py` calls the Anthropic API (Claude Haiku 4.5 by
default — `ANTHROPIC_MODEL` in `.env`, deliberately the cheap tier since
this is a short vision + structured-output call, not a task that needs a
frontier model) with the design image and `output_format=GeneratedMetadata`
(a Pydantic model) via `client.messages.parse(...)`, so the response is
guaranteed-parsed `{title, description, tags}` — no manual JSON parsing.
Two entry points, both in that file:

- `generate_design_metadata` — describes the artwork alone. Wired to
  `POST /api/designs/{id}/ai-metadata`, which **persists** the result onto
  `Design.ai_title`/`ai_description`/`ai_tags`. The frontend renders this
  as editable fields (not read-only text) with a "Save changes" button that
  calls `PATCH /api/designs/{id}` (`DesignMetadataUpdate` schema, always
  writes the full `{ai_title, ai_description, ai_tags}` set — no
  partial-patch semantics) — generated copy is a starting point, not a
  final answer, and needs to be correctable before anything downstream
  relies on it.
- `generate_product_metadata` — takes a blueprint title too (looked up from
  the cached `Blueprint` row, so `/api/catalog/sync` must have run first)
  and writes e-commerce-listing-flavored copy. Wired to
  `POST /api/products/ai-metadata`, which is **not persisted** — it just
  returns suggested title/description/tags for the frontend to prefill
  into the create-product form (`App.jsx`'s "Generate title, description &
  tags with AI" button in the variants-and-price step), and the user edits
  before submitting.

**Printify's product create/update API does not accept a `tags` field** —
confirmed against the OpenAPI spec: `tags` only appears in the *response*
schema (read-only/catalog-derived), not `createProductRequest` or
`updateProductRequest`. `ProductCreateRequest.tags` and `Product.ai_tags`
exist purely so generated tags are saved in our own DB for the user's
reference (e.g. to copy into Shopify by hand later, since Shopify does
support product tags) — they are never sent to Printify. `title` and
`description` *are* genuinely accepted by Printify's create endpoint and do
get forwarded in `create_product` (`routers/products.py`).

Missing `ANTHROPIC_API_KEY` raises `RuntimeError` inside `ai_metadata.py`,
which both routers turn into a 400 (not a 500) — the rest of the app works
fine without this key set; it's an optional feature, not a hard dependency.

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

# adhd-designs

A small internal tool for running a print-on-demand t-shirt shop through
Printify + Shopify: upload artwork, pick a Printify blueprint (product) and
print provider, choose which variants (sizes/colors) to sell, and create a
draft product on Printify ready to review and publish to Shopify.

## Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite (`backend/`)
- **Frontend**: React + Vite, built to static files and served by Nginx (`frontend/`)
- **Printify**: the [Catalog](https://developers.printify.com/#catalog) and
  [Products](https://developers.printify.com/#products) REST API

SQLite was chosen so there's nothing extra to install; the models are
written so switching to Postgres later is just a `DATABASE_URL` change.

## How a shirt gets made

1. Upload artwork (`POST /api/designs/upload`) — stored on disk, dimensions read with Pillow.
2. Browse the Printify catalog (`GET /api/catalog/blueprints`, synced via `POST /api/catalog/sync`),
   pick a blueprint (e.g. "Unisex Heavy Cotton Tee") and a print provider.
3. Pick which variants (size/color combinations) to sell and a price.
4. `POST /api/products` resizes the artwork to each print area's exact
   pixel dimensions (stamping 300 DPI), uploads it to Printify, and creates
   a **draft** product — nothing is published or sold until you review it
   in Printify and push it to Shopify yourself.

## Local development

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in PRINTIFY_API_TOKEN and PRINTIFY_SHOP_ID
.venv/bin/uvicorn app.main:app --reload
```

Frontend (in a second terminal — the Vite dev server proxies `/api` and
`/uploads` to `http://127.0.0.1:8000`, see `frontend/vite.config.js`):

```bash
cd frontend
npm install
npm run dev
```

Open the printed `http://localhost:5173` URL. On first run, click "Sync
catalog from Printify" before you can pick a product.

## Deploying

See [`DEPLOY.md`](./DEPLOY.md) for the systemd unit and Nginx config to run
this on a real server alongside an existing site.

## Known gaps

- **Artwork placement**: the frontend now has a drag/scale/rotate editor
  (`frontend/src/PlacementEditor.jsx`, plain pointer events + CSS, no canvas
  library) for a single print position per product. `ProductCreateRequest.placements`
  (see `backend/app/schemas.py`) already accepts a list, so supporting
  multiple print positions (e.g. front + back) per product is additive work,
  not a breaking change.
- **Printify schema assumptions**: `backend/app/services/catalog_parser.py`
  reads print-area pixel dimensions from `variant.placeholders[].width` /
  `.height`, matching Printify's documented API shape. Printify's API does
  version over time — worth checking the raw response of your first real
  `/api/catalog/sync` + variant fetch against what's expected, since a
  silent field-name change there would silently produce blueprints with no
  usable print areas rather than an obvious error.

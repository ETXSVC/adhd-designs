# Deploying adhd-designs

Two pieces: a FastAPI backend (served by Gunicorn+Uvicorn workers behind
Nginx) and a static React build (served directly by Nginx). SQLite is the
database; there's no separate DB server to install.

## 1. Get the code onto the server

```bash
ssh you@your-server
cd /var/www/yourdomain   # or wherever this vhost's files live
git clone <this-repo-url> adhd-designs
cd adhd-designs
```

(If you're not using git on the server yet, `scp -r` the whole repo instead
and skip straight to step 2.)

## 2. Backend: Python environment

Requires Python 3.11+.

```bash
cd adhd-designs/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```
PRINTIFY_API_TOKEN=<generate at https://printify.com/app/account/api>
PRINTIFY_SHOP_ID=<from GET https://api.printify.com/v1/shops.json>
DATABASE_URL=sqlite:////var/www/yourdomain/adhd-designs/backend/app.db
UPLOAD_DIR=/var/www/yourdomain/adhd-designs/backend/uploads
CORS_ORIGINS=https://yourdomain.com
```

Use **absolute paths** for `DATABASE_URL` and `UPLOAD_DIR` once this runs
under systemd — the working directory won't be what you expect otherwise.

Quick sanity check before wiring up systemd:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# in another shell:
curl http://127.0.0.1:8000/api/health
# should print {"status":"ok"}
```

Stop it with Ctrl-C once that works.

## 3. Backend: systemd service

Create `/etc/systemd/system/adhd-designs.service`:

```ini
[Unit]
Description=adhd-designs FastAPI backend
After=network.target

[Service]
Type=notify
User=yourusername
Group=yourusername
WorkingDirectory=/var/www/yourdomain/adhd-designs/backend
EnvironmentFile=/var/www/yourdomain/adhd-designs/backend/.env
ExecStart=/var/www/yourdomain/adhd-designs/backend/.venv/bin/gunicorn \
    app.main:app \
    -k uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind unix:/run/adhd-designs/gunicorn.sock \
    --access-logfile - \
    --error-logfile -
RuntimeDirectory=adhd-designs
RuntimeDirectoryMode=0755
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Replace `yourusername` with the account that owns the app directory (the
Nginx worker needs read/execute access to the socket via group membership
or `RuntimeDirectoryMode`, which the setting above already covers).

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now adhd-designs
sudo systemctl status adhd-designs
```

## 4. Frontend: build once, serve as static files

The frontend doesn't need Node running in production — it's compiled to
plain HTML/JS/CSS.

```bash
cd adhd-designs/frontend
npm install
npm run build
```

This produces `adhd-designs/frontend/dist/`. Point Nginx at it (step 5).

Whenever you change frontend code, re-run `npm run build` and it's live —
no service to restart.

## 5. Nginx

Add this inside your existing server block for the domain (alongside
whatever PHP `location` block Virtualmin already generated — this doesn't
replace it, it adds two new `location`s):

```nginx
    # adhd-designs frontend (static build)
    location / {
        root /var/www/yourdomain/adhd-designs/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # adhd-designs backend API
    location /api/ {
        proxy_pass http://unix:/run/adhd-designs/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # uploaded artwork, served by the backend's StaticFiles mount
    location /uploads/ {
        proxy_pass http://unix:/run/adhd-designs/gunicorn.sock;
        proxy_set_header Host $host;
    }

    client_max_body_size 30M;   # design uploads are capped at 25MB app-side
```

If this app is meant to own the **entire** vhost instead of sharing it with
PHP, delete the PHP `location` block and put the three blocks above (plus
your existing `listen`/`server_name`/TLS lines) directly in the server
block.

Test and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 6. First run

```bash
curl -X POST https://yourdomain.com/api/catalog/sync
```

This pulls the full Printify blueprint list into SQLite. It only needs to
run once, and again any time Printify adds new products you want to offer
— there's no scheduled re-sync built in.

Then open `https://yourdomain.com/` and walk through: upload artwork →
pick a product → pick a print provider → pick variants → create draft.
Check the result in your Printify dashboard before publishing to Shopify.

## Logs

```bash
sudo journalctl -u adhd-designs -f
```

## Updating after a code change

```bash
cd /var/www/yourdomain/adhd-designs
git pull
# backend changed?
cd backend && .venv/bin/pip install -r requirements.txt
sudo systemctl restart adhd-designs
# frontend changed?
cd ../frontend && npm install && npm run build
```

## Known gaps (see README for details)

- No drag/scale/rotate UI for artwork placement yet — placements default to
  dead-center, full-scale on the print area. The backend API already
  accepts per-position `x`/`y`/`scale`/`angle`.
- `catalog_parser.py` reads Printify's `placeholders[].width/height` field
  names as documented; worth eyeballing the response of your first real
  sync in case Printify has changed that shape since.

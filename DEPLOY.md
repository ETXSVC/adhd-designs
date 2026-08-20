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

This produces `adhd-designs/frontend/dist/`. Point Nginx at it directly if
you can (see step 5's preferred option) — **that requires editing the
Nginx vhost, which needs root**. If you don't have root (or the vhost's
`root` is fixed elsewhere, e.g. a Virtualmin-managed `public_html` and you
only want to touch app-owned files), copy the build into whatever
directory Nginx already serves for `/` instead:

```bash
rsync -a --delete dist/assets/ /path/to/served/root/assets/
cp dist/index.html dist/favicon.svg /path/to/served/root/
```

**Never `rsync --delete` (or otherwise wipe) the whole served root** if
anything besides this app's build might live there — on a Virtualmin
vhost, `public_html` commonly also holds AWStats' `icon/` directory,
`awstats-icon`/`awstatsicons` symlinks, and an `awstats/` reports
directory; a blanket `--delete` sync will silently delete all of it. Scope
`--delete` to the build's own `assets/` subdirectory only (that one *is*
exclusively Vite's hashed output — old hashed bundles there are safe, and
correct, to prune on every deploy) and plain-copy the few top-level files.

Whenever you change frontend code, re-run `npm run build` and redeploy with
the copy above — no service to restart. **If you skip the copy step, the
new build sits in `frontend/dist/` but the live site keeps serving
whatever was last copied — this has actually happened:** several commits'
worth of frontend work (pagination, category filters, AI-metadata UI) were
built successfully but the copy step was missed, so the live site kept
serving a much older build for hours while `frontend/dist/` silently moved
on. Check what's actually live with `curl -s https://yourdomain/ | grep -o
'index-[A-Za-z0-9]*\.\(js\|css\)'` and compare the hash against
`frontend/dist/index.html` (or a listing of `frontend/dist/assets/`) if a
change doesn't seem to have taken effect — don't assume `npm run build`
alone is enough.

## 5. Nginx

**Preferred, if you have root:** point Nginx's `root` for `location /`
directly at `adhd-designs/frontend/dist` so every `npm run build` is live
with no copy step. Add this inside your existing server block for the
domain (alongside whatever PHP `location` block Virtualmin already
generated — this doesn't replace it, it adds two new `location`s):

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

### This server, specifically

On `app.adhd-designs.com` (Virtualmin), the vhost's `root` is fixed at
`/home/app.adhd-designs.com/public_html` (set once at the top of the
server block, shared with the PHP `fastcgi_param DOCUMENT_ROOT`) — nobody
has added a `location`-level `root` override for `frontend/dist`, and
doing so needs root to edit `/etc/nginx/sites-available/app.adhd-designs.com.conf`
and reload. Until/unless that's done, every frontend deploy is the copy
step from step 4, targeting `public_html` (an app-owned directory — no
sudo needed for the copy itself, just don't `--delete` the whole thing;
see the AWStats warning above, which is specifically about this
directory):

```bash
cd adhd-designs/frontend && npm run build
rsync -a --delete dist/assets/ /home/app.adhd-designs.com/public_html/assets/
cp dist/index.html dist/favicon.svg /home/app.adhd-designs.com/public_html/
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

- Artwork placement supports one print position per product; multiple
  positions (front + back) would need frontend work, though the API
  already accepts a list of placements.
- `catalog_parser.py` reads Printify's `placeholders[].width/height` field
  names as documented; worth eyeballing the response of your first real
  sync in case Printify has changed that shape since.

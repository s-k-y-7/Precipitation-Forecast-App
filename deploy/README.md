# Oracle Cloud VM Deployment

This guide deploys the app on one Ubuntu 24.04 ARM64 VM using the OCI Always Free eligible A1 shape. Keep the selected shape, boot volume, and network resources within the Always Free limits. OCI may reclaim an instance it classifies as idle, so this path has no uptime guarantee.

## Prepare the VM

1. Create the VM in the tenancy's India home region with an A1 shape that stays within the current Always Free allocation. Assign a public IP and use a persistent boot volume. Open inbound TCP 80 and 443; restrict SSH (22) to your address. Do not expose PostgreSQL (5433).
2. Install Docker Engine and Compose, Python 3.12, Node.js 20, Nginx, Certbot, and cron. Create a `forecast` system user and clone this repository to `/srv/precipitation-forecast`, owned by that user. Enable Docker and cron at boot with `sudo systemctl enable --now docker cron`.
3. Copy `deploy/production.env.example` to the repository root as `.env`. Replace the secret, database password, and DuckDNS hostname. Generate shell-safe secrets with `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'` and `openssl rand -hex 32`. Keep `.env` readable only by root and the `forecast` group (`sudo chown root:forecast .env && sudo chmod 640 .env`).
4. Create the cache directory with `sudo install -d -o forecast -g forecast /var/cache/precipitation-forecast`. The PostgreSQL Compose volume and this cache directory must stay on persistent VM storage.

## Install and start

```sh
# Run this database command as an administrator from the project root.
cd /srv/precipitation-forecast
sudo docker compose up -d db
```

Run the remaining build/install commands as the `forecast` system user (for example, start with `sudo -u forecast -H bash`):

```sh
cd /srv/precipitation-forecast
cd backend
python3 -m venv .venv
.venv/bin/pip install -e .
cd ../frontend
npm ci
npm run build
cd ../backend
.venv/bin/python manage.py migrate
```

Copy `deploy/precipitation-forecast.service` to `/etc/systemd/system/precipitation-forecast.service`; keep its `/srv/precipitation-forecast` paths aligned with the checkout. Copy `deploy/nginx.conf` to `/etc/nginx/sites-available/precipitation-forecast`, update `server_name` to the DuckDNS name, and link it from `sites-enabled`. Then run `sudo nginx -t && sudo systemctl reload nginx`. The config serves the Vite build and proxies `/api/` to Gunicorn on localhost. PostgreSQL uses `restart: unless-stopped`.

Point the DuckDNS hostname at the VM's public IP. After DNS resolves and port 80 is reachable, run `sudo certbot --nginx -d <your-duckdns-hostname>` to configure HTTPS and renewal. Install the systemd unit, run `sudo systemctl daemon-reload`, then start the API with `sudo systemctl enable --now precipitation-forecast`.

Run `sudo -u forecast /srv/precipitation-forecast/backend/.venv/bin/python /srv/precipitation-forecast/backend/manage.py refresh_forecast_runs` once and verify its output. Create the cron log directory with `sudo install -d -o forecast -g forecast /var/log/precipitation-forecast`, adjust `PROJECT_ROOT` if needed, and install the schedule with `sudo crontab -u forecast /srv/precipitation-forecast/backend/cron/forecast-refresh.crontab.example`. It checks for updates every three hours in UTC.

## Verify

- `systemctl status precipitation-forecast`, `docker compose ps`, and `nginx -t` succeed.
- The HTTPS homepage loads, `/api/coverage/india/` returns the India boundary, and `/api/forecast-runs/` lists a validated run.
- Forecast tiles render and a Bhopal point query returns interval values.
- The cron log records refresh/skip outcomes, and the forecast records and cache files remain after a VM reboot.

Do not use `docker compose down -v`; that removes the PostgreSQL data volume.

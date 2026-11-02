# gramps-web-build

Installs [Gramps Web](https://www.grampsweb.org/) as a system service behind
Apache, without Docker, on:

- Mageia 10
- Debian 13 (and LMDE 7)
- Ubuntu 24.04 or later
- Linux Mint 22 or later (on Ubuntu/Mint the `universe` component must be enabled)

Details:

- Backend: `gramps-webapi` from PyPI in a venv, run by gunicorn on
  `127.0.0.1:5000`. The venv reuses the distro's PyGObject, cairo and ICU
  packages. On Mageia it also reuses the distro's `gramps`. Debian, Ubuntu and
  Mint ship a Gramps too old for gramps-webapi (it needs 6.0.4 or later), so
  there Gramps 6.0.x comes from PyPI, as in upstream's Docker image.
- Frontend: the prebuilt `grampsjs-vX.Y.Z.tar.gz` release from GitHub (no Node).
- Storage: SQLite for family trees, users and the search index.
- No Celery/Redis: background tasks run inline.
- Multi-tree mode: the first-run page creates an admin and an empty tree. To
  load an existing tree use Settings -> Administration -> Data (collapsed
  section) -> Import Family Tree.

## Install

```
cd ~/GIT
git clone https://github.com/barjac/gramps-web-build.git
~/GIT/gramps-web-build/gramps-web-build
```

Run it as your normal user, not root. It asks for the root password (sudo or
su) when it needs it. The first run asks for the site's host name (e.g.
`gramps.example.org`) and saves it in `~/.gramps-web-build.cfg`. Point that
name at the server in DNS or in `/etc/hosts` on the clients, then open
`http://<host name>/` and create the admin account.

The app has no built-in help. Documentation is on the Gramps Web site:

- User guide: https://www.grampsweb.org/user-guide/
- Administration (users, roles, trees): https://www.grampsweb.org/administration/admin/

## Update

```
~/GIT/gramps-web-build/gramps-web-update [--force]
```

Updates the backend and frontend to the latest releases (or the versions
pinned in `~/.gramps-web-build.cfg`). Data, `config.cfg` and the Apache vhost
are kept. The user database schema is migrated each time the service starts.

## Settings: `~/.gramps-web-build.cfg`

| key | default | |
|---|---|---|
| `basedir` | `/srv/gramps-web` | install location |
| `servername` | asked on first run | Apache vhost `ServerName` |
| `port` | `5000` | gunicorn port, localhost only |
| `workers` | `2` | gunicorn workers |
| `webapi_version` | latest | pin gramps-webapi, e.g. `3.25.0` |
| `frontend_version` | latest | pin gramps-web, e.g. `26.10.2` |

## What goes where

| path | owner | |
|---|---|---|
| `<basedir>/venv/` | root | Python venv with gramps-webapi + gunicorn |
| `<basedir>/app/` | root | alembic files for user DB migrations |
| `<basedir>/static/` | root | frontend |
| `<basedir>/config.cfg` | root:gramps-web 0640 | Gramps Web API config, holds `SECRET_KEY` |
| `<basedir>/bin/gramps-web-cli` | root | runs `python -m gramps_webapi` as gramps-web |
| `<basedir>/data/` | gramps-web | trees, media, users, search index, caches, backups |
| `<basedir>/data/backup/<tree-id>/` | gramps-web | backups made in the web UI, `<uuid>.tar`, newest 5 kept per tree |
| `<basedir>/data/gramps/gramps60/plugins/` | root | Gramps addons FilterRules and JSON |
| `/etc/systemd/system/gramps-web.service` | | the service |
| `/etc/httpd/conf/sites.d/gramps-web.conf` | | Apache vhost on port 80 (Mageia) |
| `/etc/apache2/sites-available/gramps-web.conf` | | Apache vhost on port 80 (Debian, Ubuntu, Mint), enabled with `a2ensite` |

Back up `<basedir>/data/` and `<basedir>/config.cfg`.

`<basedir>/data/` is readable only by gramps-web, so list or copy backups as
root, e.g. `ls -lR <basedir>/data/backup`. `<tree-id>` is the tree's directory
name, not the name shown in the web UI.

## Notes

- **HTTPS:** add an SSL vhost (e.g. `certbot --apache`) and change `BASE_URL`
  in `config.cfg` to `https://`. Set `X-Forwarded-Proto "https"` in that vhost.
- **E-mail** (password reset, registration): fill in the `EMAIL_*` lines in
  `config.cfg`.
- **PyGObject:** gramps-webapi caps PyGObject at 3.50, but Mageia and Ubuntu
  26.04 ship newer ones. `mk-backend` installs the dependencies without that
  cap. pip then reports a conflict with the cap; that is expected.
- **Media:** `ffmpeg` (video thumbnails), `tesseract` with English (OCR) and
  Poppler (PDF thumbnails) are installed. For other OCR languages install
  e.g. `tesseract-deu` (Mageia) or `tesseract-ocr-deu` (Debian family).
- Not installed: AI chat and face detection.

## Scripts

| script | runs as | |
|---|---|---|
| `gramps-web-build` | user | first install |
| `gramps-web-update` | user | upgrade |
| `gramps-web-passwd <user> [basedir]` | root | set a user's password (forgotten password, no SMTP) |
| `mk-backend <basedir> [ver]` | root | venv + gramps-webapi + alembic files |
| `mk-frontend <basedir> [ver]` | root | frontend release into `static/` |
| `mk-config <basedir> <name>` | root | data dirs + `config.cfg` (kept if present) |
| `mk-addons <basedir>` | root | Gramps addons (FilterRules is needed by the Relationship Graph) |
| `mk-service <basedir> <port> <workers>` | root | systemd unit + CLI wrapper |
| `mk-apache <name> <port>` | root | Apache vhost (kept if present) |

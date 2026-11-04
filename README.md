# gramps-web-build

Installs [Gramps Web](https://www.grampsweb.org/) as a system service behind
Apache, without Docker, on:

- Mageia 10
- Debian 13 (and LMDE 7)
- Ubuntu 24.04 or later
- Linux Mint 22 or later (on Ubuntu/Mint the `universe` component must be enabled)
- Raspberry Pi OS 64-bit based on Debian 13 (trixie). The 32-bit and
  bookworm-based releases are not supported. Use a Pi 4 or 5 with 2 GB RAM or
  more (set `workers=1` with less), ideally on an SSD. Tested in an emulated
  arm64 Debian 13 container, not yet on a real Pi.

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
- More trees: the web UI can't create or delete them, so `gramps-web-cli`
  has extra `tree create`, `tree delete` and `tree backup` commands. Each login belongs to
  one tree; to switch trees, log in as a user of the other tree:

  ```
  sudo <basedir>/bin/gramps-web-cli tree create "Tree B"
  sudo <basedir>/bin/gramps-web-cli user add baz-b PASSWORD --tree <tree-id> --role 4
  sudo <basedir>/bin/gramps-web-cli tree delete [--delete-users] [--no-backup] "Tree B"
  sudo <basedir>/bin/gramps-web-cli tree backup [--force] [TREE...]
  ```

  `tree list` shows the IDs; trees can be given by ID or name. `--role` is
  one of the roles below. Give a tree's own manager 4, and keep 5 for
  the one site admin: a site admin can see and change every tree and user.
  Roles can be changed later in Settings -> Administration -> Manage users.

  | Role | Name | Can also (each role has all rights of the ones above it) |
  |---|---|---|
  | 0 | Guest | view the tree, but not private records; edit own account |
  | 1 | Member | view private records (e.g. living people) |
  | 2 | Contributor | add people, events and other records |
  | 3 | Editor | edit and delete records; edit custom filters |
  | 4 | Owner | manage the tree's users, import, backups, repair, batch delete |
  | 5 | Site admin | all trees and users, users between trees, site settings |

  `tree delete` first makes a backup in `<basedir>/data/backup/<tree-id>/`,
  the same as Make Backup in the web UI (restore it by uploading it in Restore
  from Backup, or unpack `data.gramps` from it for desktop Gramps). It then
  asks for the tree's name to be typed. It refuses while users belong to the
  tree, unless `--delete-users` is given, and always if a site admin does.
  Media files are kept in `<basedir>/data/media/<tree-id>/`. The service is
  restarted afterwards.
- Daily backups: `gramps-web-backup.timer` runs `tree backup` for every tree
  at about 03:30 (`Persistent=true`: a run missed while the machine was off
  happens at the next boot). It makes the same archive as Make Backup, so the
  backups are listed, downloadable and restorable in the web UI. A tree that
  hasn't changed since its newest backup gets no new one, so the
  `BACKUP_KEEP = 30` archives kept per tree (set in `config.cfg`; upstream's
  default is 5) are the last 30 different versions, not 30 days. Manual
  backups count towards the same 30. Media files are not in the archives.
  Check it with `systemctl list-timers gramps-web-backup.timer` and
  `journalctl -u gramps-web-backup`; change the time with
  `systemctl edit gramps-web-backup.timer`.

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

### Host name

Apache picks the Gramps site by the name in the browser's address bar, so the
site only opens by that name, not by IP address.

- The suggested default is `gramps.<this machine's domain>`, or
  `gramps.localhost` if the machine has no usable domain.
- `gramps.localhost` needs no DNS, but only works in a browser on the
  server itself.
- For other machines use a name such as `gramps.lan` and add a line like this
  to `/etc/hosts` on each client (`hostname -I` on the server shows its IP):

  ```
  192.168.1.10  gramps.lan
  ```

- The last part of the name must not be all digits: Apache answers
  `gramps.1` with 400 Bad Request, so the installer refuses such names.
- Testing in a VirtualBox VM: the default NAT network can't be reached from
  the host. Switch the VM's adapter to Bridged and use the VM's new address.
  A bridged address comes from your router's DHCP and can change.

To change the name later, edit it in the Apache vhost (see below), in
`BASE_URL` in `config.cfg` and in `~/.gramps-web-build.cfg`, then reload
Apache and restart gramps-web.

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

It first pulls the latest gramps-web-build itself. If that brought changes
but Gramps Web is already current, it still reinstalls the parts this project
provides (config dirs, addons, systemd unit, `gramps-web-cli` and its
helpers) without reinstalling the backend and frontend. `--force` reinstalls
everything.

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
| `<basedir>/bin/tree-{create,delete,backup}.py` | root | the `tree create`, `tree delete` and `tree backup` commands of gramps-web-cli |
| `<basedir>/data/` | gramps-web | trees, media, users, search index, caches, backups |
| `<basedir>/data/backup/<tree-id>/` | gramps-web | backups from the web UI and the daily timer, `<uuid>.tar`, newest `BACKUP_KEEP` (30) kept per tree |
| `<basedir>/data/gramps/gramps60/plugins/` | root | Gramps addons FilterRules and JSON |
| `/etc/systemd/system/gramps-web.service` | | the service |
| `/etc/systemd/system/gramps-web-backup.{service,timer}` | | daily backup of every tree |
| `/etc/httpd/conf/sites.d/gramps-web.conf` | | Apache vhost on port 80 (Mageia) |
| `/etc/apache2/sites-available/gramps-web.conf` | | Apache vhost on port 80 (Debian, Ubuntu, Mint), enabled with `a2ensite` |
| `/var/log/httpd/gramps-web_{error,access}_log` | | Apache logs for the site (Mageia) |
| `/var/log/apache2/gramps-web_{error,access}.log` | | Apache logs for the site (Debian, Ubuntu, Mint) |

The daily backups are on the same disk as the trees. For a copy elsewhere,
back up `<basedir>/data/` (it includes `data/backup/` and the media files)
and `<basedir>/config.cfg`.

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
- **External search** (a person's External Search panel): each site is just
  a link filled in from the person's name and dates, opened in your own
  browser, so a site you are logged in to there (e.g. Ancestry) shows its
  results with your subscription. Gramps Web stores no site logins. The
  built-in Ancestry link goes to ancestry.com; for the UK site, add your own
  engine in the panel's edit mode, e.g.
  `https://www.ancestry.co.uk/search?name={{name_given}}_{{name_surname}}&birth={{birth_year}}&death={{death_year}}`,
  and hide the built-in one. Other placeholders include `{{place_name}}`.
- Not installed: AI chat and face detection.

## Scripts

| script | runs as | |
|---|---|---|
| `gramps-web-build` | user | first install |
| `gramps-web-update` | user | upgrade |
| `gramps-web-passwd <user> [basedir]` | root | set a user's password (forgotten password, no SMTP) |
| `mk-backend <basedir> [ver]` | root | venv + gramps-webapi + alembic files |
| `mk-frontend <basedir> [ver]` | root | frontend release into `static/` |
| `mk-config <basedir> <name>` | root | data dirs + `config.cfg` (kept if present; only `BACKUP_KEEP` is added if missing) |
| `mk-addons <basedir>` | root | Gramps addons (FilterRules is needed by the Relationship Graph) |
| `mk-service <basedir> <port> <workers>` | root | systemd units (service, daily backup timer) + CLI wrapper (installs `cli/*.py`) |
| `mk-apache <name> <port>` | root | Apache vhost (kept if present) |

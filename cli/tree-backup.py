"""Back up trees: tree-backup.py [--force] [TREE...] (called by gramps-web-cli).

Makes the same archive as Make Backup in the web UI, in BACKUP_DIR/<tree-id>/,
so it is listed there and can be restored from there. With no TREE, every tree
is backed up. A new archive whose contents match the tree's newest backup is
deleted again (unless --force), so that a daily timer doesn't push the older,
different backups out. Afterwards only the newest BACKUP_KEEP archives of the
tree are kept, as the web UI does.
"""
import argparse
import gzip
import hashlib
import re
import sys
import tarfile
import warnings

# Gramps asks GTK for the icon theme on import, which as the service user
# (no screen) prints a Gtk-CRITICAL warning. Answer "no theme" instead, as
# Gramps does without GTK; GTK itself stays importable for the addons.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    Gtk.IconTheme.get_default = staticmethod(lambda: None)
except (ImportError, ValueError):
    pass

from gramps_webapi.api.backup import DATA_NAME, TREE_NAME, USERS_NAME, write_backup
from gramps_webapi.api.backup_store import backups_enabled, get_backup_store
from gramps_webapi.api.util import close_db, get_db_outside_request, list_trees
from gramps_webapi.app import create_app

parser = argparse.ArgumentParser(prog="gramps-web-cli tree backup")
parser.add_argument("trees", nargs="*", metavar="TREE", help="tree ID or name (default: all)")
parser.add_argument("--force", action="store_true", help="keep the backup even if unchanged")
args = parser.parse_args()

# the export date is the only part of an unchanged tree's export that differs
CREATED = re.compile(rb'<created date="[^"]*"')


def fingerprint(path: str) -> str | None:
    """Hash an archive's tree data and settings, ignoring the export date."""
    digest = hashlib.sha256()
    try:
        with tarfile.open(path) as tar:
            for name in (DATA_NAME, TREE_NAME, USERS_NAME):
                data = tar.extractfile(name).read()
                if name == DATA_NAME:
                    data = CREATED.sub(b"<created", gzip.decompress(data), count=1)
                digest.update(name.encode() + b"\0" + data)
    except (OSError, tarfile.TarError, KeyError, AttributeError, EOFError):
        return None
    return digest.hexdigest()


def find_tree(trees: list[tuple[str, str]], wanted: str) -> tuple[str, str]:
    """Return (id, name) of the tree with this ID or name."""
    by_id = [t for t in trees if t[0] == wanted]
    by_name = [t for t in trees if t[1] == wanted]
    if by_id:
        return by_id[0]
    if len(by_name) == 1:
        return by_name[0]
    if by_name:
        sys.exit(f"ERROR: several trees are named '{wanted}'; give the tree ID")
    sys.exit(f"ERROR: no tree with ID or name '{wanted}' (see: gramps-web-cli tree list)")


# as gramps_webapi's own CLI does
warnings.filterwarnings("ignore", message=".*flask-limiter.readthedocs.io.*")
app = create_app()
failed = 0
with app.app_context():
    if not backups_enabled():
        sys.exit("ERROR: BACKUP_DIR is not set in config.cfg")
    trees = [(t[1].rstrip("/").rsplit("/", 1)[-1], t[0]) for t in list_trees()]
    if args.trees:
        trees = [find_tree(trees, wanted) for wanted in args.trees]
    store = get_backup_store()
    keep = app.config["BACKUP_KEEP"]
    for tree_id, name in trees:
        previous = store.list_backups(tree_id)
        backup_id, path = store.new_path(tree_id)
        db_handle = get_db_outside_request(
            tree=tree_id, view_private=True, readonly=True, user_id=""
        )
        try:
            write_backup(db_handle, tree=tree_id, tree_name=name, file_path=path)
        except Exception as err:  # pylint: disable=broad-except
            print(f"ERROR: backup of '{name}' ({tree_id}) failed: {err}")
            failed += 1
            continue
        finally:
            close_db(db_handle)
        if previous and not args.force:
            newest = store.get_path(tree_id, previous[0]["id"])
            if newest and fingerprint(newest) == fingerprint(path) is not None:
                store.delete(tree_id, backup_id)
                print(f"'{name}': unchanged since the backup of "
                      f"{previous[0]['manifest'].get('created')}, nothing new kept")
                continue
        store.prune(tree_id, keep=keep, keep_id=backup_id)
        print(f"'{name}': backed up to {path} (newest {keep} kept)")
sys.exit(1 if failed else 0)

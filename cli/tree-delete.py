"""Delete a tree: tree-delete.py [--no-backup] [--delete-users] TREE.

Called by gramps-web-cli as "tree delete". TREE is a tree ID or name.

1. Make a backup of the tree in the web UI's format, in BACKUP_DIR/<tree-id>/,
   which the delete leaves alone. If the backup fails, nothing is deleted.
2. Ask for the tree's name to be typed as confirmation.
3. Delete the tree's database, its users (only with --delete-users), its
   settings, search index entries and task records.
Media files are kept; their folder is printed at the end.
"""
import argparse
import os
import shutil
import sys
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

from gramps_webapi.api.backup import write_backup
from gramps_webapi.api.backup_store import get_backup_store
from gramps_webapi.api.search import get_search_indexer
from gramps_webapi.api.util import close_db, get_db_outside_request, list_trees
from gramps_webapi.app import create_app
from gramps_webapi.auth import (
    AccessToken,
    TaskTree,
    Tree,
    User,
    delete_user,
    user_db,
)
from gramps_webapi.auth.const import ROLE_ADMIN
from gramps_webapi.const import TREE_MULTI

parser = argparse.ArgumentParser(prog="gramps-web-cli tree delete")
parser.add_argument("tree", help="tree ID or name (see: gramps-web-cli tree list)")
parser.add_argument("--no-backup", action="store_true", help="don't make a backup first")
parser.add_argument(
    "--delete-users", action="store_true", help="also delete the tree's users"
)
args = parser.parse_args()


def find_tree(wanted: str) -> tuple[str, str, str]:
    """Return (id, name, path) of the tree with this ID or name."""
    trees = [(os.path.basename(t[1]), t[0], t[1]) for t in list_trees()]
    by_id = [t for t in trees if t[0] == wanted]
    if by_id:
        return by_id[0]
    by_name = [t for t in trees if t[1] == wanted]
    if len(by_name) == 1:
        return by_name[0]
    if by_name:
        sys.exit(f"ERROR: several trees are named '{wanted}'; give the tree ID")
    sys.exit(f"ERROR: no tree with ID or name '{wanted}' (see: gramps-web-cli tree list)")


# as gramps_webapi's own CLI does
warnings.filterwarnings("ignore", message=".*flask-limiter.readthedocs.io.*")
app = create_app()
with app.app_context():
    if app.config["TREE"] != TREE_MULTI:
        sys.exit("ERROR: multi-tree mode is off (TREE is not '*' in config.cfg)")
    tree_id, name, path = find_tree(args.tree)

    # never delete outside the tree folder
    db_root = os.path.realpath(os.environ["GRAMPS_DATABASE_PATH"])
    path = os.path.realpath(path)
    if os.path.dirname(path) != db_root or os.path.basename(path) != tree_id:
        sys.exit(f"ERROR: unexpected tree path {path}")

    users = user_db.session.query(User).filter_by(tree=tree_id).all()
    admins = [u.name for u in users if u.role >= ROLE_ADMIN]
    if admins:
        sys.exit(
            f"ERROR: site admin(s) belong to this tree: {', '.join(admins)}\n"
            "Deleting the tree would leave the site without them; nothing deleted."
        )
    if users and not args.delete_users:
        sys.exit(
            f"ERROR: these users belong to the tree: {', '.join(u.name for u in users)}\n"
            "Add --delete-users to delete them with the tree; nothing deleted."
        )

    print(f"Tree:   {name}")
    print(f"ID:     {tree_id}")
    print(f"Users:  {', '.join(u.name for u in users) or 'none'}")
    print(f"Backup: {'NO (--no-backup)' if args.no_backup else 'yes, made first'}")
    try:
        answer = input(f"Type the tree name ({name}) to delete it: ")
    except EOFError:
        answer = ""
    if answer != name:
        sys.exit("Name doesn't match; nothing deleted.")

    backup_path = None
    if not args.no_backup:
        print("Making a backup...")
        store = get_backup_store()
        _, backup_path = store.new_path(tree_id)
        db_handle = get_db_outside_request(
            tree=tree_id, view_private=True, readonly=True, user_id=""
        )
        try:
            write_backup(db_handle, tree=tree_id, tree_name=name, file_path=backup_path)
        except Exception as err:  # pylint: disable=broad-except
            sys.exit(f"ERROR: backup failed, nothing deleted: {err}")
        finally:
            close_db(db_handle)

    shutil.rmtree(path)
    for user in users:
        user_db.session.query(AccessToken).filter_by(user_id=user.id).delete()
        delete_user(user.name)
    get_search_indexer(tree_id)._delete_all()  # pylint: disable=protected-access
    user_db.session.query(Tree).filter_by(id=tree_id).delete()
    user_db.session.query(TaskTree).filter_by(tree=tree_id).delete()
    user_db.session.commit()

    print(f"Deleted tree '{name}'" + (f" and {len(users)} user(s)" if users else ""))
    if backup_path:
        print(f"Backup: {backup_path}")
    media_dir = os.path.join(app.config["MEDIA_BASE_DIR"], tree_id)
    if os.path.isdir(media_dir):
        print(f"Media files kept in {media_dir} - delete them when sure")

"""Create an empty tree: tree-create.py NAME (called by gramps-web-cli)."""
import sys
import warnings
import uuid

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

from gramps_webapi.api.util import list_trees
from gramps_webapi.app import create_app
from gramps_webapi.const import TREE_MULTI
from gramps_webapi.dbmanager import WebDbManager

if len(sys.argv) != 2 or not sys.argv[1].strip():
    sys.exit("Usage: gramps-web-cli tree create NAME")
name = sys.argv[1].strip()
# as gramps_webapi's own CLI does
warnings.filterwarnings("ignore", message=".*flask-limiter.readthedocs.io.*")
app = create_app()
with app.app_context():
    if app.config["TREE"] != TREE_MULTI:
        sys.exit("ERROR: multi-tree mode is off (TREE is not '*' in config.cfg)")
    if name in [t[0] for t in list_trees()]:
        sys.exit(f"ERROR: a tree named '{name}' already exists")
    tree_id = str(uuid.uuid4())
    WebDbManager(
        dirname=tree_id,
        name=name,
        username=app.config["POSTGRES_USER"],
        password=app.config["POSTGRES_PASSWORD"],
        create_if_missing=True,
        create_backend=app.config["NEW_DB_BACKEND"],
        ignore_lock=app.config["IGNORE_DB_LOCK"],
    )
print(f"Created tree '{name}' with ID {tree_id}")
print(f"Add a user for it: gramps-web-cli user add NAME PASSWORD --tree {tree_id} --role 4")

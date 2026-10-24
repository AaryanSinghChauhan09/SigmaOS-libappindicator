"""XApp library engine for SigmaOS-xapp / xapp-python / xapp-thumbnailers /
libappindicator (inspired by xapp, blueman, celluloid).

Principles: widget inventories and thumbnailer files are parsed into typed
records with strict validation, icon lookup is deterministic (sorted walk),
GI binding plans are derived from a single namespace table (DRY), fail-fast
with actionable messages.
"""
import argparse, os, re, sys

ENGINE = {
    "name": "sigma-xapp",
    "summary": "XApp widgets, icons, thumbnailers and GI binding plans",
    "language": "python",
    "verbs": ["widgets", "icon", "thumbnailers", "bindings-plan"],
    "principles": ["Abstraction", "Single Source of Truth", "Fail-Fast",
                   "Defensive Programming", "KISS", "DRY",
                   "Deterministic Testing"],
}

cli_doc = """\
$ sigma-xapp widgets inventory.txt
core         3   deprecated   1   unavailable  1
$ sigma-xapp icon folder-open --theme-dir ~/.icons/Mint-Y/scalable
~/.icons/Mint-Y/scalable/apps/folder-open.svg
$ sigma-xapp thumbnailers ./thumbnailers
sigma-png.thumbnailer   ok (2 mime types)
$ sigma-xapp bindings-plan Gtk.Button Xapp.StatusIcon GdkPixbuf.Pixbuf
import gi
gi.require_version("Gtk", "3.0")
"""

_STATUSES = ("core", "deprecated", "unavailable", "unknown")
_MIME_RE = re.compile(r"^(?:\*|[a-z0-9.+-]+)/(?:\*|[a-z0-9.+-]+)$")
_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_ICON_EXTS = (".png", ".svg", ".xpm")
_THUMBNAILER_SECTION = "[Thumbnailer Entry]"


class XappError(ValueError):
    pass


def _read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def parse_inventory(text):
    """Parse `ClassName status [note]` lines into widget records."""
    entries = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise XappError(f"line {lineno}: expected 'Class status', "
                            f"got {line!r}")
        cls, rest = parts
        tokens = rest.split()
        status, note = tokens[0], " ".join(tokens[1:])
        if not _CLASS_RE.match(cls):
            raise XappError(f"line {lineno}: bad class name {cls!r}")
        if status not in _STATUSES:
            raise XappError(f"line {lineno}: bad status {status!r} "
                            f"(want one of {_STATUSES})")
        entries.append({"class": cls, "status": status, "note": note})
    if not entries:
        raise XappError("inventory is empty")
    return entries


def summarize(entries):
    """Counts by status and by toolkit prefix (deterministic dicts)."""
    by_status = {s: 0 for s in _STATUSES}
    by_toolkit = {}
    for entry in entries:
        by_status[entry["status"]] += 1
        prefix = entry["class"].split(".")[0]
        by_toolkit[prefix] = by_toolkit.get(prefix, 0) + 1
    return {"by_status": by_status,
            "by_toolkit": dict(sorted(by_toolkit.items())),
            "classes": sorted(e["class"] for e in entries)}


def icon_search(name, dirs):
    """Deterministic icon lookup: sorted walk of the given theme dirs."""
    if not name or "/" in name or "\\" in name or "\x00" in name:
        raise XappError(f"unsafe icon name: {name!r}")
    matches = []
    for root in dirs:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fname in sorted(filenames):
                stem, ext = os.path.splitext(fname)
                if stem == name and ext.lower() in _ICON_EXTS:
                    matches.append(os.path.join(dirpath, fname))
    if not matches:
        raise XappError(
            f"icon {name!r} not found in: "
            f"{', '.join(dirs) or '(no dirs given)'}")
    return sorted(matches)


def parse_thumbnailer(text, source="<text>"):
    """Parse a .thumbnailer file; returns record with an error list."""
    data, section, errors = {}, None, []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            errors.append(f"{source}:{lineno}: cannot parse {line!r}")
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if section != "Thumbnailer Entry":
            errors.append(f"{source}:{lineno}: key {key!r} outside "
                          f"{_THUMBNAILER_SECTION}")
            continue
        if key in data:
            errors.append(f"{source}:{lineno}: duplicate key {key!r}")
            continue
        data[key] = value
    exec_line = data.get("Exec", "")
    if not exec_line:
        errors.append(f"{source}: missing Exec")
    elif "%o" not in exec_line:
        errors.append(f"{source}: Exec must write to %o")
    mimes = [m for m in data.get("MimeType", "").split(";") if m]
    if not mimes:
        errors.append(f"{source}: missing MimeType")
    for mime in mimes:
        if not _MIME_RE.match(mime):
            errors.append(f"{source}: bad mime type {mime!r}")
    return {"exec": exec_line, "mimes": mimes, "try_exec":
            data.get("TryExec", ""), "errors": errors, "source": source}


GIR_NAMESPACES = {
    "Gtk": ("Gtk", "3.0"),
    "Gdk": ("Gdk", "3.0"),
    "GdkPixbuf": ("GdkPixbuf", "2.0"),
    "Gio": ("Gio", "2.0"),
    "GLib": ("GLib", "2.0"),
    "Pango": ("Pango", "1.0"),
    "Atk": ("Atk", "2.0"),
    "Xapp": ("Xapp", "1.0"),
}


def bindings_plan(classes):
    """Derive gi.require_version lines from the widget classes in use."""
    if not classes:
        raise XappError("no classes given")
    prefixes = sorted({c.split(".")[0] for c in classes})
    unknown = [p for p in prefixes if p not in GIR_NAMESPACES]
    if unknown:
        raise XappError(f"unknown toolkit prefix(es): {', '.join(unknown)} "
                        f"(known: {', '.join(sorted(GIR_NAMESPACES))})")
    namespaces = sorted({GIR_NAMESPACES[p] for p in prefixes})
    lines = ["import gi"]
    for ns, ver in namespaces:
        lines.append(f'gi.require_version("{ns}", "{ver}")')
    lines.append("from gi.repository import " +
                 ", ".join(sorted(ns for ns, _ in namespaces)))
    return {"namespaces": namespaces, "script": "\n".join(lines) + "\n"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"],
                                description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    wi = sub.add_parser("widgets", help="parse a widget inventory")
    wi.add_argument("inventory_file")
    ic = sub.add_parser("icon", help="find an icon in theme dirs")
    ic.add_argument("name")
    ic.add_argument("--theme-dir", action="append", default=[],
                    dest="dirs")
    th = sub.add_parser("thumbnailers", help="validate thumbnailer files")
    th.add_argument("path", help="a .thumbnailer file or a directory")
    bp = sub.add_parser("bindings-plan", help="generate GI binding imports")
    bp.add_argument("classes", nargs="+")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "widgets":
            summary = summarize(parse_inventory(_read(args.inventory_file)))
            status = "   ".join(f"{k:<12}{v}" for k, v in
                                summary["by_status"].items())
            print(status)
            toolkit = "   ".join(f"{k}:{v}" for k, v in
                                 summary["by_toolkit"].items())
            print(toolkit)
        elif args.cmd == "icon":
            for match in icon_search(args.name, args.dirs):
                print(match)
        elif args.cmd == "thumbnailers":
            if os.path.isdir(args.path):
                files = [os.path.join(args.path, f)
                         for f in sorted(os.listdir(args.path))
                         if f.endswith(".thumbnailer")]
                if not files:
                    raise XappError(f"no .thumbnailer files in {args.path!r}")
            else:
                files = [args.path]
            bad = 0
            for path in files:
                record = parse_thumbnailer(_read(path), source=path)
                if record["errors"]:
                    bad += 1
                    for err in record["errors"]:
                        print(f"FAIL {err}")
                else:
                    print(f"{os.path.basename(path):<28} ok "
                          f"({len(record['mimes'])} mime type(s))")
            return 1 if bad else 0
        elif args.cmd == "bindings-plan":
            print(bindings_plan(args.classes)["script"], end="")
        return 0
    except (XappError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    import tempfile
    # --- widget inventory ---------------------------------------------------
    inventory = """\
# core widgets
Gtk.ApplicationWindow  core
Gtk.HeaderBar          core
Gtk.MenuButton         core
Xapp.StatusIcon        deprecated  use Gtk.StatusIcon instead
Xapp.PinIntrospection  unavailable needs xapp >= 1.8
"""
    entries = parse_inventory(inventory)
    assert [e["class"] for e in entries][0] == "Gtk.ApplicationWindow"
    assert entries[3]["status"] == "deprecated"
    assert entries[4]["note"] == "needs xapp >= 1.8"
    summary = summarize(entries)
    assert summary["by_status"] == {"core": 3, "deprecated": 1,
                                    "unavailable": 1, "unknown": 0}
    assert summary["by_toolkit"] == {"Gtk": 3, "Xapp": 2}
    assert summary["classes"][-1] == "Xapp.StatusIcon"
    for bad in ("Gtk.Button\n",                       # missing status
                "Gtk.Button maybe\n",                 # bad status
                "Bad Class core\n",                   # bad class name
                "# nothing\n"):
        try:
            parse_inventory(bad)
        except XappError:
            pass
        else:
            raise AssertionError(f"inventory accepted: {bad!r}")

    # --- icon lookup (tempdir, deterministic) --------------------------------
    with tempfile.TemporaryDirectory() as d:
        theme_a = os.path.join(d, "ThemeA")
        theme_b = os.path.join(d, "ThemeB")
        os.makedirs(os.path.join(theme_a, "scalable", "apps"))
        os.makedirs(os.path.join(theme_a, "48", "apps"))
        os.makedirs(os.path.join(theme_b, "apps"))
        for path in (os.path.join(theme_a, "scalable", "apps",
                                  "folder-open.svg"),
                     os.path.join(theme_a, "48", "apps", "folder-open.png"),
                     os.path.join(theme_b, "apps", "folder-open.xpm"),
                     os.path.join(theme_b, "apps", "folder-open.txt")):
            open(path, "w").close()
        matches = icon_search("folder-open", [theme_b, theme_a])
        assert [os.path.basename(m) for m in matches] == \
            ["folder-open.png", "folder-open.svg", "folder-open.xpm"]
        assert matches == sorted(matches)
        # directories are walked in sorted order -> stable results
        assert matches == icon_search("folder-open", [theme_b, theme_a])
        try:
            icon_search("ghost", [theme_a, theme_b])
        except XappError as e:
            assert "not found" in str(e)
        else:
            raise AssertionError("missing icon accepted")
        for bad_name in ("../evil", "a/b", "", "nul\x00byte"):
            try:
                icon_search(bad_name, [theme_a])
            except XappError:
                pass
            else:
                raise AssertionError(f"icon name accepted: {bad_name!r}")

        # --- thumbnailers ----------------------------------------------------
        good = (_THUMBNAILER_SECTION + "\n"
                "TryExec=sigma-thumb\n"
                "Exec=sigma-thumb %i %o %s\n"
                "MimeType=image/png;image/jpeg;\n")
        record = parse_thumbnailer(good)
        assert record["errors"] == []
        assert record["mimes"] == ["image/png", "image/jpeg"]
        assert record["exec"] == "sigma-thumb %i %o %s"
        bad_cases = (
            (_THUMBNAILER_SECTION + "\nExec=sigma-thumb %i %o\n", "MimeType"),
            (_THUMBNAILER_SECTION + "\nExec=sigma-thumb %i %s\n", "%o"),
            (_THUMBNAILER_SECTION + "\nExec=x %o\nMimeType=notamime\n",
             "bad mime type"),
            (_THUMBNAILER_SECTION + "\nExec=x %o\nMimeType=image/png;\n"
                                    "Exec=y %o\n", "duplicate key"),
            ("Exec=x %o\n", "outside"),
            ("random line\n", "cannot parse"),
        )
        for text, fragment in bad_cases:
            record = parse_thumbnailer(text, source="bad.thumbnailer")
            assert any(fragment in e for e in record["errors"]), \
                (fragment, record["errors"])

        # directory mode in main() finds and validates files
        tdir = os.path.join(d, "thumbnailers")
        os.makedirs(tdir)
        with open(os.path.join(tdir, "sigma-png.thumbnailer"), "w") as fh:
            fh.write(good)
        with open(os.path.join(tdir, "broken.thumbnailer"), "w") as fh:
            fh.write(_THUMBNAILER_SECTION + "\nMimeType=image/png\n")

    # --- bindings plan ------------------------------------------------------
    plan = bindings_plan(["Gtk.Button", "Xapp.StatusIcon",
                          "GdkPixbuf.Pixbuf"])
    assert plan["namespaces"] == [("GdkPixbuf", "2.0"), ("Gtk", "3.0"),
                                  ("Xapp", "1.0")]
    assert plan["script"] == (
        "import gi\n"
        'gi.require_version("GdkPixbuf", "2.0")\n'
        'gi.require_version("Gtk", "3.0")\n'
        'gi.require_version("Xapp", "1.0")\n'
        "from gi.repository import GdkPixbuf, Gtk, Xapp\n")
    assert "gi.repository import Gtk" in \
        bindings_plan(["Gtk.Box"])["script"]
    for bad in ([], ["Foo.Bar"], ["Widget"]):
        try:
            bindings_plan(bad)
        except XappError:
            pass
        else:
            raise AssertionError(f"bindings accepted: {bad!r}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

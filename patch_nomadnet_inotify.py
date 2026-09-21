#!/usr/bin/env python3
"""
patch_nomadnet_inotify.py - make NomadNet register new files instantly.

License: Unlicense (public domain) - see LICENSE.

This software is possible because my parents believed in me and encouraged me to follow my passions.

WHAT THIS FIXES
---------------
NomadNet's Node.register_files() only ever registers a /file/... handler for
files that existed at the last scan (startup, or every file_refresh_interval
minutes - a poll). A file epub.py just extracted has no handler until the
next scan, so file_refresh_interval=1 means "up to a minute", not instant.

This patches Node.py to additionally watch storage/files/ with inotify
(via the `watchdog` package) and register a handler the moment a new file
appears - typically within milliseconds, not up to a minute. It does NOT
replace file_refresh_interval; keep that as a fallback in case the watcher
ever misses an event (inotify queues can overflow under extreme load).

This is a patch to NomadNet's own installed source, not your config. Two
real consequences of that:
  - Upgrading NomadNet (pip install --upgrade nomadnet) overwrites Node.py
    and silently discards this patch. Re-run this script after any upgrade.
  - Confirmed working against NomadNet 1.4.1's Node.py (which has a
    register_media() call and a file_refresh_interval job loop - see the
    CALL_ANCHOR_CANDIDATES list below for exactly what that means for the
    patch site). Not verified against any other version; if yours has
    restructured register_files() or __init__ significantly, the anchors
    may not match, and this script will tell you that plainly rather than
    silently doing nothing or partially patching.

USAGE
-----
    pip install watchdog
    python3 patch_nomadnet_inotify.py            # apply the patch
    python3 patch_nomadnet_inotify.py --revert    # restore from backup
    python3 patch_nomadnet_inotify.py --dry-run   # show what would change, do nothing
"""

import argparse
import importlib
import os
import re
import shutil
import sys

WATCHER_IMPORT_ANCHOR = "import RNS.vendor.umsgpack as msgpack"
WATCHER_IMPORT_BLOCK = """import RNS.vendor.umsgpack as msgpack

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAVE_WATCHDOG = True
except ImportError:
    _HAVE_WATCHDOG = False
"""

METHOD_ANCHOR = "    def register_files(self):"
NEW_METHOD = '''    def _start_file_watcher(self):
        """Patched in by patch_nomadnet_inotify.py.

        Registers a /file/... handler the moment a new file appears in
        storage/files/, instead of waiting for the next scan_files() poll.
        file_refresh_interval keeps working as a fallback alongside this.
        """
        if not _HAVE_WATCHDOG:
            RNS.log("watchdog not installed; instant file registration is disabled "
                    "(falling back to file_refresh_interval polling only). "
                    "Install with: pip install watchdog", RNS.LOG_WARNING)
            return

        node = self
        TEMP_SUFFIXES = (".part", ".tmp")

        class Handler(FileSystemEventHandler):
            def _register(self, src_path, wait_for_stable):
                if os.path.isdir(src_path):
                    return
                if src_path.endswith(TEMP_SUFFIXES):
                    return

                if wait_for_stable:
                    # Only needed for a file written in place (not the atomic
                    # temp-file-then-rename pattern, which is already whole
                    # the instant it appears under its final name).
                    last_size = -1
                    for _ in range(20):  # ~2s max
                        try:
                            size = os.path.getsize(src_path)
                        except OSError:
                            return
                        if size == last_size and size > 0:
                            break
                        last_size = size
                        time.sleep(0.1)

                request_path = "/file" + src_path.replace(node.app.filespath, "", 1)
                if request_path in node.servedfiles:
                    return
                try:
                    node.destination.register_request_handler(
                        request_path,
                        response_generator=node.serve_file,
                        allow=RNS.Destination.ALLOW_ALL,
                        auto_compress=32_000_000,
                    )
                    node.servedfiles.append(request_path)
                    RNS.log("Instantly registered new file: " + request_path, RNS.LOG_VERBOSE)
                except Exception as e:
                    RNS.log(f"Could not register {request_path}: {e}", RNS.LOG_ERROR)

            def on_created(self, event):
                self._register(event.src_path, wait_for_stable=True)

            def on_moved(self, event):
                # os.replace()/os.rename() into place - e.g. epub.py's
                # write-to-.part-then-rename pattern. Already complete the
                # instant this fires, so no stabilization wait needed.
                self._register(event.dest_path, wait_for_stable=False)

        try:
            observer = Observer()
            observer.schedule(Handler(), self.app.filespath, recursive=True)
            observer.daemon = True
            observer.start()
            self._file_observer = observer
            RNS.log("Watching " + self.app.filespath + " for instant file registration", RNS.LOG_VERBOSE)
        except Exception as e:
            RNS.log(f"Could not start file watcher: {e}", RNS.LOG_ERROR)

'''.strip("\n") + "\n\n" + METHOD_ANCHOR

CALL_ANCHOR_CANDIDATES = [
    # Newer NomadNet (added register_media()): this exact pair only ever
    # appears once, in __init__ - the periodic file_refresh_interval job
    # loop calls register_files() alone, with no register_media() after it.
    "        self.register_files()\n        self.register_media()",
    # Older NomadNet, no register_media(): only safe to use this shorter
    # anchor if it's unique, checked in apply_patch() below.
    "        self.register_files()",
]


def find_node_py():
    try:
        nomadnet = importlib.import_module("nomadnet")
    except ImportError:
        sys.exit("Could not import nomadnet - is it installed in this Python environment?")
    path = os.path.join(os.path.dirname(nomadnet.__file__), "Node.py")
    if not os.path.isfile(path):
        sys.exit(f"nomadnet is installed but {path} does not exist - unexpected layout.")
    return path


def ensure_time_import(content):
    if re.search(r"^import time$", content, re.MULTILINE):
        return content
    # Node.py has used `import time` since early versions; if it's missing,
    # add it near the other imports rather than assume where "top" is.
    return content.replace(WATCHER_IMPORT_ANCHOR, "import time\n" + WATCHER_IMPORT_ANCHOR, 1)


def pick_call_anchor(content):
    """Return the first candidate anchor that appears exactly once, or None."""
    for candidate in CALL_ANCHOR_CANDIDATES:
        if content.count(candidate) == 1:
            return candidate
    return None


def apply_patch(path, dry_run=False):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if "_start_file_watcher" in content:
        print("Already patched:", path)
        return False

    problems = []
    if content.count(WATCHER_IMPORT_ANCHOR) != 1:
        problems.append(f"expected exactly one '{WATCHER_IMPORT_ANCHOR}', found {content.count(WATCHER_IMPORT_ANCHOR)}")
    if content.count(METHOD_ANCHOR) != 1:
        problems.append(f"expected exactly one '{METHOD_ANCHOR}', found {content.count(METHOD_ANCHOR)}")

    call_anchor = pick_call_anchor(content)
    if call_anchor is None:
        counts = ", ".join(f"{content.count(c)}x {c.strip()!r}" for c in CALL_ANCHOR_CANDIDATES)
        problems.append(f"none of the call-site anchors were unique - counts were: {counts}")

    if problems:
        print(f"Cannot safely patch {path} - this installed version doesn't match what the script expects:")
        for p in problems:
            print("  -", p)
        print("\nNo changes made. You'll need to apply the equivalent edit by hand - "
              "see the comments at the top of this script for what to add and where.")
        return False

    print(f"Using call-site anchor: {call_anchor.strip()!r}")
    call_block = call_anchor + "\n        self._start_file_watcher()"

    new_content = content.replace(WATCHER_IMPORT_ANCHOR, WATCHER_IMPORT_BLOCK, 1)
    new_content = ensure_time_import(new_content)
    new_content = new_content.replace(METHOD_ANCHOR, NEW_METHOD, 1)
    new_content = new_content.replace(call_anchor, call_block, 1)

    if dry_run:
        print(f"Would patch {path} (3 edits, all anchors matched cleanly). No changes made (--dry-run).")
        return True

    backup = path + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print("Backed up original to", backup)
    else:
        print("Backup already exists at", backup, "- leaving it as-is.")

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched", path)
    print("Restart your NomadNet node for this to take effect.")
    return True


def revert(path):
    backup = path + ".bak"
    if not os.path.isfile(backup):
        sys.exit(f"No backup found at {backup} - nothing to revert.")
    shutil.copy2(backup, path)
    print(f"Restored {path} from {backup}")
    print("Restart your NomadNet node for this to take effect.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--revert", action="store_true", help="restore Node.py from the .bak made when patching")
    ap.add_argument("--dry-run", action="store_true", help="check whether the patch would apply cleanly, without writing")
    args = ap.parse_args()

    path = find_node_py()
    print("Found:", path)

    if args.revert:
        revert(path)
        return

    try:
        import watchdog  # noqa: F401
    except ImportError:
        if not args.dry_run:
            sys.exit("The `watchdog` package isn't installed in this Python environment.\n"
                      "Install it with:  pip install watchdog\n"
                      "(then re-run this script)")
        print("Note: `watchdog` isn't installed yet - the patched code checks for it at "
              "runtime and falls back to polling-only if it's missing, but install it "
              "with `pip install watchdog` before restarting the node.")

    apply_patch(path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

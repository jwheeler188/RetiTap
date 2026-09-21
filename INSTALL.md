# Installing RetiTap

See [README.md](./README.md) for what this does and why. This file is the
step-by-step install guide, settings reference, and troubleshooting.

## What's in this package

| File | What it is |
|---|---|
| `epub.py` | **New file.** Extraction logic — finds/copies the EPUB out of the ZIM, builds one from the book's text if the ZIM has none, manages the extracted-file cache. |
| `epub.mu` | **New file.** The page that runs when someone clicks a download link. |
| `entry.mu` | **Replaces your existing file.** Adds one `⤓ EPUB` link to the book-reading page's action row. |
| `zim_index.mu` | **Replaces your existing file.** Adds one `⤓` link to each row of the bookshelf listing. |
| `results.mu` | **Replaces your existing file.** Adds one `⤓ EPUB` link to each book in search results. |
| `check_zim_epubs.py` | Optional diagnostic — confirms your ZIM actually contains EPUBs, and can pre-warm the ID lookup cache. Not needed at runtime. |
| `clean_epubs.py` | Optional housekeeping — clears the extracted-EPUB cache, same idea as Retipedia's own `clean_images.py`. |
| `patch_nomadnet_inotify.py` | Optional, separate concern — patches your *installed NomadNet* (not this Retipedia folder) so new files register instantly instead of on a timer. See "Going instant" below. |

`entry.mu`, `zim_index.mu`, and `results.mu` here are your real files with the
EPUB link already added — copy them straight over your existing copies
rather than hand-editing. If you've since made your own changes to any of
these three, diff them first so you don't lose your edits.

**This assumes Retipedia v3.** These three files are patched copies of
v3's own code. If you're on an older Retipedia release, update it first —
a different version's `entry.mu`/`zim_index.mu`/`results.mu` may not match
closely enough for a straight copy-over to be safe.

## Install

1. **Back up your current `entry.mu`, `zim_index.mu`, and `results.mu`** in case you want to compare or revert:

   ```bash
   cd ~/.nomadnetwork/storage/pages/Retipedia   # your Retipedia folder
   cp entry.mu entry.mu.bak
   cp zim_index.mu zim_index.mu.bak
   cp results.mu results.mu.bak
   ```

2. **Copy all the files in this package into that same folder**, overwriting `entry.mu`, `zim_index.mu`, and `results.mu`:

   ```bash
   cp /path/to/retitap/*.py /path/to/retitap/*.mu \
      ~/.nomadnetwork/storage/pages/Retipedia/
   ```

3. **Make sure the new/replaced `.mu` files are executable** — they already are in this package, but if your copy step drops the permission bit:

   ```bash
   chmod +x entry.mu zim_index.mu results.mu epub.mu
   ```

4. **If you run Retipedia from a virtualenv/conda environment** (not the system Python), re-run Retipedia's own shebang fixer so `epub.mu` gets the same interpreter as the rest of your `.mu` files:

   ```bash
   python3 generate_meta.py --fix-shebangs
   ```

5. **Add these lines to your `settings.py`:**

   ```python
   epub_enabled     = True
   epub_files_dir   = None     # auto-detected: NomadNet's storage/files
   epub_subfolder   = "books"  # subfolder inside storage/files
   epub_cache_mb    = 2048     # size budget for extracted EPUBs; 0 = unlimited
   epub_refresh_min = 1        # should match NomadNet's file_refresh_interval below
   epub_fallback    = True     # build a simple EPUB from text if the ZIM has none
   epub_instant_refresh = False  # set True only after applying patch_nomadnet_inotify.py
                                 # AND confirming (via the node's log) that it's running -
                                 # see the "Going instant" section below
   ```

6. **Set `file_refresh_interval = 1` in your NomadNet config** (the same config file where you set `pages_path`, `announce_interval`, etc. — usually `~/.nomadnetwork/config`), under the node section:

   ```
   file_refresh_interval = 1
   ```

   Without this, NomadNet only registers download links for files that
   existed at the last scan — which defaults to startup only. Setting this
   means a freshly extracted EPUB becomes downloadable within about a
   minute instead of not at all until a restart.

7. **Restart your NomadNet node** so the config change and new pages take effect.

## Verify it before relying on it

Confirm your ZIM actually has EPUBs, and see the exact ID→path mapping it'll use:

```bash
python3 check_zim_epubs.py /path/to/your/gutenberg.zim --build-index 52424
```

(Swap `52424` for a real book ID from your archive — any numeric ID that
shows up in a `.epub` filename inside the ZIM works.) This also pre-warms
the fallback lookup cache, though for archives with Retipedia's own
catalog JSON (`full_by_title.js`), `epub.py` resolves most books without
ever needing this.

Then click through it for real:

1. Open a Gutenberg book's page — you should see a new `⤓ EPUB` link next to `⤓ Micron` / `⤓ HTML`.
2. Click it. You'll land on a page showing the file size and a download link.
3. Click the download link. If this is the first time that book's been requested, wait up to a minute (per `file_refresh_interval`) and reload the `epub.mu` page if the download doesn't start immediately — it'll tell you to.
4. Go back to the bookshelf listing (`zim_index.mu`) — the same book's row should now show a small `⤓` next to its title, which does the same thing.
5. Search for that book by title — the search results page (`results.mu`) should now show `⤓ EPUB` after the `parts` link on its row too.
6. Find a book that has a real EPUB in the archive (use `check_zim_epubs.py` to identify one) and click its `⤓ EPUB` link — you should see the Full vs. Text-only choice screen, with a real file size shown for the full option.

## Full vs. text-only EPUBs

Illustrated Gutenberg EPUBs can run several MB — one real example from this
project's own testing was 8.5 MB. Some clients (MeshChatX has been observed
doing this) enforce their own maximum file-transfer size and will fail with
an error like `file_too_large` on a big download, independent of anything
on the NomadNet/Retipedia side.

When a book has a real EPUB in the archive *and* `epub_fallback = True`,
`epub.mu` now shows a choice instead of assuming:

```
⤓ Full EPUB · 8.5 MB          (includes original formatting and illustrations)
⤓ Text-only EPUB              (no illustrations - much smaller)
```

The text-only version is built fresh from the book's own readable text —
the same code path already used automatically for books that have no EPUB
in the archive at all. Each variant caches separately (`title-id.epub` vs
`title-id-text.epub`), so choosing one doesn't affect the other.

This choice only appears when there's a genuine decision to make: books
with no EPUB in the archive (the common case for many Gutenberg ZIM
builds — check with `check_zim_epubs.py`) skip straight to the single
result, exactly as before this feature existed. Setting `epub_fallback =
False` also skips the choice screen, since there'd be nothing to choose
between — only the full EPUB is ever offered in that case.

## Going instant (optional)

By default, a freshly extracted EPUB isn't downloadable until NomadNet's
next file scan — up to `file_refresh_interval` minutes, because
`epub_instant_refresh` defaults to `False` and `epub.mu` shows an honest
"wait a bit, then reload" message for that case.

If you've applied `patch_nomadnet_inotify.py` (a separate script, not part
of this package — it patches NomadNet's own installed `Node.py` to register
new files via inotify instead of only on a timer), new files become
downloadable in about a second instead. Once you've confirmed that's
actually working — restart the node, extract a book you haven't downloaded
before, and check the node's log for a line like
`Instantly registered new file: /file/books/...` appearing within about a
second of the extraction — set:

```python
epub_instant_refresh = True
```

in `settings.py`. `epub.mu` will then skip the wait message and the
now-unnecessary "reload this page" link, and just show "Ready in about a
second" above the download link.

**This is a manual flag, not auto-detected.** `epub.mu` runs as a one-shot
subprocess with no way to ask the live node process whether its file
watcher is actually running. If you later revert the NomadNet patch, or it
gets silently dropped by a NomadNet upgrade (`pip install --upgrade
nomadnet` overwrites `Node.py`), set this back to `False` — otherwise
`epub.mu` will claim instant delivery while actually falling back to the
old polling behavior underneath, which is a worse experience than the
honest wait message it replaces.

## Housekeeping

```bash
python3 clean_epubs.py --stats   # see how much the extracted-EPUB cache is using
python3 clean_epubs.py 30        # remove EPUBs untouched for 30+ days
python3 clean_epubs.py           # remove all of them
```

`epub.py` also prunes automatically as new EPUBs are extracted, evicting the
least-recently-used ones once the folder passes `epub_cache_mb`. You don't
need to run the cleaner manually unless you want to reclaim space sooner.

## If something's wrong

- **No `⤓ EPUB` link appears on a book page** — check `epub_enabled = True` is in `settings.py`, and that `entry.mu` was actually replaced (grep for `epub.mu` in it — should find one line in the action row).
- **Download link 404s** — almost certainly `file_refresh_interval` isn't set, or the node hasn't been restarted since. It should be `1`, not `0` (the default).
- **"Could not read the EPUB from the archive" / "no EPUB in this archive"** — run the `check_zim_epubs.py --build-index` command above with a real book ID from your ZIM to see whether it's genuinely missing or a lookup problem. If it's genuinely missing, `epub_fallback = True` (already set above) makes `epub.mu` build a simple EPUB from the book's text instead.
- **A book with an unusual title (brackets, pipes, backticks) breaks the link** — this shouldn't happen; both patched files route through Retipedia's own `gutenberg.entry_fields()`, which is specifically designed to avoid this. If you do hit it, it's worth reporting exactly which book, since it'd point at an edge case in that escaping.

## License

Unlicense (public domain) — see [LICENSE](./LICENSE) and the
[README](./README.md#license). Every file in this package, including the
modified `entry.mu` / `zim_index.mu` / `results.mu`, carries the same
terms as Retipedia itself, so there's nothing extra to track when mixing
these files into your own copy.

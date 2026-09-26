# RetiTap

Demo site: ecb618b568d276fabbeed7355845cb91:/page/Retipedia/zim_index.mu`zim=gutenberg_en_lcc-g_2026-03.zim

On-demand EPUB downloads for [Retipedia](https://github.com/RFnexus/Retipedia) —
a searchable Gutenberg/Wikipedia/etc. `.zim` reader for
[NomadNet](https://github.com/markqvist/NomadNet).

Retipedia already lets people *read* Project Gutenberg books over the mesh.
This adds a `⤓ EPUB` link next to a book's title — on its reading page, in
the bookshelf listing, and in search results — that hands them a real EPUB
file instead, extracted from the `.zim` the moment they ask for it.

**This is an unofficial add-on.** It isn't part of Retipedia itself, and
it isn't affiliated with the Retipedia or NomadNet projects. It works by
patching a few of your own installed Retipedia files (see below) — you're
running this against your own copy, not a fork.

## Why this exists

Retipedia's Gutenberg archives can hold well over a thousand books.
Pre-converting all of them into EPUBs ahead of time means either a massive
one-time job, a giant index page nobody needs to scroll through, or both.

The better option turns out to be much simpler: current Kiwix Gutenberg
`.zim` builds already contain each book's EPUB as a regular entry in the
archive — extracting one is a blob copy, not a conversion. So instead of
converting anything in bulk, this hands out the file the instant someone
actually asks for it, and never touches the ~99% of books nobody requests
in a given session.

## Features

- **One-click EPUB downloads** from three places: a book's own page, the
  bookshelf listing, and search results.
- **Nothing pre-extracted.** A book's EPUB doesn't exist as a file on disk
  until someone clicks for it — then it's cached for next time.
- **Works even when the archive has no EPUB for a book.** Falls back to
  building a plain, readable EPUB straight from the book's text.
- **Full vs. text-only choice** when a book's real EPUB is large enough
  that some clients (MeshChatX has been observed doing this) refuse to
  download it — pick the lightweight, image-free version instead.
- **Automatic cache management.** Extracted files are pruned
  least-recently-used once they pass a configurable size budget.
- **Optional instant registration.** A companion patch to NomadNet itself
  makes a freshly extracted file downloadable in about a second, instead
  of waiting on NomadNet's next scheduled file scan.

## How it works, briefly

1. Click `⤓ EPUB` on any Gutenberg book. This links to a new page,
   `epub.mu`, rather than straight to a file — NomadNet can only serve
   files that already exist on disk, so something has to put the file
   there first.
2. `epub.mu` looks the book up in the `.zim` (reusing Retipedia's own
   catalog lookup, so it always agrees with what Retipedia itself would
   navigate to) and either copies its EPUB out directly, or — if the
   archive doesn't have one for that book — builds a simple one from the
   book's readable text.
3. The file lands in NomadNet's `storage/files/` folder, where NomadNet
   can serve it like any other file.
4. Re-requesting the same book later just serves the already-extracted
   file — no repeat work.

See [INSTALL.md](./INSTALL.md) for the full technical walkthrough,
including why NomadNet's file-registration timing matters here and what
the optional instant-registration patch actually changes.

## Requirements

- [Retipedia](https://github.com/RFnexus/Retipedia) **v3** or newer, serving
  at least one Gutenberg `.zim` archive. This was built and tested against
  Retipedia v3 specifically (the release that added Gutenberg bookshelf
  support) — `entry.mu`, `zim_index.mu`, and `results.mu` in this repo are
  patched copies of v3's own files, so an older or substantially different
  version of those files may not accept the patches cleanly. If you're on
  an earlier Retipedia release, update it first.
- [NomadNet](https://github.com/markqvist/NomadNet) — the core feature (the
  download links, `file_refresh_interval`) doesn't depend on a specific
  version. The optional `patch_nomadnet_inotify.py` is more particular: it
  was built and confirmed working against **NomadNet 1.4.1**'s `Node.py`
  specifically (which has a `register_media()` call and a `file_refresh_interval`
  job loop — see the patch script's own comments for why that matters). It
  refuses to touch a `Node.py` that doesn't match closely enough rather
  than guessing, so it's reasonably safe to just try on another version —
  but it hasn't been verified against anything other than 1.4.1.
- Everything Retipedia itself already requires (`libzim`, `beautifulsoup4`).
- `ebooklib`, for building the text-only fallback EPUB:
  ```
  pip install ebooklib
  ```
- Optional: [`watchdog`](https://pypi.org/project/watchdog/), only if you
  want the instant-registration patch (`pip install watchdog`).

## Quick start

```bash
# from your cloned RetiTap folder
cp epub.py epub.mu entry.mu zim_index.mu results.mu /path/to/your/Retipedia/
chmod +x /path/to/your/Retipedia/epub.mu /path/to/your/Retipedia/entry.mu \
         /path/to/your/Retipedia/zim_index.mu /path/to/your/Retipedia/results.mu
```

Then add to `settings.py`:

```python
epub_enabled     = True
epub_files_dir   = None     # auto-detected: NomadNet's storage/files
epub_subfolder   = "books"
epub_cache_mb    = 2048     # 0 = unlimited
epub_refresh_min = 1        # match NomadNet's file_refresh_interval
epub_fallback    = True
epub_instant_refresh = False  # see "Going instant" in INSTALL.md
```

...and set `file_refresh_interval = 1` in your NomadNet config, then
restart the node.

**Full step-by-step instructions, verification checklist, and
troubleshooting are in [INSTALL.md](./INSTALL.md) — read that before
deploying to a live node.** `entry.mu`, `zim_index.mu`, and `results.mu`
here are meant to replace your existing copies; back yours up first if
you've customized them.

## What's in this repo

| File | What it is |
|---|---|
| `epub.py` | Core extraction logic — finds/copies a book's EPUB out of the `.zim`, builds a text-only fallback when the archive has none, manages the extracted-file cache. |
| `epub.mu` | The page that runs when someone clicks a download link; shows the full-vs-text-only choice when relevant. |
| `entry.mu` | Retipedia's book-reading page, with one `⤓ EPUB` link added to its action row. |
| `zim_index.mu` | Retipedia's bookshelf listing, with one `⤓` link added per row. |
| `results.mu` | Retipedia's search results page, with the same link added per result. |
| `check_zim_epubs.py` | Diagnostic — confirms a `.zim` actually contains EPUBs, and can pre-warm the ID lookup cache. |
| `clean_epubs.py` | Housekeeping for the extracted-EPUB cache. |
| `patch_nomadnet_inotify.py` | Optional — patches your *installed NomadNet* (not Retipedia) so new files register instantly. Self-checking: refuses to touch a version it doesn't recognize, and has a `--revert`. |
| `INSTALL.md` | Full install guide, settings reference, verification steps, troubleshooting. |

## Limitations

- Built and tested against **Retipedia v3** specifically. `entry.mu`,
  `zim_index.mu`, and `results.mu` are patched copies of that version's own
  files — a different Retipedia version's files may have different line
  structure and reject the patch, or worse, apply somewhere subtly wrong if
  the anchor text happens to still match. Diff against your own copies
  before overwriting them if you're not certain you're on v3.
- Assumes the naming convention current Kiwix Gutenberg `.zim` builds use
  (`<title>.<id>` for a book's content, `<title>.<id>.epub` for its EPUB,
  both in the same flat namespace). Other `.zim` builds may not match this,
  though `epub.py` includes some fallback path guesses for older layouts.
- Some archives ship EPUBs for only a fraction of their books — the rest
  transparently use the text-only fallback. Check yours with
  `check_zim_epubs.py`.
- The instant-registration patch edits NomadNet's own installed source. A
  NomadNet upgrade will overwrite it; re-run the patch script afterward.
- Not tested against every Retipedia version or every `.zim` archive kind
  Retipedia supports — this add-on only touches the Gutenberg code path.

## Credits

- [Retipedia](https://github.com/RFnexus/Retipedia) by RFnexus — the
  project this extends, released under the Unlicense.
- [NomadNet](https://github.com/markqvist/NomadNet) by markqvist, and the
  underlying [Reticulum](https://github.com/markqvist/Reticulum) network
  stack.
- Gutenberg `.zim` archives from the [Kiwix](https://www.kiwix.org/)
  project, via [ebookfoundation.org/openzim.html](https://ebookfoundation.org/openzim.html).

## License

[Unlicense](https://unlicense.org/) — public domain. Same scheme Retipedia
itself uses, so there's nothing to reconcile between the new files here
(`epub.py`, `epub.mu`, `check_zim_epubs.py`, `clean_epubs.py`,
`patch_nomadnet_inotify.py`) and the modified Retipedia files
(`entry.mu`, `zim_index.mu`, `results.mu`) — everything in this repo is
released the same way, with no conditions attached. See [LICENSE](./LICENSE).

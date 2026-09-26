# 0004: The web door, Pyodide and the Content-Security-Policy

Date: 2026-09-25. Status: accepted.

## Context

Door 2 is a static page on GitHub Pages. It runs the `second_look` package in the
browser through [Pyodide](../glossary.md#pyodide), so a statement never has to leave
the user's computer. The page makes a promise: nothing leaves your browser. This
record decides how the page gets Pyodide, which
[Content-Security-Policy (CSP)](../glossary.md#content-security-policy-csp) it sets,
and how the promise is checked.

Facts checked on 2026-09-25:

- The newest stable Pyodide release is
  [`314.0.7`](https://github.com/pyodide/pyodide/releases/tag/314.0.7), published
  2026-09-14. It runs CPython `3.14.2`. The project's
  [changelog](https://pyodide.org/en/stable/project/changelog.html) lists the Python
  upgrade under `314.0.0`. The `0.29.x` and `0.27.x` lines still get fixes, but they
  are older.
- The release has a small "core" archive, `pyodide-core-314.0.7.tar.bz2`, of
  `6,757,104` bytes. GitHub lists its SHA-256 as
  `2abdcc2e35208af406e07724cffa85bc582ced97e9028383ecf5462541393f95`, and a download
  gave the same hash. The full archive with every package is `337,536,678` bytes. This
  project needs only the core.
- The page needs five files from the core archive: `pyodide.mjs`, `pyodide.asm.mjs`,
  `pyodide.asm.wasm`, `python_stdlib.zip` and `pyodide-lock.json`. Together they are
  `13,531,207` bytes (about `13.5` MB).
- GitHub Pages cannot set custom HTTP headers, so the CSP must be a `<meta>` tag. A
  `<meta>` CSP cannot use `frame-ancestors`
  ([MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors)).
- A web worker loaded from its own URL does not follow the page's CSP. Its policy comes
  from the HTTP headers of the worker script, and GitHub Pages sends none. A worker
  made from a `blob:` URL does inherit the page's policy. This is stated on
  [MDN's CSP page](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy),
  and the local test below showed it.

### How the CSP was tested

The core archive was unpacked into a scratch folder (not this repo) and served from
`127.0.0.1` by a small Python server. Two pages loaded Pyodide `314.0.7` in headless
Chrome `153.0.8010.53` on Windows. They ran Python code that imported every standard
library module the engine needs ([ADR 0001](0001-one-engine-two-doors.md)) and read a
small CSV. The pages recorded every CSP violation and reported back to the server.

- With `script-src 'self' 'wasm-unsafe-eval'`, Python ran and printed `3.14.2`. There
  were zero CSP violations. The policy did not include `'unsafe-eval'`, so Pyodide
  needs no JavaScript `eval`. This matches the Pyodide fix in
  [pull request `3075`](https://github.com/pyodide/pyodide/pull/3075).
- With `script-src 'self'` only, Chrome blocked the WebAssembly compile. It reported a
  violation of `script-src` with the blocked item `wasm-eval`, and Python never
  started. So `'wasm-unsafe-eval'` is required.
- A third page created a worker from its own URL and a worker from a `blob:` URL. Each
  worker tried to fetch from a server on another port. The request from the worker with
  its own URL reached that server. The request from the `blob:` worker was blocked, and
  so was the same request from the page itself.

Only Chrome was tested. Firefox and Safari were not.

## Options

How the page gets Pyodide:

1. Commit the five files into the repo. Every clone and every build has them with no
   network access. The cost is about `13.5` MB of binary files in git history for each
   Pyodide version. Binary files do not shrink much between versions, so each upgrade
   adds roughly the same again, forever.
2. Fetch the core archive when the site is built, pinned by version and SHA-256. The
   repo stays small, and the build either gets the exact same bytes or stops with an
   error. The cost is that building the page needs the network, and the build breaks if
   GitHub ever removes the release file.
3. Load Pyodide from a public CDN. It is the simplest setup, but the browser would
   contact a third party, which breaks the promise and needs a looser CSP.

Where Python runs in the browser:

1. On the page's main thread. The page's CSP covers it.
2. In a web worker with its own URL. The page stays responsive during loading, but, as
   the test above shows, the page's CSP does not cover it on GitHub Pages.

## Decision

Pyodide:

- Pin Pyodide `314.0.7` and the core archive's SHA-256 above in one committed file.
- Fetch at build time (option 2). The Pages workflow and a local `make` target download
  the core archive from the GitHub release, check the hash, and extract the five files
  into `web/pyodide/`. That folder is already in `.gitignore`. A wrong hash stops the
  build.
- The browser loads every file from the site's own origin. Only the build machine talks
  to GitHub, never the user's browser.
- The `second_look` wheel is built in the same workflow and served from the same origin.
  The Door 2 task picks how Pyodide installs it (`loadPackage` with the wheel's URL, or
  `unpackArchive`). Either way, no `micropip` and no package index are used.
- Pyodide starts loading only after the user picks a file. The first page load stays
  small, which helps the Lighthouse target. The browser cache keeps the files for later
  visits.
- Python runs on the main thread. No worker is used. If a later change needs a worker,
  it must be created from a `blob:` URL so it inherits the CSP. That change must add
  `worker-src blob:` and extend the browser test to cover the worker.

The CSP, as the first element inside `<head>`, before any script:

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
```

This is the exact policy that passed the test above. Each part:

- `default-src 'none'`: anything not listed below is blocked, including workers, frames,
  fonts and media.
- `script-src 'self' 'wasm-unsafe-eval'`: scripts only from the site's own files, plus
  WebAssembly compiling, which Pyodide needs. No inline scripts and no `eval`.
- `connect-src 'self'`: `fetch` and similar calls can reach only the site's own origin.
- `style-src 'self'` and `img-src 'self'`: styles and images only from the site's own
  files. No inline `<style>` blocks.
- `base-uri 'none'` and `form-action 'none'`: no changed base URL and no form posts.

There is no upload endpoint. The site is static files only, and no code path sends
the statement anywhere.

How the page shows that nothing leaves the browser:

- The CSP itself, which anyone can read in the page source. The page links to it and to
  the code.
- A headless browser test (Playwright) in CI, written in the Door 2 task. It loads the
  page, runs the committed synthetic statement and checks that the flags appear. It
  records every network request and fails if any request goes to another origin, uses a
  method other than `GET`, carries a query string, or asks for a path outside a fixed
  list of the site's own files. This goes further than the CSP, which still allows
  requests to the site's own origin.
- The test runs in Chromium, and also in Firefox and WebKit if Playwright can run them
  in CI, because only Chrome was tested for this record.

## Consequences

- The page contacts no third party. A reader can check this in three places: the CSP,
  the test and the code.
- Building the page needs the network. `make demo` uses the command line door, so it
  still needs no downloads.
- Loading Python on the main thread can freeze the page for a moment after the user
  picks a file. The page should say "Loading Python, about `13.5` MB, only the first
  time" while it waits.
- Some limits stay, and `docs/whats_weak.md` should list them:
  - A `<meta>` CSP cannot set `frame-ancestors`, so another site could show this page in
    a frame.
  - The CSP does not stop the page from sending the user to another address, and it
    allows requests to the site's own origin. The browser test and the short code cover
    these, not the CSP.
  - Browser extensions the user installed run outside the page's CSP.
- Upgrading Pyodide means changing the pinned version and hash, then rerunning the
  browser test. The page never follows "latest" on its own.

## Option not taken

Committing the Pyodide files into the repo was not chosen, because each version would
add about `13.5` MB of binaries to git history for good, and a pinned hash gives the
same reproducible build.

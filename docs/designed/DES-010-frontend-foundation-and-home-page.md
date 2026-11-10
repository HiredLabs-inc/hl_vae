# DES-010: Frontend foundation and home page (HTML, CSS, JS)

- **Status:** Designed
- **Area:** Frontend
- **Created:** 2026-11-10
- **Updated:** 2026-11-10
- **Related:** branch `feature/home-view`. Builds on DES-006 (merged into `develop` in PR #3): the `static/vae/…` layout, WhiteNoise, manifest storage and `test_manifest_build`. DES-006 also says how a frontend build step would be added later. Not yet placed in the backlog's *Implementation order* (see Implementation Plan). DES-005 runs the tests below in CI once it lands. DES-009 (custom domain) is needed before social-sharing meta tags. hl_main's `frontend/` app (Tailwind, Vite, htmx, Alpine) was looked at and not copied (see Alternatives).

## Summary

This sets up the site's front end. It adds one base template that every page
extends, a shared header and footer, one hand-written stylesheet, and one small
JavaScript file. All of it is served as plain static files, with no Node, npm or
build step. The first page built on it is the home page at `/`, which renders
`templates/index.html`. That file is empty today.

## Motivation / Problem

- `/` returns 200 but renders a blank page. `templates/index.html` is an empty
  file, `works.views.home_view` renders it, and the DES-002 smoke test only
  checks that the template is used.
- There's no base template. Without one, each new page copies its own `<head>`,
  header and footer, and they drift apart.
- There's no CSS or JS yet. DES-006 is merged, so serving is in place:
  WhiteNoise, hashed and gzipped files on stage, and a README section saying
  project assets go in `static/vae/…`. `static/` holds only a `.gitkeep`.
  DES-006 doesn't decide how styles and scripts are written, named, loaded or
  tested.
- hl_main's front end is the obvious thing to copy. It needs Node in the Docker
  build, a `package.json`, a Vite manifest template tag and a second
  cache-busting scheme. DES-006 deliberately left all of that out. This design
  has to decide whether VAE needs it yet.
- Decisions made here are expensive to change later: template block names, the
  CSS naming scheme, design tokens and how JS attaches to the page. Every later
  page depends on them.

## Goals and Non-goals

**Goals**

- One `base.html` that has the document skeleton, the site header and footer,
  and the extension points (blocks) every page uses.
- A home page with semantic HTML that is complete without JavaScript and
  responsive from 320 px wide up.
- One place for design decisions (colours, type, spacing): CSS custom
  properties in `site.css`. When the brand is decided, only that block changes.
- Accessible from day one, to WCAG 2.2 AA: landmarks, a skip link, visible focus
  styles, colour contrast, 44 px touch targets, and respect for
  `prefers-reduced-motion`.
- No build step. Assets are edited in `static/vae/` and served as they are,
  hashed and compressed by DES-006's WhiteNoise setup.
- No third-party requests, so no CDNs, web fonts or analytics. This keeps a
  strict Content Security Policy possible later (`script-src 'self'`), with no
  inline scripts or inline styles.
- Tests that catch a broken page skeleton or a missing asset before it reaches
  stage.

**Non-goals**

- **Final branding and copy.** There's no logo, palette, typeface or mission
  text yet (see Open Questions). The home page ships with clearly marked
  placeholder copy and a neutral placeholder palette.
- **A frontend build pipeline** (npm, Tailwind, Vite, Sass, TypeScript). If one
  is needed later, DES-006's *Future frontend tooling* section says how it fits.
- **Interactive features** such as htmx, Alpine, forms or sign-up. Nothing on
  the home page talks to the server.
- **Dark mode, print styles and RTL.** None are needed for a placeholder home
  page.
- **Open Graph and Twitter card tags.** They need absolute URLs, so they wait
  for DES-009.
- **CSS, JS and template linters in CI** (Stylelint, Biome, djLint). See Open
  Questions.
- **Moving the home view out of `works`.** `works.views.home_view` and the
  `index` URL name stay. A `pages` app can come with the second static page if
  it's wanted.
- **Styling the Django admin.** It keeps its own CSS.

## Proposed Design

### File layout

```
templates/
├── base.html                    # new: document skeleton every page extends
├── index.html                   # filled in: home page, extends base.html
└── components/
    ├── site_header.html         # new: brand link + main nav
    └── site_footer.html         # new: copyright, contact

static/                          # STATICFILES_DIRS (already in base.py)
└── vae/                         # project namespace, as in DES-006
    ├── css/
    │   └── site.css             # the only stylesheet
    ├── js/
    │   └── site.js              # the only script
    └── img/
        └── favicon.svg          # placeholder until there's a logo
```

- Site-wide templates stay in the project-level `templates/` that
  `TEMPLATES["DIRS"]` already points at. `components/` uses the same folder name
  as hl_main.
- `static/.gitkeep` (from DES-006) is deleted in this change. DES-006 kept it
  only until the first real asset arrived.
- **No settings change is needed.** DES-006's settings in `base.py` already
  cover these files:

  | Where | Storage | What `{% static 'vae/css/site.css' %}` gives |
  |---|---|---|
  | Dev (`runserver`, `DEBUG = True`) | WhiteNoise serves from the finders and autorefreshes (`runserver_nostatic`) | `/static/vae/css/site.css`, with no `collectstatic` |
  | Tests (`test.py`) | Plain `StaticFilesStorage`, `WHITENOISE_AUTOREFRESH` | `/static/vae/css/site.css` |
  | `collectstatic` (Docker build) and stage | `CompressedManifestStaticFilesStorage` | `/static/vae/css/site.<hash>.css`, plus a `.gz` copy |

- **Manifest storage is strict.** On stage, a `{% static %}` path that isn't in
  the manifest (for example a typo) raises `ValueError` and the page returns
  500. Tests use plain storage, which doesn't catch that. That's why
  `test_assets_linked_and_found` (see Testing) checks every asset the base
  template names.

### Templates

**`base.html`.** Every page extends this template and fills in blocks. Nothing
else goes in `<head>`.

```django
<!DOCTYPE html>
{% load static %}
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Veteran Academic Exchange{% endblock %}</title>
  <meta name="description" content="{% block meta_description %}Veteran Academic Exchange{% endblock %}">
  <link rel="icon" href="{% static 'vae/img/favicon.svg' %}" type="image/svg+xml">
  <link rel="stylesheet" href="{% static 'vae/css/site.css' %}">
  <script type="module" src="{% static 'vae/js/site.js' %}"></script>
  {% block head %}{% endblock %}
</head>
<body{% block body_attrs %}{% endblock %}>
  <a class="skip-link" href="#main">Skip to main content</a>
  {% include "components/site_header.html" %}
  <main id="main" tabindex="-1">
    {% block content %}{% endblock %}
  </main>
  {% include "components/site_footer.html" %}
  {% block scripts %}{% endblock %}
</body>
</html>
```

| Block | Purpose | Default |
|---|---|---|
| `title` | `<title>`. Pages use `{% block title %}Page name · {{ block.super }}{% endblock %}` | `Veteran Academic Exchange` |
| `meta_description` | Search-result snippet | site name (until copy exists) |
| `head` | Extra page-only `<link>` tags. Rarely needed | empty |
| `body_attrs` | Page hook, e.g. ` class="page-home"`. Avoid if possible | empty |
| `content` | The page itself, inside `<main>` | empty |
| `scripts` | Page-only `<script type="module" src=…>` tags | empty |

- `site.js` loads in `<head>` as `type="module"`. Modules are deferred, so this
  doesn't block rendering, and the download starts as early as possible.
- `<main tabindex="-1">` lets the skip link move keyboard focus, not just
  scroll the page.
- **No inline `<script>` and no `style="…"` attributes** anywhere in templates.
  A test enforces this (see Testing).

**`components/site_header.html`**

```django
<header class="site-header">
  <div class="container site-header__inner">
    <a class="site-header__brand" href="{% url 'index' %}">Veteran Academic Exchange</a>
    <nav class="site-nav" aria-label="Main">
      <button class="site-nav__toggle" type="button" data-nav-toggle
              aria-expanded="false" aria-controls="site-nav-list" hidden>Menu</button>
      <ul class="site-nav__list" id="site-nav-list">
        <li><a href="{% url 'index' %}#about">About</a></li>
        <li><a href="{% url 'index' %}#how-it-works">How it works</a></li>
        <li><a href="{% url 'index' %}#contact">Contact</a></li>
      </ul>
    </nav>
  </div>
</header>
```

- The brand is a text wordmark until a logo exists. A logo later becomes an
  `<img>` with `alt="Veteran Academic Exchange home"`, and `width` and `height`
  set to avoid layout shift.
- Nav links point at sections of the home page, because that's the only page.
  They use `{% url 'index' %}#…` so they still work from other pages later.
- The toggle starts `hidden`. Without JS, the full list shows and wraps on
  narrow screens.

**`components/site_footer.html`** has `© {% now "Y" %} Veteran Academic
Exchange` and a contact line. The address is an Open Question. It has no
links to pages that don't exist yet, such as privacy or terms.

**`index.html`**

```django
{% extends "base.html" %}

{% block content %}
<section class="hero" aria-labelledby="hero-title">
  <div class="container">
    <h1 id="hero-title">Veteran Academic Exchange</h1>
    <p class="hero__lede">{# PLACEHOLDER COPY #}One-sentence mission statement.</p>
    <a class="button button--primary" href="#contact">Get in touch</a>
  </div>
</section>

<section id="about" class="section" aria-labelledby="about-title">…<h2 id="about-title">About</h2>…</section>
<section id="how-it-works" class="section" aria-labelledby="how-title">
  …<h2 id="how-title">How it works</h2>
  <ol class="steps">…three steps…</ol>
</section>
<section id="contact" class="section" aria-labelledby="contact-title">…<h2 id="contact-title">Contact</h2>…</section>
{% endblock %}
```

- One `<h1>` per page, and headings never skip a level.
- Placeholder copy is marked `{# PLACEHOLDER COPY #}`, so
  `grep -rn "PLACEHOLDER COPY" templates/` lists everything still to write.
- `home_view` stays as it is. The page needs no context.

### CSS

**One file, `static/vae/css/site.css`, organised with cascade layers.** Layers
make the order of precedence explicit, so later rules don't need more specific
selectors or `!important` to win.

```css
@layer reset, tokens, base, layout, components, utilities;

@layer tokens {
  :root {
    /* Colour (placeholder palette; replace when the brand is decided).
       Every text/background pair must meet WCAG AA 4.5:1. */
    --color-ink: #1b2430;
    --color-ink-muted: #4a5666;
    --color-surface: #ffffff;
    --color-surface-alt: #f4f6f8;
    --color-line: #dde2e8;
    --color-accent: #1f4e8c;
    --color-accent-ink: #ffffff;
    --color-focus: #1f4e8c;

    /* Type */
    --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --step--1: clamp(0.875rem, 0.85rem + 0.1vw, 0.95rem);
    --step-0: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);
    --step-1: clamp(1.25rem, 1.15rem + 0.5vw, 1.5rem);
    --step-2: clamp(1.5rem, 1.3rem + 1vw, 2.25rem);
    --step-3: clamp(2rem, 1.6rem + 2vw, 3.25rem);

    /* Space, shape, layout */
    --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 1rem;
    --space-4: 1.5rem;  --space-5: 2.5rem; --space-6: 4rem;
    --radius: 0.5rem;
    --container-max: 70rem;
    --tap-min: 2.75rem; /* 44px */
  }
}
```

| Layer | Contains |
|---|---|
| `reset` | A small modern reset: `box-sizing`, margin removal, `img { max-width: 100%; height: auto }`, and `font: inherit` on form controls |
| `tokens` | Custom properties only (above) |
| `base` | Element styles: `body`, headings, links, `:focus-visible`, `::selection`, smooth scroll guarded by `prefers-reduced-motion: no-preference` |
| `layout` | `.container`, `.section`, `.stack` (vertical rhythm), `.site-header`, `.site-footer` |
| `components` | `.skip-link`, `.site-nav`, `.button`, `.hero`, `.steps` |
| `utilities` | `.visually-hidden`, and little else |

**Conventions**

- **Naming:** a light form of BEM, `block__element--modifier`, for example
  `.site-nav__toggle` and `.button--primary`. Classes describe what a thing is,
  not how it looks.
- **Only tokens in components.** Components use `var(--…)` for colour, spacing,
  type and radius. A raw hex value or `px` outside the `tokens` layer is a review
  comment.
- **Mobile first.** Base rules are for narrow screens. Wider screens are added
  with `@media (min-width: 40em)` and `(min-width: 64em)`. Custom properties
  can't be used inside media queries, so the two breakpoints are written as
  literals and listed in a comment at the top of the file.
- **Focus is always visible.** `:focus-visible { outline: 3px solid
  var(--color-focus); outline-offset: 2px; }`, and outlines are never removed
  without a replacement.
- **Fonts:** the system font stack. That means no web-font download, no
  third-party request and no flash of unstyled text. A brand typeface would be
  self-hosted in `static/vae/fonts/` and referenced with a relative `url()`.
- **Browser support:** features that are [Baseline Widely
  available](https://web.dev/baseline). As of 2026 that covers cascade layers,
  custom properties, `clamp()`, `:focus-visible`, `gap` and native nesting.
  There's no autoprefixer, so check Baseline before using a newer feature.
- **References between assets** use relative `url()` paths, for example
  `url("../img/x.svg")`. DES-006's manifest storage rewrites them to hashed
  names, and its `test_manifest_build` fails if a referenced file is missing.
- **When the file gets big** (roughly 600+ lines), split components into
  `static/vae/css/components/*.css` and `@import` them from `site.css`, inside
  their layer: `@import url("components/nav.css") layer(components);`. The
  manifest storage rewrites `@import` URLs too. Don't split before then.

### JavaScript

**One ES module, `static/vae/js/site.js`, which only adds to the page.** Every
page has to work fully without it.

```js
// Progressive enhancements shared by every page. The site must work without this file.
document.documentElement.classList.add("js");

// Collapsible main nav on narrow screens.
const toggle = document.querySelector("[data-nav-toggle]");
const menu = toggle && document.getElementById(toggle.getAttribute("aria-controls"));

if (toggle && menu) {
  const isOpen = () => toggle.getAttribute("aria-expanded") === "true";
  const setOpen = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    menu.dataset.open = String(open);
  };

  setOpen(false);
  toggle.hidden = false;

  toggle.addEventListener("click", () => setOpen(!isOpen()));
  menu.addEventListener("click", (event) => {
    if (event.target.closest("a")) setOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) {
      setOpen(false);
      toggle.focus();
    }
  });
}
```

The matching CSS keeps the collapsed state on narrow screens only:

```css
@media (max-width: 39.99em) {
  .js .site-nav__list[data-open="false"] { display: none; }
}
@media (min-width: 40em) {
  .site-nav__toggle { display: none; }
}
```

**Conventions**

- **No framework and no npm.** If a library is ever needed (for example htmx
  for a later form), vendor its minified file into `static/vae/vendor/` with
  its version in the file name and its licence beside it. Don't use a CDN.
- **Hooks are `data-*` attributes**, never CSS classes. JS finds
  `[data-nav-toggle]`, not `.site-nav__toggle`, so renaming a class can't break
  behaviour. State goes in ARIA attributes (`aria-expanded`) or `data-*`, and
  CSS styles from those.
- **Module scripts only** (`<script type="module" src=…>`). They're deferred,
  run in strict mode, keep their variables out of the global scope, and don't
  run in very old browsers. Those browsers just get the no-JS page.
- **No imports between our own modules, for now.** Django's manifest storage
  doesn't rewrite JS `import` paths by default
  (`support_js_module_import_aggregation` is off). An imported file would then
  load by its unhashed name, with WhiteNoise's 60-second cache. When a second
  module is needed, turn that option on in the same change. That means a small
  subclass of `whitenoise.storage.CompressedManifestStaticFilesStorage` with
  `support_js_module_import_aggregation = True`, named in `STORAGES` in
  `base.py`. `test_manifest_build` then covers it.
- **Page-only scripts** go in the page's `{% block scripts %}`, not in `site.js`.
- **No inline JS, no `onclick=`, and no `eval`.** This keeps a strict CSP
  possible.

### Request flow

```
GET /  ──▶ works.views.home_view ──▶ index.html ⟶ base.html (+ header, footer includes)
             browser then fetches, in parallel:
               /static/vae/css/site.css       (render-blocking, ~5–10 KB)
               /static/vae/js/site.js         (module, deferred, <2 KB)
               /static/vae/img/favicon.svg
```

After `collectstatic` (in the Docker build on stage, or locally with `DEBUG`
off), those become hashed URLs such as `site.3f2a….css`. They're served gzip-compressed with one-year immutable cache
headers. The budget for the home page is **under 30 KB transferred** with no
images, and **no requests to any other origin**.

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| hl_main's stack: Tailwind 3 + Vite + npm, htmx + Alpine | Same class names and patterns as hl_main; fast to build pages with utilities | Node in a separate Docker stage, a `package.json` and lockfile, a watcher in dev, Node in CI, and a custom tag that reads `manifest.json` from disk. Vite's hashing duplicates Django's, which DES-006 asked to avoid | Too much for one page with no interactivity. DES-006's *Future frontend tooling* is the way in if it's needed |
| Tailwind standalone CLI (`django-tailwind-cli`), no Node | Utility classes without npm | Still a build step: a binary download in Docker before `collectstatic`, in CI, and as a dev watcher. The generated CSS has to be either committed or built everywhere | Revisit if several pages start repeating layout code |
| Bootstrap from a CDN | Ready-made components, no build | Third-party request (privacy, CSP, availability), around 30 KB of CSS for one page, generic look, overriding it fights the brand | Goes against the no-third-party goal |
| Classless CSS (Pico, Water.css), vendored | Looks decent with nothing written | Its defaults have to be undone once the brand exists. Another file to keep updated | A small own stylesheet costs about as much and isn't thrown away later |
| Sass/SCSS | Variables, nesting, partials | Needs a compiler, which is a build step | Custom properties, native nesting and `@import … layer()` cover it |
| Several stylesheets per page from the start | Smaller per-page CSS | More `<link>` tags and more decisions with only one page | One file until it's large (see CSS conventions) |
| Google Fonts or another hosted font | Brand typography right away | Third-party request, privacy/GDPR questions, and a flash of unstyled text | System fonts now. Self-host when there's a brand font |
| No JS at all (wrapping nav only) | Nothing to test in a browser | No pattern for the first script that someone needs | One small, proven enhancement sets the pattern now |
| Templates in `works/templates/works/` | App-namespaced | The header, footer and base are site-wide, not part of `works`. `index.html` already lives in `templates/` | Project-level `templates/` for site chrome |

## Implementation Plan

On `feature/home-view`, which already has DES-006 merged in from `develop`. As
the backlog's merge rule requires, it reaches `develop` only through a reviewed
pull request.

DES-010 depends only on DES-002 (done) and DES-006 (merged). None of DES-005,
DES-003 or DES-008 depend on it. **Proposed place in the backlog's
*Implementation order*: a new step 2, right after DES-006 and before DES-005.**
The branch is already open. The only file it shares with DES-005 is
`works/tests.py`, which DES-005's formatting-only ruff commit then reformats
along with the rest of the code. If DES-005 goes first instead, rebase this
branch on it and run `ruff format` on the new tests.

- [ ] In `docs/backlog.md`, add a DES-010 row with status *Designed*, add
  DES-010 to *Implementation order* (above), and bump *Next free ID* to
  **DES-011**.
- [ ] Create `static/vae/css/`, `static/vae/js/` and `static/vae/img/`, and
  delete `static/.gitkeep`.
- [ ] Add `templates/base.html`, `templates/components/site_header.html` and
  `templates/components/site_footer.html`.
- [ ] Fill in `templates/index.html` with the sections above and marked
  placeholder copy.
- [ ] Add `static/vae/css/site.css`: layers, tokens, base, layout and
  components. Check every text/background token pair for 4.5:1 contrast.
- [ ] Add `static/vae/js/site.js` (the nav toggle) and the matching CSS.
- [ ] Add a placeholder `static/vae/img/favicon.svg`, for example the
  initials "VAE" on the accent colour.
- [ ] Add the tests below to `works/tests.py` as a new `HomePageTests(TestCase)`
  class, next to `SmokeTests` and DES-006's `StaticFilesTests`, and extend
  `test_manifest_build` as described.
- [ ] Add a short *Frontend* section to `README.md`, after DES-006's *Static
  files* section and linking to it rather than repeating it. It covers where
  templates, CSS and JS live, that there's no build step, and the
  no-inline-JS/CSS rule, and links to this doc.
- [ ] Do the manual checks below, and note the browsers and versions in the PR.

## Testing / Verification

**Automated (`uv run pytest`, and DES-005's CI once it lands)**

- `test_home_renders`: `GET /` returns 200. `index.html`, `base.html`,
  `components/site_header.html` and `components/site_footer.html` are all used.
- `test_home_skeleton`: the response contains `<html lang="en">`,
  `<main id="main"`, a skip link to `#main`, and exactly one `<h1`.
- `test_assets_linked_and_found`: the response references `vae/css/site.css`
  and `vae/js/site.js`, and `django.contrib.staticfiles.finders.find()` finds
  both files and `vae/img/favicon.svg`. This catches a renamed or missing asset
  in tests. It also covers the case plain test storage misses, where manifest
  storage on stage would return 500.
- `test_no_inline_script_or_style`: render `/` and assert there's no `<script>`
  without `src`, no `style="` attribute, and no `on…=` event attribute. This
  protects CSP-readiness.
- DES-006's existing `test_manifest_build` runs `collectstatic` over every
  finder. It already fails on a broken `url()` or `@import` in `site.css`, with
  no change. Extend it to also assert that `vae/css/site.<hash>.css` and its
  `.gz` exist, and that `vae/js/site.<hash>.js` exists. That proves the project
  assets go through the same pipeline as the admin's.
- The existing `SmokeTests` and `StaticFilesTests` still pass unchanged.

**Manual (local `runserver`)**

- Widths 320 px, 768 px and 1280 px: no horizontal scroll, the nav collapses
  under 40em and is inline above it, and text stays readable.
- Keyboard only: the first Tab shows the skip link, and Enter moves focus to
  `<main>`. Every link and button shows a visible focus ring. The nav toggle
  opens and closes with Enter and Space, `aria-expanded` updates, and Escape
  closes the menu and returns focus to the toggle.
- JavaScript disabled: the toggle isn't shown, and all nav links are visible
  and work.
- `prefers-reduced-motion: reduce` (DevTools rendering emulation): anchor links
  jump instead of smooth-scrolling.
- Lighthouse (mobile) or axe DevTools: no accessibility violations.
  Performance 95 or higher. The network panel shows only same-origin requests
  and under 30 KB transferred.
- The rendered HTML passes the W3C Nu validator with no errors.
- Checked in current Chrome, Firefox and Safari, including iOS Safari.
- `uv run python manage.py collectstatic --noinput` writes
  `staticfiles/vae/css/site.<hash>.css` and a `.gz` copy, and `git status`
  stays clean, because `staticfiles/` is gitignored.

**On stage (after DES-008)**

- `/` loads styled on the `run.app` URL. `site.css` and `site.js` are served
  from hashed URLs with `Cache-Control: max-age=315360000, public, immutable`.

## Open Questions

- **Is the no-build approach right, or should VAE match hl_main
  (Tailwind + Vite) from the start?** The recommendation is no build step for
  now. It's a one-way door only in the sense that pages written now would need
  their classes rewritten. Moving to Tailwind later means a new design that
  follows DES-006's *Future frontend tooling*.
- **Brand:** who provides the logo, colour palette and typeface? Until then the
  neutral placeholder tokens above are used. Changing them later should only
  touch the `tokens` layer.
- **Home page copy:** what are the mission statement, the *About* and *How it
  works* text, and the call to action? There's no sign-up yet, so the CTA goes
  to `#contact`.
- **Contact and footer:** which email address goes in the footer? Should the
  footer mention Hired Labs (for example "A Hired Labs project", with its
  nonprofit details as hl_main does)?
- **Front-end linting:** add djLint (templates), Stylelint (CSS) and Biome or
  ESLint (JS) to DES-005? djLint is a Python tool and fits `uv run`. The CSS and
  JS linters bring Node back into CI. Proposed: djLint only, as a DES-005
  follow-up.

- **Where does DES-010 go in the implementation order?** Proposed: step 2,
  after DES-006 and before DES-005 (see Implementation Plan). The alternative is
  to put it after DES-005, so `CI / checks` reviews its PR.

## Changelog

- 2026-11-10 — Created. `templates/index.html` is empty, `static/` doesn't exist, and there's no base template. Compared with hl_main's `frontend/` app (Tailwind 3, Vite 4, htmx, Alpine).
- 2026-11-10 — Revised after merging `develop`, which brought in DES-006 (PR #3) and the backlog's PR-only rule and implementation order. DES-006 is now treated as in place: per-environment storage table, the strict-manifest 500 risk, deleting `static/.gitkeep`, extending the existing `test_manifest_build`, and the README section placed after *Static files*. The `W004` claims are dropped (DES-006 fixed it). The JS-import note names the concrete storage subclass. Added a proposed implementation-order slot and the PR-only rule.

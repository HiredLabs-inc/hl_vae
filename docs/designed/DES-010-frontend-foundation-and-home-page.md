# DES-010: Frontend foundation and home page (HTML, CSS, JS)

- **Status:** Designed
- **Area:** Frontend
- **Created:** 2026-11-10
- **Updated:** 2026-11-11
- **Related:** branch `feature/home-view`. Uses the static-files setup from [DES-006](../archive/DES-006-static-files.md) (WhiteNoise, `static/vae/…`). Tests run in `CI / checks` from [DES-005](../archive/DES-005-ci-pipeline.md). Stage from [DES-008](../archive/DES-008-gcp-infrastructure.md).

## Summary

Minimal frontend boilerplate: one base template, one stylesheet with a simple
font and colour scheme, one empty vanilla JS file, and a placeholder home page
at `/`. Everything is plain static files, with no build step or framework.

## Motivation / Problem

- `/` returns 200 but renders a blank page, because `templates/index.html` is
  empty.
- There's no base template, CSS or JS, so every new page would start from
  nothing.

## Goals and Non-goals

**Goals**

- A `base.html` that every page extends, with a simple header and footer.
- A placeholder home page (hero only) that looks presentable on mobile and
  desktop.
- A starter stylesheet. Fonts and colours are CSS variables in one place, so
  they're easy to change later.
- A vanilla JS file wired into every page and ready for code.

**Non-goals**

- Final branding, logo or copy.
- Build tools, frameworks or npm (Tailwind, Vite, htmx, Alpine and so on).
  hl_main was a reference only. VAE is much simpler and doesn't need its
  frontend stack.
- Any JS behaviour, extra pages, forms or nav menus.

## Proposed Design

### Files

```
templates/
├── base.html          # new: page skeleton, header, footer
└── index.html         # filled in: hero, extends base.html

static/vae/
├── css/site.css       # new: variables + basic styles
└── js/site.js         # new: empty vanilla JS stub
```

`static/.gitkeep` is deleted, because `static/` now has real files. No settings,
URL or view changes are needed. `works.views.home_view` already renders
`index.html`, and DES-006 already serves `static/vae/…`.

### `base.html`

```django
<!DOCTYPE html>
{% load static %}
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Veteran Academic Exchange{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'vae/css/site.css' %}">
  <script src="{% static 'vae/js/site.js' %}" defer></script>
</head>
<body>
  <header class="site-header">
    <div class="container">
      <a class="brand" href="{% url 'index' %}">Veteran Academic Exchange</a>
    </div>
  </header>

  <main class="container">
    {% block content %}{% endblock %}
  </main>

  <footer class="site-footer">
    <div class="container">© {% now "Y" %} Veteran Academic Exchange</div>
  </footer>
</body>
</html>
```

There are two blocks, `title` and `content`. More can be added when a page
needs them.

### `index.html`

```django
{% extends "base.html" %}

{% block content %}
<section class="hero">
  <h1>Veteran Academic Exchange</h1>
  <p>Placeholder tagline. Replace when copy is ready.</p>
</section>
{% endblock %}
```

### `site.css`

The system font stack (no downloads) and a neutral placeholder palette. To
rebrand, change the variables in `:root`.

```css
:root {
  --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;

  --color-text: #1b2430;
  --color-muted: #4a5666;
  --color-bg: #ffffff;
  --color-bg-alt: #f4f6f8;
  --color-primary: #1f4e8c;

  --space: 1rem;
  --max-width: 60rem;
}

*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  font-family: var(--font-sans);
  line-height: 1.5;
  color: var(--color-text);
  background: var(--color-bg);
}

a { color: var(--color-primary); }

.container { max-width: var(--max-width); margin: 0 auto; padding: 0 var(--space); }

.site-header, .site-footer { background: var(--color-bg-alt); padding: var(--space) 0; }
.brand { font-weight: 700; text-decoration: none; }
.site-footer { color: var(--color-muted); font-size: 0.875rem; }

.hero { padding: calc(var(--space) * 4) 0; text-align: center; }
.hero h1 { font-size: clamp(2rem, 5vw, 3rem); margin: 0 0 var(--space); }
```

The text colours on both backgrounds meet WCAG AA contrast (4.5:1).

### `site.js`

```js
// Site-wide vanilla JS. Loaded with `defer` on every page.
// Pages must still work without it.
```

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| hl_main's stack (Tailwind + Vite + htmx + Alpine) | Matches hl_main | Needs Node, npm and a build step | Too much for VAE's scope |
| A CSS framework (Bootstrap, Pico) | Ready-made styles | Extra file to maintain, generic look | A small stylesheet is enough |
| Google Fonts | Nicer type now | Third-party request | System fonts are fine until there's a brand |

## Implementation Plan

- [ ] Add `templates/base.html` and fill in `templates/index.html`.
- [ ] Add `static/vae/css/site.css` and `static/vae/js/site.js`, and delete
  `static/.gitkeep`.
- [ ] Add the tests below to `works/tests.py`.
- [ ] In `docs/backlog.md`, add a DES-010 row and bump *Next free ID* to
  **DES-011**.
- [ ] Run the README's *Check your work before pushing* command, then open a
  PR into `develop`.

## Testing / Verification

**Automated (`uv run pytest`; `CI / checks` on the PR)**

- `test_home_uses_base_template`: `GET /` returns 200 and uses `index.html`
  and `base.html`.
- `test_assets_linked_and_found`: the page links `vae/css/site.css` and
  `vae/js/site.js`, and `django.contrib.staticfiles.finders.find()` finds both
  files. A missing file would otherwise only show up on stage, where it
  returns a 500.

**Manual**

- `uv run python manage.py runserver`: `/` shows the styled header, hero and
  footer, with no console errors.
- The page looks right at phone width (about 375 px) and on desktop.
- After the PR merges and is promoted to stage, `/` loads styled on the
  `run.app` URL.

## Open Questions

- Brand: logo, colours and font. The placeholders above are used until then.
- Home page copy: the tagline and anything beyond the hero.

## Changelog

- 2026-11-10 — Created, with a broad design compared against hl_main's frontend.
- 2026-11-10 — Revised after merging `develop`, which brought in DES-006.
- 2026-11-11 — Revised after merging `develop` up to PR #11 (DES-005, DES-003 and DES-008 done).
- 2026-11-11 — Rescoped to an MVP: hero-only home page, header and footer in `base.html` (no include files), a short stylesheet with system fonts and a neutral palette as variables, and an empty vanilla JS stub. Dropped the cascade layers, BEM conventions, nav toggle, accessibility and performance budgets, CSP rules, the README section and most of the tests.

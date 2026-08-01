# Frontend Changes: Light/Dark Theme Toggle

## Summary

Added a fixed, icon-based theme toggle button in the top-right corner that switches the app between the existing dark theme and a new light theme, with smooth transitions and full keyboard accessibility.

## Files Changed

### `frontend/index.html`
- Added a `<button id="themeToggle" class="theme-toggle">` as the first element in `<body>`, containing inline sun and moon SVG icons (`.icon-sun`, `.icon-moon`).
- Button includes `aria-label` (dynamically updated) and `aria-pressed` for screen reader support.
- Bumped cache-busting query params on `style.css` and `script.js` from `v=10` to `v=11`.

### `frontend/style.css`
- Added `:root[data-theme="light"]` block overriding the dark-theme CSS custom properties (`--background`, `--surface`, `--surface-hover`, `--text-primary`, `--text-secondary`, `--border-color`, `--assistant-message`, `--shadow`, `--welcome-bg`, `--welcome-border`) with light equivalents. The default (no attribute) remains the existing dark theme, so no visual change occurs until the user toggles.
- Added a shared `transition` rule (`background-color`, `color`, `border-color`, `box-shadow`, 0.3s ease) across the key surfaces (body, sidebar, chat areas, input, buttons, message bubbles, source chips) so switching themes animates smoothly instead of snapping.
- Added `.theme-toggle` styles: a fixed-position (`top-right`) circular button matching the existing surface/border/shadow aesthetic, with hover, active, and `:focus-visible` states (reusing `--focus-ring` for the focus outline, consistent with other interactive elements).
- Added crossfade + rotate animation between the sun and moon icons, driven by the `[data-theme="light"]` attribute selector (moon visible in dark mode, sun visible in light mode).
- Added a responsive rule shrinking the toggle button on small screens (`max-width: 768px`).

### `frontend/script.js`
- Added `themeToggle` to the cached DOM element references.
- Added `initializeTheme()`, called on `DOMContentLoaded`, which reads a saved preference from `localStorage` (`theme` key, defaulting to `dark`) and applies it.
- Added `toggleTheme()`, wired to the button's `click` event, which flips between `dark`/`light`, persists the choice to `localStorage`, and applies it.
- Added `applyTheme(theme)`, which sets `data-theme` on `document.documentElement` (driving the CSS overrides) and updates the button's `aria-label`/`aria-pressed` to reflect current state.

## Accessibility & Keyboard Navigation

- Implemented as a native `<button>`, so it's reachable via Tab and activates with Enter/Space by default — no extra keydown handling needed.
- `aria-label` toggles between "Switch to light mode" / "Switch to dark mode" so the accessible name always describes the next action.
- `aria-pressed` reflects current toggle state for assistive technologies.
- Visible focus ring (`:focus-visible`) matches the existing focus-ring styling used elsewhere in the app (inputs, suggested-question buttons).

## Persistence

Theme preference is stored in `localStorage` under the `theme` key and restored on page load, so the choice survives refreshes and new sessions.

## Manual Verification

Started the app from `backend/` via `uv run uvicorn app:app --port 8001` and confirmed via `curl` that the served `index.html`, `style.css`, and `script.js` include the new toggle markup, styles, and theme logic.

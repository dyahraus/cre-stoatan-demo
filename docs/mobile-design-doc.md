# Mobile-First Responsive Design — Warehouse Signal Frontend

## Context

The Warehouse Signal frontend has almost zero responsive design (only `lg:grid-cols-2` in one file). All pages are desktop-only with a 224px fixed sidebar, full-width tables, and absolute-positioned panels sized in pixels. The goal is a demo-perfect mobile experience on iPhone 14/15 Pro (~390px) without breaking the existing desktop UI.

**Strategy:** Mobile-first Tailwind — default styles target phones, `md:` (768px+) for tablets, `lg:` (1024px+) for desktop. No new dependencies.

---

## Phase 1: Layout Shell — Sidebar to Bottom Tab Bar

> Foundation that all other phases depend on.

### `src/app/layout.tsx`

- Change outer div: `flex h-screen` → `flex flex-col md:flex-row h-screen`
- Change main: `p-6` → `p-4 pb-20 md:p-6 md:pb-6` (pb-20 reserves space for mobile tab bar)

### `src/components/layout/sidebar.tsx`

Render **both** a desktop sidebar and a mobile bottom tab bar, toggled via Tailwind `hidden`/`md:flex`:

- Desktop `<aside>`: Add `hidden md:flex` to existing classes
- New mobile `<nav>`: Fixed bottom bar with 3 tab items
  - `fixed bottom-0 left-0 right-0 z-50 flex md:hidden`
  - `border-t border-zinc-800 bg-zinc-950/95 backdrop-blur-md`
  - Each tab: `flex-1 flex flex-col items-center justify-center py-3 min-h-[56px]`
  - Inline SVG icons (globe, radar, map-pin) — no icon library needed
  - Active state: `text-blue-400`, inactive: `text-zinc-500`
  - Stats section stays desktop-only (inside `<aside>`)
- Wrap both in `<>...</>`

### `src/app/globals.css`

Add one keyframe for bottom sheet animation:
```css
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
```

---

## Phase 2: Market Tracker — Globe + Bottom Sheet

> Highest complexity, most visual impact.

### `src/app/tracker/page.tsx`

**Negative margin fix** (must match Phase 1 padding):
- `-m-6` → `-m-4 -mb-20 md:-m-6 md:-mb-6`

**Header overlay:**
- Padding: `px-4 py-4 md:px-8 md:py-6`
- Title text: `text-lg md:text-xl`
- Subtitle: `text-[10px] md:text-[11px]`
- Reset button: `px-4 py-3 md:px-5 md:py-2` (44px+ touch target)

**Side panel → bottom sheet on mobile:**
- Mobile: `inset-x-0 bottom-0 h-[55vh]` with `rounded-t-2xl`, `animate-[slideUp_0.4s_ease-out]`
- Desktop: `md:h-auto md:inset-x-auto md:right-0 md:top-0 md:bottom-0 md:w-80 md:rounded-none md:animate-[slideInRight_0.6s_ease-out]`
- Background gradient: vertical on mobile, horizontal on desktop
- Padding: `pt-4 md:pt-20 p-5`
- Add drag handle pill (`w-10 h-1 rounded-full bg-zinc-600`) visible only on mobile (`md:hidden`)

**Bottom status bar:** Add `hidden md:flex` (hide on mobile, panel covers it)

**Globe prompt "Click to explore":** Move up to `bottom-24 md:bottom-20` to clear tab bar

### `src/components/tracker/tracker-globe.tsx`

**Touch support:**
- Add `onTouchStart` handler alongside existing `onMouseMove` — find nearest marker within 40px radius (larger than 30px mouse radius)
- Add `onTouchEnd` handler — clear hover after 2s delay
- Add `touch-none` class or `style={{ touchAction: "none" }}` to globe container to prevent scroll interference

### `src/components/tracker/tracker-tooltip.tsx`

**Edge clamping:** Clamp tooltip x/y so it doesn't clip off-screen edges:
- `left: Math.max(80, Math.min(marker.x, windowWidth - 80))`
- `top: Math.max(40, marker.y - 16)`

---

## Phase 3: Deal Radar — Filters + Table-to-Cards

### `src/components/radar/radar-filters.tsx`

**Collapsible filter panel on mobile:**
- Add `useState(false)` for `open` toggle
- Mobile toggle button: `flex md:hidden` — full-width button reading "Filters" with show/hide text
  - Styled: `px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-300`
- Filter container: `${open ? "grid" : "hidden"} md:flex flex-wrap gap-3 items-end grid-cols-2`
- All input/select widths: `w-full md:w-{original}` (e.g., `w-full md:w-24`, `w-full md:w-44`)

### `src/components/radar/radar-table.tsx`

**Dual render — table on desktop, cards on mobile:**
- Wrap existing `<Table>` in `<div className="hidden md:block">`
- Add mobile card list: `<div className="md:hidden space-y-3">`
  - Each card: `<Link>` wrapping full card → `/company/{ticker}`
  - Card layout: `p-4 bg-zinc-900 border border-zinc-800 rounded-lg active:bg-zinc-800`
  - Row 1: rank number + ticker (blue-400 mono) + company name (truncated) + ScoreBadge
  - Row 2: MoveTypeBadge + TimeHorizonBadge + SignalFlags
  - Row 3 (conditional): geography badges

### `src/app/radar/page.tsx`

- Heading: `text-xl md:text-2xl`

---

## Phase 4: Geography — Table-to-Cards

### `src/components/geography/geo-table.tsx`

**Same dual-render pattern as Phase 3:**
- Desktop: `<div className="hidden md:block">` wrapping existing table
- Mobile cards: `<div className="md:hidden space-y-3">`
  - Each card: `p-4 bg-zinc-900 border border-zinc-800 rounded-lg`
  - Row 1: region name + company count
  - Row 2: Avg ScoreBadge + Max ScoreBadge
  - Row 3: ticker links with `py-1` for touch targets

### `src/app/geography/page.tsx`

- Heading: `text-xl md:text-2xl`

---

## Phase 5: Company Detail — Responsive Polish

### `src/app/company/[ticker]/page.tsx`

- Back link: add `py-2` for touch target (already uses `grid-cols-1 lg:grid-cols-2`)

### `src/components/company/score-panel.tsx`

- Header: `flex items-start justify-between gap-2` (allow wrapping)
- Title: `text-lg md:text-xl`

### `src/components/company/extraction-table.tsx`

**Dual render (same pattern):**
- Desktop: existing table in `hidden md:block`
- Mobile: cards showing transcript key, relevance/expansion/move badges, evidence quote (line-clamp-2)

### `src/components/company/evidence-list.tsx`

- Blockquote padding: `pl-2 md:pl-3`

---

## Files Modified (complete list)

| Phase | File | Change |
|-------|------|--------|
| 1 | `src/app/layout.tsx` | Flex direction + responsive padding |
| 1 | `src/components/layout/sidebar.tsx` | Desktop sidebar + mobile bottom tab bar |
| 1 | `src/app/globals.css` | `slideUp` keyframe |
| 2 | `src/app/tracker/page.tsx` | Negative margins, bottom sheet, responsive header |
| 2 | `src/components/tracker/tracker-globe.tsx` | Touch handlers, touch-action |
| 2 | `src/components/tracker/tracker-tooltip.tsx` | Edge clamping |
| 3 | `src/components/radar/radar-filters.tsx` | Collapsible mobile filter panel |
| 3 | `src/components/radar/radar-table.tsx` | Table→card dual render |
| 3 | `src/app/radar/page.tsx` | Responsive heading |
| 4 | `src/components/geography/geo-table.tsx` | Table→card dual render |
| 4 | `src/app/geography/page.tsx` | Responsive heading |
| 5 | `src/app/company/[ticker]/page.tsx` | Touch-friendly back link |
| 5 | `src/components/company/score-panel.tsx` | Header flex + font size |
| 5 | `src/components/company/extraction-table.tsx` | Table→card dual render |
| 5 | `src/components/company/evidence-list.tsx` | Responsive padding |

## Files NOT Changed

- `src/components/ui/*` — All shadcn primitives untouched
- `src/lib/*` — All types, API, utils, format untouched
- `src/components/shared/*` — Badges already compact and responsive
- `src/components/tracker/tracker-panel.tsx` — Unused, can delete later
- `src/components/tracker/location-panel.tsx` — Works in both panel and sheet context, no changes

## Known Considerations

1. **`-m-4 -mb-20` math** — Tracker page negative margins must exactly cancel layout padding. Test this first.
2. **55vh bottom sheet** — Works on iPhone 14/15 Pro (844px). iPhone SE (667px) may feel tight. Acceptable for demo.
3. **Dual DOM rendering** — Cards + table both in DOM. Fine for demo data volumes (<50 rows).
4. **Radix Select on mobile** — Popover may need testing. Should work with shadcn defaults.
5. **touch-action: none** on globe — Prevents scroll/zoom gestures on the canvas. Required so touch events work for marker interaction.

## Verification

1. `npm run build` — must compile with zero errors after each phase
2. Desktop regression: sidebar visible, tables intact, tracker panel on right at `lg:` width
3. Mobile testing (Chrome DevTools → iPhone 14 Pro, 393x852):
   - Bottom tab bar visible, all 3 tabs navigate correctly
   - Tracker: globe fills screen, tap zooms in, bottom sheet slides up, markers touchable
   - Radar: filter toggle works, card list renders, cards link to company detail
   - Geography: card list renders with Midwest-only regions
   - Company detail: single column, back link tappable, extraction cards readable
4. Touch targets: verify all interactive elements are >= 44px

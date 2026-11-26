# Lens — Design
> warm alabaster paper with cobalt primary actions

**Theme:** light-first (charcoal darkroom companion)

Source of truth is CSS variables in `../frontend/src/globals.css`. Hex values below are normalized readings of those tokens for humans. Code conventions stay in [backend coding style](BACKEND-CODING-STYLE.md) and [frontend coding style](FRONTEND-CODING-STYLE.md); this file is the visual contract for any admin UI.

Lens is an operations console for LLM routing and observability, not a consumer chat client or marketing page. The canvas is an airy warm alabaster (`#F9F8F5`) paired with soft paper cards (`#FCFBF8`), quiet oat-stone wells (`#EEEDE7`), and a subtle warm linen sidebar (`#F3F2EE`). Core typography relies on deep warm obsidian ink (`#24231E` in light, `#F3F2ED` in dark), while primary committing actions, switches, focus rings, and selection highlights use the Lens mark cobalt (`#2563EB`, matching `logo.svg`). Structure comes from 1px pencil hairlines (`#E5E4DE`) and gentle surface shifts. Chromatic color is reserved for primary actions (`--primary`), the Lens mark (`logo.svg`), and data visualizations (`--chart-*`). Typography is Geist for UI and Geist Mono for identifiers, versions, and JSON.

## Colors

Use the CSS variable in code. Hex values are normalized light/dark readings.

| Name | Variable | Light | Dark | Role |
|------|----------|-------|------|------|
| Alabaster Paper | `--background` | `#F9F8F5` | `#141412` | Page canvas, workspace backdrop |
| Soft Paper | `--card` | `#FCFBF8` | `#1B1B18` | Stat cards, table shells, login frame |
| Pure Pill | `--pure` | `#FFFFFF` | `#2A2A26` | Active segmented/tab pills |
| Linen Rail | `--sidebar` | `#F3F2EE` | `#191917` | Navigation sidebar rail |
| Obsidian Ink | `--foreground` | `#24231E` | `#F3F2ED` | Body copy, table values, primary labels |
| Deep Carbon | `--card-foreground` | `#171612` | `#FAF9F5` | Headings, stat values, active nav text |
| Lens Cobalt | `--primary` | `#2563EB` | `#2563EB` | Primary committing buttons, switches, active fills (matches `logo.svg`) |
| Primary Paper | `--primary-foreground` | `#FCFBF8` | `#FCFBF8` | Text on primary fills |
| Cobalt Ring | `--ring` | `#2563EB` | `#2B7FFF` | Keyboard focus ring |
| Oat Well | `--muted` | `#EEEDE7` | `#252521` | Secondary buttons, inset wells, track fills |
| Graphite | `--muted-foreground` | `#717069` | `#9B9A93` | Captions, table headers, pagination, placeholders |
| Mist Wash | `--accent` | `#ECEBE4` | `#2A2A26` | Hover wash, active table row wash |
| Hairline | `--border` | `#E5E4DE` | `white/10` | 1px structural borders |
| Field Line | `--input` | `#D4D3CC` | `white/15` | Input border (`border-input/60`) |
| Alarm | `--destructive` | `#D1382C` | `#EE6C5E` | Delete/confirm danger; never a large fill |
| Chart 1–5 | `--chart-1` … `--chart-5` | `#93B4F5` … `#1D449E` | `#93B4F5` … `#3B6FD9` | Overview charts only; optical cobalt ramp matching `logo.svg` |

Destructive UI is a tint, not a billboard: `bg-destructive/10 text-destructive`. Success has no dedicated brand green — status is copy, badges, and table cells.

## Typography

### Geist Variable — UI family for every dashboard surface. Weight 400 for prose and table cells, 500 for buttons and labels, 600 for section titles and stat values. No second sans and no display serif in the admin chrome.

- **Substitute:** Geist, then `ui-sans-serif, system-ui`
- **Weights:** 400, 500, 600
- **Sizes in use:** 11, 12, 13, 14, 15, 16, 18
- **Line height:** 1.25 on titles, 1.25rem (20px) on `text-xs` cells
- **Features:** `antialiased`; `tabular-nums` on money, counts, latency

### Geist Mono Variable — Identifiers only: model names, JSON, IDs, versions, HTTP codes. Never body copy.

### Type Scale

| Role | Token | Weight | Size | Line Height | Where |
|------|-------|--------|------|-------------|-------|
| micro | `text-[11px]` | 500 | 11px | 1 | Table headers, version chips |
| caption | `text-xs` | 400 | 12px | 20px | Table cells, dialog description, pagination, field hints |
| label | `text-xs` / `text-sm` | 400–500 | 12–14px | 1–1.25 | Field labels (`text-xs font-normal text-muted-foreground` in dense forms) |
| body | `text-sm` | 400 | 14px | 20px | Dialogs, settings copy, buttons, nav items |
| title | `.page-title` / `text-base font-semibold` | 600 | 16px | 22px | Top-level view headings |
| section | `.page-section-title` / `text-sm font-semibold` | 600 | 14px | 20px | Overview blocks, dialog title, settings section |
| stat | `text-base md:text-lg font-semibold tabular-nums` | 600 | 16–18px | 1.25 | Overview metric value |
| display | — | — | — | — | Not used. This is not a marketing type system. |

Page titles stay at `text-base` (16px) with tight `-0.015em` tracking — never 24–64px marketing heroes.

## Spacing & Layout

**Base unit:** 4px (Tailwind), with an 8px rhythm on page sections.

**Density:** compact

- **Shell:** quiet warm linen sidebar + `SidebarInset` on alabaster paper; header `min-h-12` with bottom hairline `border-border/50`, horizontal padding `px-4 sm:px-6 lg:px-8`
- **List pages:** `space-y-4`, toolbar `min-h-10`, pagination flush under the table
- **Settings:** section `space-y-4 md:space-y-5 xl:space-y-6`; field rows stack on small screens, label/control split on `md+`
- **Dialog padding:** `p-5`, inner gap `gap-4`
- **Table cell:** `px-3 py-2.5`; header row `h-8 px-3 py-1.5`

### Border Radius

`--radius` is `0.5rem` (8px). Derived tokens:

| Token | Value | Use |
|-------|-------|-----|
| `rounded-sm` | 4px | Avoid in new UI |
| `rounded-md` | 6px | Inputs, inset wells |
| `rounded-lg` | 8px | Buttons, sidebar items, dialogs |
| `rounded-xl` | 12px | Stat cards, table shells, menus/popovers |
| `rounded-2xl` | 16px | Centered login container |
| `rounded-3xl` | ~18px | Floating sheets |
| `rounded-full` / `rounded-4xl` | pill | Badges, tab lists, segmented controls |

## Components

Reuse the primitives in `../frontend/src/components/ui`. Do not restyle a one-off copy.

### Primary Button
**Role:** One committing action per view or footer

`variant="default"` `size="sm"` in dialogs/sheets (`h-7`), `size="default"` (`h-8`) in page toolbars. `rounded-lg`, Lens cobalt fill (`bg-primary`), `text-sm font-medium`, no shadow. Ghost or secondary cancel sits to its left.

### Secondary & Ghost Buttons
- **Secondary:** `bg-secondary text-secondary-foreground` (`#EEEDE7` oat fill, no border) for subtle pill/button actions.
- **Ghost:** Transparent, `hover:bg-muted hover:text-foreground`, `shadow-none`. Pagination chevrons are `size="icon-sm"` forced to `h-5 w-5` with `stroke-1` icons.
- **Outline:** `border-input/60`, transparent/soft fill, hover muted.

### Destructive Button
**Role:** The button that commits a delete or overwrite

`bg-destructive/10 text-destructive`, not a solid red slab. Pair with ghost Cancel in a right-aligned footer.

### Compact Table Pagination
**Role:** Every paged list (channels, groups, requests, health, prices)

Left: `共 N 条，第 X / Y 页` / `N items, page X / Y`. Right: ghost prev, ghost page-size **dropdown** (not a native `<select>`), ghost next. Container: `text-xs font-normal text-muted-foreground`. Use `TablePagination` from `Pagination.tsx`.

### Data Table Shell
**Role:** Tabular data

`Table` paints `rounded-xl border border-border/70 bg-card`. Header `text-[11px] font-medium text-muted-foreground` on `bg-muted/45`. Cells `text-xs` / `text-sm`. Do **not** wrap `Table` in another `rounded-md border`.

### Soft Paper Wells & Cards
- **Quiet Well (`Card` / `OverviewStatCard` / charts):** `rounded-xl bg-muted/55`, no extra border, `shadow-none`. Lets warm alabaster and oat tones separate content effortlessly without boxy borders.
- **Inset well:** `rounded-md bg-muted/45`, no border, `shadow-none`. Used for nested form blocks, empty states, and expanded code/JSON previews.

### Dialog & Sheet Panels
- **Dialog:** Overlay `bg-black/50`. Panel `rounded-lg border border-border/70 bg-background/96 p-5 shadow-xl backdrop-blur`, default `sm:max-w-[560px]`. Footer right-aligned, default buttons forced to `h-7`.
- **Sheet (Inspector Drawer):** Overlay `bg-black/45`. Edge-docked architectural drawer (`inset-y-0 right-0 h-dvh border-l border-border/75 bg-background shadow-2xl`, `sm:max-w-[540px]`–`[620px]`). Structured `border-b` header (`px-6 py-4`) and `border-t` footer (`px-6 py-3.5`) with comfortable `h-8` actions.

### Editor Form & Member Layout
- Group primary configuration fields into a quiet `rounded-xl bg-muted/50 p-4` card using a 2-column grid for paired choices (e.g., Group Type + Routing Strategy, Channel Name + Tags) and inline hint tooltips (`SettingsHint`) instead of stacked prose blocks.
- Render member lists and setting sections inside crisp `rounded-xl border border-border/70 bg-card` containers with `size="sm"` switches on dense rows.

### Field & Badge & Segmented Controls
- **Input:** `h-8 rounded-md border-input/60 bg-card/60 text-xs shadow-none`, focus `border-primary/60 ring-[1px] ring-primary/40`.
- **Badge:** `h-5 rounded-4xl text-xs`. Default Lens cobalt (`bg-primary`), secondary `bg-muted text-muted-foreground`, outline hairline.
- **Segmented / Tabs track:** `rounded-full bg-muted/55 p-1`. Active item uses `bg-pure text-pure-foreground ring-1 ring-border/50`.

### Tooltip
Always `Tooltip` from `@/components/ui/Tooltip` (`TooltipTrigger asChild` + `TooltipContent`); never the native `title` attribute.

## Do's and Don'ts

### Do
- Keep primary actions in crisp Lens cobalt (`--primary`, `#2563EB`), letting warm alabaster surfaces and obsidian typography carry the calm instrument feel.
- Frame tabular data with `rounded-xl border border-border/70 bg-card` and quiet stat/chart wells with borderless `rounded-xl bg-muted/55`.
- Keep Login open and borderless on the `--background` paper canvas (centered `max-w-[348px]`, no card wrapper).
- Use `TablePagination` for every paged list, including page size as a ghost dropdown.
- Use Geist Mono for IDs, JSON, versions, and model names; Geist for everything else.

### Don't
- Don't wrap `Table` in a second bordered card.
- Don't add drop shadows to stats, tables, or settings sections. Shadows belong on popovers (`shadow-xs`), dialogs (`shadow-xl`), and sheets (`shadow-2xl`) only.
- Don't introduce heavy saturated primary button fills or warm-brown muddiness across chrome.
- Don't use the native `title` attribute for hover hints or truncated text; use `Tooltip`.
- Don't color row-level delete actions red unless they are the final confirm button committing deletion.

## Imagery

No photography, no illustration, no decorative gradients. The mark is `logo.svg` on paper. Vendor identity is the small monochrome glyphs in `../frontend/public/brand-icons/` inside table/group rows. Lucide icons at `size-3.5`–`size-4`; use `stroke-1` on compact chrome. Charts stay in the optical `--chart-*` cobalt-slate family.

# Lens — Design
> warm paper console with indigo ink

**Theme:** light-first (dark companion)

Source of truth is CSS variables in `frontend/src/globals.css`. Hex values below are normalized readings of those tokens for humans. Roles and recommendations are interpreted. HTML examples are reconstructions, not source components. Code conventions stay in [STYLING.md](STYLING.md); this file is the visual contract for any new admin UI.

Lens is an operations console, not a marketing site. The canvas is a warm off-white (`#f8f8f6`) instead of sterile SaaS white. Structure comes from 1px hairlines at `border/60` and quiet `muted/35` wells — not from drop shadows or filled cards. The only chromatic action color is indigo (`#1447e6`): primary buttons, focus rings, and selected text. Almost everything else is ink and paper. Typography is Geist for UI, Geist Mono for identifiers and JSON. Density is compact: 28–32px controls, 12px table type, 20px pagination chevrons. The feel is an instrument panel printed on warm paper — closer to Linear than to a landing page.

## Colors

Use the CSS variable in code. Hex is the light-theme reading.

| Name | Variable | Light | Dark | Role |
|------|----------|-------|------|------|
| Paper | `--background` | `#f8f8f6` | `#0c0a09` | Page canvas, dialog panel, table shell fill |
| Ink | `--foreground` | `#3d3929` | `#fafaf9` | Body, table values, primary labels |
| Heavy Ink | `--card-foreground` | `#141413` | `#fafaf9` | Stronger headings inside wells |
| Indigo | `--primary` | `#1447e6` | `#193cb8` | Primary actions, focus ring, text selection |
| Indigo Ink | `--primary-foreground` | `#eff6ff` | `#eff6ff` | Text on primary fills |
| Sand | `--muted` | `#ede9de` | `#292524` | Well recipe base (`bg-muted/35`), secondary fills |
| Graphite | `--muted-foreground` | `#83827d` | `#a6a09b` | Captions, table headers, pagination, placeholders |
| Mist | `--accent` | `#efeeeb` | `#292524` | Table header wash, hover wash |
| Hairline | `--border` | `#d7d7d5` | `white/10` | Borders at `/60` on shells; `/40` on inputs |
| Field Line | `--input` | `#b4b2a7` | `white/15` | Input border (`border-input/40`) |
| Alarm | `--destructive` | `#e7000b` | `#ff6467` | Delete/confirm danger; never a large fill |
| Sidebar Paper | `--sidebar` | `#f7f7f5` | `#1c1917` | Navigation rail |
| Chart 1–5 | `--chart-1` … `--chart-5` | `#8ec5ff` … `#193cb8` | same | Overview charts only; indigo family, not a second brand |

Destructive UI is a tint, not a billboard: `bg-destructive/10 text-destructive`. Success has no dedicated brand green — status is copy, badges, and table cells.

## Typography

### Geist Variable — UI family for every dashboard surface. Weight 400 for prose and table cells, 500 for buttons and labels, 600 for section titles and stat values. No second sans. Do not introduce Inter, system-ui as a design choice, or a display serif in the admin chrome.

- **Substitute:** Geist, then `ui-sans-serif, system-ui`
- **Weights:** 400, 500, 600
- **Sizes in use:** 11, 12, 14, 16, 18
- **Line height:** 1.25 on titles, 1.25rem (20px) on `text-xs` cells
- **Features:** `antialiased`; `tabular-nums` on money, counts, latency

### Geist Mono Variable — Identifiers only: model names, JSON, IDs, HTTP codes. Never body copy.

### Noto Serif Variable — Mapped as `--font-heading`. Do not use it for dashboard chrome. The admin voice is sans.

### Type Scale

| Role | Token | Weight | Size | Line Height | Where |
|------|-------|--------|------|-------------|-------|
| micro | `text-[11px]` | 500 | 11px | 1 | Table headers |
| caption | `text-xs` | 400 | 12px | 20px | Table cells, dialog description, pagination, field hints |
| label | `text-xs` / `text-sm` | 400–500 | 12–14px | 1–1.25 | Field labels (`text-xs font-normal text-muted-foreground` in dense forms) |
| body | `text-sm` | 400 | 14px | 20px | Dialogs, settings copy, buttons |
| title | `text-sm font-semibold` | 600 | 14px | 20px | Page `h3`, dialog title, settings section |
| stat | `text-base md:text-lg font-semibold tabular-nums` | 600 | 16–18px | 1.25 | Overview metric value |
| display | — | — | — | — | Not used. This is not a marketing type system. |

Page titles in the dashboard are `text-sm font-semibold`, not 24–64px heroes. If a screen needs more presence, raise weight or add a one-line `text-xs text-muted-foreground` description — do not invent a display size.

## Spacing & Layout

**Base unit:** 4px (Tailwind), with an 8px rhythm on page sections.

**Density:** compact

- **Shell:** sidebar + `SidebarInset`; header `min-h-12`, horizontal padding `px-4 sm:px-6 lg:px-8`
- **List pages:** `space-y-3`, toolbar `min-h-10`, pagination flush under the table
- **Settings:** section `space-y-4 md:space-y-5 xl:space-y-6`; field rows stack on small screens, label/control split on `md+`
- **Dialog padding:** `p-5`, inner gap `gap-4`
- **Table cell:** `px-3 py-2.5`; header row `h-8 px-3 py-1.5`

### Border Radius

`--radius` is `0.5rem` (8px). Derived tokens:

| Token | Value | Use |
|-------|-------|-----|
| `rounded-sm` | 4px | Avoid in new UI |
| `rounded-md` | 6px | Wells, cards, inputs, sidebar items |
| `rounded-lg` | 8px | Buttons, dialogs, **table shells** |
| `rounded-xl` | 12px | Menus/popovers only — not wells or cards |
| `rounded-3xl` | ~18px | Floating sheets |
| `rounded-full` / `rounded-4xl` | pill | Badges, tab lists |

## Components

Reuse the primitives in `frontend/src/components/ui`. Do not restyle a one-off copy.

### Primary Button
**Role:** One committing action per view or footer

`variant="default"` `size="sm"` in dialogs/sheets (`h-7`), `size="default"` (`h-8`) in page toolbars. `rounded-lg`, indigo fill, `text-sm font-medium`, no shadow. Ghost cancel sits to its left.

### Ghost Button
**Role:** Cancel, icon actions, pagination, toolbar

Transparent, `hover:bg-muted hover:text-foreground`, `shadow-none`. Pagination chevrons are `size="icon-sm"` forced to `h-5 w-5` with `stroke-1` icons.

### Outline Button
**Role:** Secondary action that still needs a box

`border-input/40`, transparent fill, hover muted. Prefer ghost in compact footers.

### Destructive Button
**Role:** Delete / overwrite confirm

`bg-destructive/10 text-destructive`, not a solid red slab. Pair with ghost Cancel in a right-aligned footer.

### Compact Table Pagination
**Role:** Every paged list (channels, groups, requests, health, prices)

Left: `共 N 条，第 X / Y 页` / `N items, page X / Y`. Right: ghost prev, ghost page-size **dropdown** (not a native `<select>`), ghost next. Container: `text-xs font-normal text-muted-foreground`. Use `TablePagination` from `Pagination.tsx`. Numbered page-link chrome is not this product.

### Data Table Shell
**Role:** Tabular data

`Table` already paints `rounded-lg border border-border/60 bg-background`. Header `text-[11px] font-medium text-muted-foreground` on `--accent`. Cells `text-xs`. Do **not** wrap `Table` in another `rounded-md border`. Height clipping is `max-h-* overflow-y-auto` only.

### Muted Well
**Role:** Stats, settings groups, nested form groups, empty JSON, success result panels

`rounded-md bg-muted/35`, no extra border, `shadow-none`. Hover on interactive wells may go `bg-muted/50`. Do not use `bg-muted/20`, `/25`, `/30`, or `/45`.

### Confirm Dialog
**Role:** Delete, overwrite, bulk destroy

Same dialog chrome. Title `text-sm font-semibold`, description `text-xs text-muted-foreground` (put the target name in the description). Footer `justify-end gap-2`, ghost Cancel + destructive Action at `h-7`. No bordered name-card. No stacked full-width buttons.

### Dialog Panel
**Role:** Create/edit/import/test

Overlay `bg-black/50`. Panel `rounded-lg border border-border/60 bg-background/96 p-5 shadow-xl backdrop-blur`, default `sm:max-w-[560px]`. Footer right-aligned, default buttons forced to `h-7`.

### Sheet Panel
**Role:** Channel editor, group editor, API key editor, request detail

Overlay `bg-black/50`. Floating inset sheet, `rounded-3xl`, `border-border/60 bg-background/96 backdrop-blur`, `shadow-2xl`. Title `text-sm font-semibold`, description `text-xs`. Footer `justify-end gap-2` (status text may sit on the left in group editor).

### Field
**Role:** Form controls

Input `h-8 rounded-md border-input/40 bg-transparent text-xs shadow-none`, focus `border-primary/60 ring-[1px] ring-primary/40`. Labels are quiet: in dense editors `text-xs font-normal text-muted-foreground`.

### Badge
**Role:** Protocol, status, count

`h-5 rounded-4xl text-xs`. Default indigo, secondary `bg-muted text-muted-foreground`, outline hairline. Status is a badge plus copy — not a colored card.

### Tab List
**Role:** Settings sections

Pill track `rounded-full bg-muted/40 p-1`. Active tab is the only filled chip.

### Overview Stat
**Role:** Dashboard metric family

Muted well, caption `text-xs text-muted-foreground` with a 16px icon at `text-foreground/55`, value `font-semibold tabular-nums`. Optional 4px dots to cycle views.

### List Toolbar
**Role:** Search / filter / sort / refresh on list pages

`min-h-10`, ghost `h-8` tools, `text-xs text-muted-foreground`, icons `size-3.5 stroke-1`. Search field on `md+`; icon popover on small screens.

## Do's and Don'ts

### Do
- Put indigo only on the committing control, focus ring, and selection — never on page backgrounds or table shells.
- Define data with `rounded-lg border-border/60` table shells and `rounded-md bg-muted/35` wells.
- Set dashboard titles at `text-sm font-semibold`; put explanation in `text-xs text-muted-foreground`.
- Use `TablePagination` for every paged list, including page size as a ghost dropdown.
- Keep dialog/sheet overlays at `bg-black/50` and panels at `bg-background/96` + `backdrop-blur`.
- Put confirm actions in a compact `justify-end gap-2` footer at `h-7`.
- Use Geist Mono for IDs, JSON, and model names; Geist for everything else.
- Prefer existing `Button` / `Table` / `Dialog` / `Sheet` / `Card` primitives over new class recipes.

### Don't
- Don't wrap `Table` in a second bordered card (`rounded-md border` around the table).
- Don't use a native `<select>` for page size, and don't use numbered `PaginationLink` chrome on admin lists.
- Don't ship `rounded-xl` wells or the default shadcn Card (`rounded-xl border bg-card py-6 shadow-sm`).
- Don't mix well opacities (`bg-muted/20`–`/45`); the well is `/35`.
- Don't put the delete target in a bordered name-card with oversized stacked Cancel/Delete.
- Don't add drop shadows to wells, tables, or settings sections. Shadows belong on dialogs (`shadow-xl`) and sheets (`shadow-2xl`) only.
- Don't introduce a second accent (orange, yellow, mint) or a marketing display size.
- Don't use solid destructive fills or green “success cards”; failure wells may add `border-destructive/40`, success wells stay `bg-muted/35`.

## Elevation

Most of the console is flat. Wells and cards are `shadow-none`. Tables are a 1px `border/60` on paper. The only lifted layers are:

1. **Popover / menu** — `shadow-xs`, `rounded-xl`, opaque popover fill
2. **Dialog** — `shadow-xl` + blur on `background/96`
3. **Sheet** — `shadow-2xl` on a floating `rounded-3xl` panel

If a block needs to read as “a thing”, use a well or a table shell. Do not raise `box-shadow` to fake a card.

## Surfaces

- **Paper page** (`--background`) — Dashboard canvas, table interior, login
- **Sidebar paper** (`--sidebar`) — Navigation rail, slightly separate from the page
- **Sand well** (`bg-muted/35`) — Stats, nested groups, empty states, success results
- **Frosted panel** (`bg-background/96` + `backdrop-blur`) — Dialogs and sheets
- **Opaque popover** (`--popover`) — Dropdowns and selects
- **Indigo fill** (`--primary`) — Primary buttons only
- **Alarm tint** (`bg-destructive/10`) — Danger actions and failed result wells

## Imagery

No photography, no illustration, no decorative gradients. The mark is `logo.svg` (and optional custom `logo_url`) on paper. Vendor identity is the small monochrome glyphs in `frontend/public/brand-icons/` inside table/group rows — not logo clouds. Lucide icons at `size-3.5`–`size-4`; use `stroke-1` on compact chrome (pagination, toolbars). Charts stay in the indigo `--chart-*` family.

## Layout

Authenticated UI is a **sidebar + inset**: first-level nav of operational pages, compact header (GitHub, theme, locale), then a single scrolling column. The product name sits in the sidebar with the version beside it. Sidebar footer shows the account name and a ghost sign-out control. List screens are title row → toolbar → table shell → compact pagination. Settings screens are a title row and stacked fields, not cards in a grid. Login is a centered column, max width ~360px, no card, `h-9` fields, full-width primary.

Do not build split marketing heroes, 24px-radius sticky-note cards, or max-width 1200px editorial bands. This product is a dense console.

## Similar Brands

- **Linear** — Compact hairline tables, muted wells, one accent, no decorative shadow on content
- **Vercel dashboard** — Geist, warm neutrals, indigo/blue as the only action color, `text-sm` page titles
- **Raycast** — Geist, dense controls, blur panels over a quiet canvas
- **shadcn/ui admin** — Token names and primitives; Lens restyles them toward paper wells instead of elevated cards

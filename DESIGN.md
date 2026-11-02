# Design direction

Working notes for the frontend revamp, so every page stays one product instead of
a pile of components.

## Personality

A neighbourhood rental desk that is quick, warm and a little cheeky. Confident, not
corporate. It should look like someone who likes cars built it, not like a dashboard
template.

## Palette

| Token | Value | Use |
|---|---|---|
| `--ink` | `#16211c` | Text, header, table heads |
| `--paper` | `#f6f1e7` | Page background |
| `--surface` | `#fffdf8` | Cards, forms |
| `--line` | `#ded4c3` | Borders, dividers |
| `--brand` | `#d9482b` | Primary buttons, links, accents |
| `--sun` | `#f4b740` | Highlights, prices, focus glow |
| `--teal` | `#1f6f5c` | Secondary details, success |

Coral and sun on warm paper. No default blue-grey SaaS palette.

## Type

System sans stack, heavy display weights for headings, tight tracking on large text.
One typeface is enough; hierarchy comes from size, weight and space, not from fonts.

## Shape and depth

- 12-16px radii, 1px ink-tinted borders.
- Buttons get a small hard offset shadow, like a sticker. Cards stay calm.
- No cards inside cards, no page-sized rounded containers, no glow gradients.

## Layout

- Header: ink band, brand wordmark, role-aware nav pills.
- Landing: headline and one real car photo in the hero, then the available fleet, then
  three concrete steps.
- Interior pages: one column of content at 64-72rem, tables scroll horizontally on phones.

## Photography

Cars use real photographs, not emoji or illustrations. `VEHICLE.Image_Path` stores the
path under `static/`, and `shared/_car_photo.html` renders it with a flat fallback panel
when a car has no photo. Photos are cropped 16:10 in cards and 4:3 on the vehicle page.
Attribution lives in `app/static/img/cars/CREDITS.md` and stays with the files.


## Copy

Short, plain, no invented numbers or claims. Prices and counts come from the database.
No eyebrows above every heading, no tracked-out capital labels, no "revolutionary".

## Motion

Transitions under 200ms, colour and transform only. Respect
`prefers-reduced-motion: reduce`.

## Accessibility floor

Visible focus rings, 4.5:1 text contrast, tap targets at least 44px, forms keep their
labels, and every page must work at 360px wide.

## Rules for new pages

1. Extend `shared/base.html`; never write a standalone `<html>`.
2. Load only your own component CSS in the `head` block.
3. Use the shared classes (`card`, `btn`, `grid`, `muted`, `tag`) before inventing new ones.

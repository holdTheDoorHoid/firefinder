# Firefinder

**Every fire lookout in the US on one map: standing or gone, with its history, how to visit,
and how to stay.**

Firefinder pulls together information scattered across many lookout websites, registers
and agency pages. It puts that information on a modern interactive map with a page for every
lookout site:

- **Visit & stay**: whether you can climb it or rent it, the rules, and a link to
  recreation.gov where it's bookable.
- **History**: a sourced story of who built it, who staffed it and what happened to it.
- **The view**: a simulated panorama from the cab and a map of what the lookout could
  see, worked out in your browser from terrain data. This works for towers that are long gone
  too.
- **Spot the smoke**: a short lesson in how two lookouts found a fire with the Osborne
  Firefinder.

It's named for the Osborne Firefinder, the round sighting table in every lookout cab.

> Status: early and growing. Entries marked **Unverified** come from a single source and have
> not been checked yet. Corrections are very welcome.

## Credits

Firefinder stands on the work of people who have documented lookouts for decades, above all
the **Forest Fire Lookout Association**, the **National Historic Lookout Register** and the
**Former Fire Lookout Sites Register**. Every tower page links back to its sources. See the
site's *Credits* page for the full list.

## Corrections, additions, takedowns

- Use **Suggest an edit** on any tower page, or [open an issue](https://github.com/holdTheDoorHoid/firefinder/issues/new).
- **Photo or text removal:** if you own something shown here and want it credited
  differently or removed, open an issue titled "Takedown: <tower name>". It will be handled
  promptly, no questions asked.

## Licenses

Code: GPL-3.0 (`LICENSE`). Lookout database: ODbL 1.0 (`DATA-LICENSE.md`). Our written
histories: CC BY-SA 4.0. Photos keep their own rights; see the credit next to each one.

## For developers

See `DESIGN.md` (authoritative design and data model). The 3D views need Rust with the
`wasm32-unknown-unknown` target and wasm-pack: `cd web && npm run wasm` once before
`npm run dev`.

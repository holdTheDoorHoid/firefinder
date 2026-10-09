/**
 * "Lookouts we can't place yet": theme toggle; the lists are prerendered per state
 * (scripts/prerender.ts). In dev, `?st=pa` renders a state's list in the browser.
 */
import '../styles/about.css';
import '../styles/unplaced.css';
import { initCommon } from '../ui/common.ts';

async function devFill(): Promise<void> {
  const main = document.querySelector<HTMLElement>('[data-ff-unplaced]');
  if (!main || !main.innerHTML.includes('ff:unplaced')) return;
  const base = import.meta.env.BASE_URL;
  const { unplacedIndexMain, unplacedStateMain } = await import('../render/unplaced.ts');
  const [file, meta] = await Promise.all([
    fetch(`${base}data/unplaced.json`).then((r) => r.json()),
    fetch(`${base}data/meta.json`).then((r) => r.json()),
  ]);
  const ctx = { base, siteUrl: location.origin + base, repo: 'holdTheDoorHoid/firefinder', sources: new Map(meta.sources.map((s: { id: string }) => [s.id, s])) };
  const st = new URLSearchParams(location.search).get('st');
  main.innerHTML = (st ? unplacedStateMain(file, st.toUpperCase(), meta, ctx as never) : unplacedIndexMain(file, meta, ctx as never)).value;
}

initCommon();
if (import.meta.env.DEV) void devFill();

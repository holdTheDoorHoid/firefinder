/** Enhancements for a prerendered tower page: theme, checklist buttons, copy coordinates. */
import '../styles/tower.css';
import { enhanceCoords, initCommon } from '../ui/common.ts';
import { initChecklistOnPage } from '../ui/checklist-ui.ts';

async function devRender(): Promise<void> {
  // `npm run dev` serves the raw template; render a tower client-side from ?id=… so the page
  // can be worked on without running the prerender. Production pages are already static HTML.
  const main = document.getElementById('main')!;
  if (!main.innerHTML.includes('ff:main')) return;
  const id = new URLSearchParams(location.search).get('id') ?? 'us-or-dutchmans-peak';
  const { renderTowerMain } = await import('../render/tower.ts');
  const base = import.meta.env.BASE_URL;
  const [rec, meta] = await Promise.all([
    fetch(`${base}data/t/${id}.json`).then((r) => r.json()),
    fetch(`${base}data/meta.json`).then((r) => r.json()),
  ]);
  const ctx = { base, siteUrl: location.origin + base, repo: 'holdTheDoorHoid/firefinder', sources: new Map(meta.sources.map((s: { id: string }) => [s.id, s])) };
  main.innerHTML = renderTowerMain(rec, ctx as never).value;
  document.title = `${rec.name} (dev render)`;
}

async function start(): Promise<void> {
  initCommon();
  if (import.meta.env.DEV) await devRender();
  initChecklistOnPage();
  enhanceCoords();
}

void start();

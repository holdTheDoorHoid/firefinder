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

/** "View from the cab": loads the panorama code and terrain only when asked. */
function initPanorama(): void {
  const host = document.querySelector<HTMLElement>('[data-pano]');
  const btn = host?.querySelector<HTMLButtonElement>('[data-pano-start]');
  if (!host || !btn) return;
  btn.disabled = false;
  const size = host.querySelector<HTMLElement>('[data-pano-size]');
  if (size && window.innerWidth < 600 && size.dataset.light) {
    const mb = Number(size.dataset.light) / 1_048_576;
    size.textContent = `Downloads about ${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB of terrain data the first time.`;
  }
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    try {
      const tower = JSON.parse(host.dataset.pano!);
      const { PanoramaView } = await import('../view3d/panorama-view.ts');
      const view = new PanoramaView(host, { tower, recon: false });
      view.el.querySelector<HTMLElement>('.pv-viewport')?.focus({ preventScroll: true });
      await view.start();
    } catch (err) {
      console.error(err);
      btn.disabled = false;
      btn.removeAttribute('aria-busy');
      size && (size.textContent = 'The view could not be loaded. Check your connection and try again.');
    }
  });
}

async function start(): Promise<void> {
  initCommon();
  if (import.meta.env.DEV) await devRender();
  initChecklistOnPage();
  enhanceCoords();
  initPanorama();
}

void start();

/** About page: theme and the checklist dialog. Sources table and key are filled at build time. */
import '../styles/about.css';
import { initCommon } from '../ui/common.ts';
import { initChecklistOnPage } from '../ui/checklist-ui.ts';

async function devFill(): Promise<void> {
  const body = document.querySelector('[data-ff-sources]');
  if (!body || body.children.length) return;
  const { sourcesRows, mapKey } = await import('../render/site.ts');
  const meta = await fetch(`${import.meta.env.BASE_URL}data/meta.json`).then((r) => r.json());
  body.innerHTML = sourcesRows(meta).value;
  document.getElementById('key-h')?.insertAdjacentHTML('afterend', mapKey().value);
}

initCommon();
initChecklistOnPage();
if (import.meta.env.DEV) void devFill();

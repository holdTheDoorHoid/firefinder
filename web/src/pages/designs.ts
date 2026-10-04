/** Designs guide: theme toggle and checklist dialog; the content is prerendered (filled live in dev). */
import '../styles/about.css';
import '../styles/designs.css';
import { initCommon } from '../ui/common.ts';
import { initChecklistOnPage } from '../ui/checklist-ui.ts';

async function devFill(): Promise<void> {
  const box = document.querySelector('[data-ff-designs]');
  if (!box || box.children.length) return;
  const { designsMain } = await import('../render/designs.ts');
  const file = await fetch(`${import.meta.env.BASE_URL}data/designs.json`).then((r) => r.json());
  box.innerHTML = designsMain(file, { base: import.meta.env.BASE_URL, repo: '' }).value;
}

initCommon();
initChecklistOnPage();
if (import.meta.env.DEV) void devFill();

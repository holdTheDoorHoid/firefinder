/** Designs guide: theme toggle and checklist dialog; the content is prerendered (filled live in dev). */
import '../styles/about.css';
import '../styles/designs.css';
import '../styles/structures.css';
import { initCommon } from '../ui/common.ts';
import { initChecklistOnPage } from '../ui/checklist-ui.ts';

async function devFill(): Promise<void> {
  const box = document.querySelector('[data-ff-designs]');
  const end = document.querySelector('[data-ff-design-end]');
  if (!box || box.children.length) return;
  const { designsMain, designsEnd } = await import('../render/designs.ts');
  const file = await fetch(`${import.meta.env.BASE_URL}data/designs.json`).then((r) => r.json());
  box.innerHTML = designsMain(file, { base: import.meta.env.BASE_URL, repo: '' }, { toc: [['structure-types', 'Structure types']] }).value;
  if (end) end.innerHTML = designsEnd(file).value;
}

/** "Structure types" (render/structures.ts), filled the same way. */
async function devFillStructures(): Promise<void> {
  const box = document.querySelector('[data-ff-structures]');
  if (!box || box.children.length) return;
  const { structuresSection } = await import('../render/structures.ts');
  const file = await fetch(`${import.meta.env.BASE_URL}data/structure_kinds.json`).then((r) => r.json());
  box.innerHTML = structuresSection(file, { base: import.meta.env.BASE_URL }).value;
}

initCommon();
initChecklistOnPage();
if (import.meta.env.DEV) {
  void devFill();
  void devFillStructures();
}

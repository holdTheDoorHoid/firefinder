/** Shared start-up for every page: fonts, base styles, theme toggle. */
import '@fontsource-variable/public-sans/wght.css';
import '@fontsource-variable/public-sans/wght-italic.css'; // only downloaded where italics appear
import '@fontsource-variable/besley/wght.css';
import '../styles/base.css';
import { initTheme } from './theme.ts';

export function initCommon(): void {
  initTheme();
}

/** Adds a small "Copy" button after every [data-coords] element. */
export function enhanceCoords(root: ParentNode = document): void {
  if (!navigator.clipboard) return;
  for (const el of root.querySelectorAll<HTMLElement>('[data-coords]')) {
    if (el.nextElementSibling?.classList.contains('copy-btn')) continue;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.setAttribute('aria-label', 'Copy coordinates');
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(el.dataset.coords!);
        btn.textContent = 'Copied';
      } catch {
        btn.textContent = 'Could not copy';
      }
      setTimeout(() => (btn.textContent = 'Copy'), 2000);
    });
    el.after(btn);
  }
}

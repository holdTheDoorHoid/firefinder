/**
 * Colour theme: Auto (follow the device) → Light → Dark. The choice is kept in localStorage
 * when allowed; an inline script in each page's <head> applies it before first paint.
 */

export type ThemeChoice = 'auto' | 'light' | 'dark';
const KEY = 'firefinder.theme';
const LABELS: Record<ThemeChoice, string> = { auto: 'Auto', light: 'Light', dark: 'Dark' };
const NEXT: Record<ThemeChoice, ThemeChoice> = { auto: 'light', light: 'dark', dark: 'auto' };

const listeners = new Set<(effective: 'light' | 'dark') => void>();
const media = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;

function readChoice(): ThemeChoice {
  const attr = document.documentElement.getAttribute('data-theme');
  return attr === 'light' || attr === 'dark' ? attr : 'auto';
}

export function effectiveTheme(): 'light' | 'dark' {
  const c = readChoice();
  if (c !== 'auto') return c;
  return media?.matches ? 'dark' : 'light';
}

export function onThemeChange(fn: (effective: 'light' | 'dark') => void): void {
  listeners.add(fn);
}

function apply(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === 'auto') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', choice);
  try {
    if (choice === 'auto') localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    /* storage blocked: the choice lasts for this page only */
  }
  updateButtons();
  const eff = effectiveTheme();
  for (const fn of listeners) fn(eff);
}

function updateButtons(): void {
  const choice = readChoice();
  const next = NEXT[choice];
  for (const btn of document.querySelectorAll<HTMLButtonElement>('[data-theme-toggle]')) {
    const label = btn.querySelector('[data-theme-label]');
    if (label) label.textContent = LABELS[choice];
    const now = choice === 'auto' ? `Auto (following your device, currently ${effectiveTheme()})` : LABELS[choice];
    btn.setAttribute('aria-label', `Colour theme: ${now}. Switch to ${LABELS[next]}.`);
    btn.title = `Switch to ${LABELS[next]} theme`;
  }
}

export function initTheme(): void {
  updateButtons();
  for (const btn of document.querySelectorAll<HTMLButtonElement>('[data-theme-toggle]')) {
    btn.addEventListener('click', () => apply(NEXT[readChoice()]));
  }
  media?.addEventListener('change', () => {
    updateButtons();
    if (readChoice() === 'auto') for (const fn of listeners) fn(effectiveTheme());
  });
}

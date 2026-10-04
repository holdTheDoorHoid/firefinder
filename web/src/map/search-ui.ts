/**
 * Name search as an ARIA combobox: results appear as you type; arrow keys move, Enter picks,
 * Escape closes (a second Escape clears). Searches every lookout, even ones the current
 * filters hide; picking a hidden one says so in the side panel.
 */
import { html, raw } from '../lib/html.ts';
import { fillFor, markerSvg, shapeFor } from '../lib/icons.ts';
import { search, type SearchEntry } from '../lib/search.ts';
import { statusWording } from '../lib/vocab.ts';
import { placeLine } from '../render/tower.ts';

export interface SearchDeps {
  input: HTMLInputElement;
  list: HTMLUListElement;
  status: HTMLElement;
  index: () => readonly SearchEntry[];
  onPick: (entry: SearchEntry) => void;
}

export function initSearch(d: SearchDeps): void {
  const { input, list, status } = d;
  let results: SearchEntry[] = [];
  let active = -1;

  const close = () => {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    active = -1;
  };

  const setActive = (i: number) => {
    const items = list.querySelectorAll<HTMLElement>('[role="option"]');
    items.forEach((el, n) => el.setAttribute('aria-selected', String(n === i)));
    active = i;
    if (i >= 0 && items[i]) {
      input.setAttribute('aria-activedescendant', items[i]!.id);
      items[i]!.scrollIntoView({ block: 'nearest' });
    } else {
      input.removeAttribute('aria-activedescendant');
    }
  };

  const render = () => {
    const q = input.value;
    if (!q.trim()) {
      list.innerHTML = '';
      status.textContent = '';
      close();
      return;
    }
    results = search(d.index(), q, 30);
    if (!results.length) {
      list.innerHTML = html`<li class="search-empty" role="presentation">No lookouts match “${q.trim()}”. Try part of the name, like “hirz”.</li>`.value;
      status.textContent = 'No matching lookouts.';
    } else {
      list.innerHTML = html`${results.map((r, i) => {
        const p = r.props;
        return html`<li role="option" id="q-opt-${i}" aria-selected="false" data-i="${i}">
          <span class="res-icon">${raw(markerSvg(shapeFor(p.k), fillFor(p.s), { size: 18, rentable: !!p.rt }))}</span>
          <span class="res-text"><span class="res-name">${p.n}</span><span class="res-meta">${placeLine({ county: p.c ?? null, region: p.r })} · ${statusWording(p.s).label}${p.rt ? ' · Rentable' : ''}</span></span>
        </li>`;
      })}`.value;
      status.textContent = `${results.length === 30 ? 'At least 30' : results.length} matching lookout${results.length === 1 ? '' : 's'}. Use the arrow keys to choose.`;
    }
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    setActive(-1);
  };

  const pick = (i: number) => {
    const r = results[i];
    if (!r) return;
    close();
    d.onPick(r);
  };

  input.addEventListener('input', render);
  input.addEventListener('focus', () => {
    if (input.value.trim()) render();
  });
  input.addEventListener('keydown', (e) => {
    const n = results.length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (list.hidden) render();
      if (n) setActive((active + 1) % n);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (n) setActive(active <= 0 ? n - 1 : active - 1);
    } else if (e.key === 'Enter') {
      if (!list.hidden && n) {
        e.preventDefault();
        pick(active >= 0 ? active : 0);
      }
    } else if (e.key === 'Escape') {
      if (!list.hidden) close();
      else input.value = '';
    }
  });
  list.addEventListener('mousedown', (e) => e.preventDefault()); // keep focus in the input
  list.addEventListener('click', (e) => {
    const li = (e.target as Element).closest<HTMLElement>('[role="option"]');
    if (li) pick(Number(li.dataset.i));
  });
  input.addEventListener('blur', () => setTimeout(close, 120));
}

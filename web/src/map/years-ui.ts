/**
 * The national year view: "Lookouts standing in 1935". A slider from 1900 to today, the count
 * the records support, an honest count of those whose dates are incomplete (shown faded on the
 * map when asked), a small chart of every year, the numbers as a table, and how it is worked
 * out. Counts follow the map's other filters.
 */
import { formatCount } from '../lib/format.ts';
import { html, raw } from '../lib/html.ts';
import { SLIDER_FIRST_YEAR, yearSeries, type YearCounts } from '../lib/history.ts';
import type { HistoryCounts, TowerFeature } from '../lib/types.ts';
import { YearChart } from './year-chart.ts';

export interface YearPanelDeps {
  host: HTMLElement;
  thisYear: number;
  /** National counts from meta.json (what the records hold, before any filter). */
  history: () => HistoryCounts | null;
  /** Every lookout, for the national notes. */
  all: () => readonly TowerFeature[];
  /** Lookouts that pass the other filters (the counts follow them). */
  filtered: () => readonly TowerFeature[];
  filtersActive: () => boolean;
  onChange: (year: number | null, maybe: boolean) => void;
}

const CLOSE = '<svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m5 5 10 10M15 5 5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const PREV = '<svg width="16" height="16" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M12.5 4.5 7 10l5.5 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const NEXT = '<svg width="16" height="16" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M7.5 4.5 13 10l-5.5 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function plural(n: number, one: string, many: string): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`;
}

/** "a, b and c" */
function listing(parts: string[]): string {
  return parts.length <= 1 ? (parts[0] ?? '') : `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}`;
}

export class YearPanel {
  #d: YearPanelDeps;
  #el: HTMLElement | null = null;
  #chart: YearChart | null = null;
  #year: number | null = null;
  #maybe = false;
  #series: YearCounts[] = [];
  #today: YearCounts | null = null;

  constructor(d: YearPanelDeps) {
    this.#d = d;
  }

  get year(): number | null {
    return this.#year;
  }

  get maybe(): boolean {
    return this.#maybe;
  }

  get isOpen(): boolean {
    return this.#year !== null;
  }

  open(year: number, maybe = false, focus = false): void {
    this.#year = Math.min(Math.max(Math.round(year), SLIDER_FIRST_YEAR), this.#d.thisYear);
    this.#maybe = maybe;
    if (!this.#el) this.#build();
    this.#el!.hidden = false;
    this.refresh();
    if (focus) this.#el!.querySelector<HTMLInputElement>('input[type="range"]')?.focus();
    this.#d.onChange(this.#year, this.#maybe);
  }

  close(): void {
    this.#year = null;
    if (this.#el) this.#el.hidden = true;
    this.#d.onChange(null, this.#maybe);
  }

  /** Recount (the filters changed) and redraw. */
  refresh(): void {
    if (this.#year === null || !this.#el) return;
    const T = this.#d.thisYear;
    const all = yearSeries(this.#d.filtered(), SLIDER_FIRST_YEAR, T, T);
    this.#series = all.slice(0, -1);
    this.#today = all.at(-1) ?? null;
    this.#chart?.update(this.#series, this.#today!, this.#year);
    this.#render();
  }

  #set(year: number): void {
    const y = Math.min(Math.max(year, SLIDER_FIRST_YEAR), this.#d.thisYear);
    if (y === this.#year) return;
    this.#year = y;
    this.#chart?.select(y);
    this.#render();
    this.#d.onChange(this.#year, this.#maybe);
  }

  #counts(): YearCounts | null {
    if (this.#year === null) return null;
    return this.#year >= this.#d.thisYear ? this.#today : (this.#series[this.#year - SLIDER_FIRST_YEAR] ?? null);
  }

  #build(): void {
    const T = this.#d.thisYear;
    const el = document.createElement('section');
    el.className = 'years-card';
    el.setAttribute('aria-labelledby', 'years-h');
    el.innerHTML = html`
      <div class="years-main">
        <div class="years-head">
          <h2 id="years-h"><span class="years-pre" data-pre>Lookouts standing in</span> <span class="years-year" data-year></span></h2>
          <button type="button" class="icon-btn years-close" data-years-close aria-label="Close the year view">${raw(CLOSE)}</button>
        </div>
        <div class="years-slider">
          <button type="button" class="icon-btn years-step" data-step="-1" aria-label="One year earlier">${raw(PREV)}</button>
          <input type="range" min="${SLIDER_FIRST_YEAR}" max="${T}" step="1" aria-label="Year">
          <button type="button" class="icon-btn years-step" data-step="1" aria-label="One year later">${raw(NEXT)}</button>
        </div>
        <div class="years-jumps" role="group" aria-label="Jump to a year">
          ${[1910, 1935, 1960, 1990].map((y) => html`<button type="button" class="years-jump" data-jump="${y}">${y}</button>`)}
          <button type="button" class="years-jump" data-jump="${T}">Today</button>
        </div>
        <p class="years-count" data-count></p>
        <p class="years-maybe" data-maybe></p>
        <label class="years-toggle"><input type="checkbox" data-maybe-toggle> <span data-toggle-label>Show them faded on the map</span></label>
        <p class="fine years-markers">Markers keep today's look: a hollow one is a lookout that is gone now.</p>
      </div>
      <div class="years-side">
        <div data-chart></div>
        <ul class="years-legend">
          <li><span class="yc-key yc-key-stood" aria-hidden="true"></span>Standing, going by the records</li>
          <li><span class="yc-key yc-key-band" aria-hidden="true"></span>Built by then; when it came down is not recorded</li>
        </ul>
        <details class="years-more"><summary>How this is worked out, and the numbers</summary>
          <div class="years-notes" data-notes></div>
          <div class="years-table-wrap" data-table></div>
        </details>
      </div>`.value;
    this.#d.host.append(el);
    this.#el = el;

    const range = el.querySelector<HTMLInputElement>('input[type="range"]')!;
    range.addEventListener('input', () => this.#set(Number(range.value)));
    el.querySelector('[data-years-close]')!.addEventListener('click', () => this.close());
    el.addEventListener('click', (e) => {
      const t = e.target as Element;
      const step = t.closest<HTMLElement>('[data-step]');
      if (step && this.#year !== null) this.#set(this.#year + Number(step.dataset.step));
      const jump = t.closest<HTMLElement>('[data-jump]');
      if (jump) this.#set(Number(jump.dataset.jump));
    });
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        this.close();
      }
    });
    const toggle = el.querySelector<HTMLInputElement>('[data-maybe-toggle]')!;
    toggle.addEventListener('change', () => {
      this.#maybe = toggle.checked;
      this.#d.onChange(this.#year, this.#maybe);
    });
    this.#chart = new YearChart((y) => this.#set(y));
    el.querySelector('[data-chart]')!.append(this.#chart.el);
  }

  #render(): void {
    const el = this.#el;
    const c = this.#counts();
    if (!el || this.#year === null || !c) return;
    const T = this.#d.thisYear;
    const today = this.#year >= T;
    const filtered = this.#d.filtersActive();
    el.querySelector('[data-pre]')!.textContent = today ? 'Lookouts standing' : 'Lookouts standing in';
    el.querySelector('[data-year]')!.textContent = today ? 'today' : String(this.#year);
    const range = el.querySelector<HTMLInputElement>('input[type="range"]')!;
    range.value = String(this.#year);
    const maybe = c.built + c.nostart + c.nodates;
    range.setAttribute(
      'aria-valuetext',
      today ? `Today: ${formatCount(c.stood)} standing` : `${this.#year}: ${formatCount(c.stood)} standing by the records, ${formatCount(maybe)} more may have been`,
    );
    for (const b of el.querySelectorAll<HTMLButtonElement>('[data-jump]')) b.setAttribute('aria-pressed', String(Number(b.dataset.jump) === this.#year));
    el.querySelector<HTMLButtonElement>('[data-step="-1"]')!.disabled = this.#year <= SLIDER_FIRST_YEAR;
    el.querySelector<HTMLButtonElement>('[data-step="1"]')!.disabled = this.#year >= T;

    const of = filtered ? ' of the lookouts your filters show' : '';
    el.querySelector('[data-count]')!.innerHTML = today
      ? html`<strong>${formatCount(c.stood)}</strong> ${c.stood === 1 ? 'lookout stands' : 'lookouts stand'} today${of}, going by their current status.`.value
      : html`<strong>${formatCount(c.stood)}</strong> ${c.stood === 1 ? 'lookout' : 'lookouts'}${of} stood in ${this.#year}, going by their recorded dates.`.value;
    const parts: string[] = [];
    if (today) {
      if (maybe) parts.push(`${plural(maybe, 'other lookout has', 'other lookouts have')} no known status: we do not know whether ${maybe === 1 ? 'it still stands' : 'they still stand'}.`);
    } else if (maybe) {
      const why: string[] = [];
      if (c.built) why.push(`${formatCount(c.built)} were built by then but nobody recorded when they came down`);
      if (c.nostart) why.push(`${formatCount(c.nostart)} have no recorded build year`);
      if (c.nodates) why.push(`${formatCount(c.nodates)} have no dates at all`);
      parts.push(`Another ${formatCount(maybe)} may have: ${listing(why)}.`);
    }
    el.querySelector('[data-maybe]')!.textContent = parts.join(' ');
    const toggle = el.querySelector<HTMLInputElement>('[data-maybe-toggle]')!;
    toggle.checked = this.#maybe;
    toggle.closest('label')!.hidden = maybe === 0;
    el.querySelector('[data-toggle-label]')!.textContent = `Show ${maybe === 1 ? 'it' : `these ${formatCount(maybe)}`} faded on the map`;
    this.#renderTable();
    this.#renderNotes();
  }

  #renderTable(): void {
    const box = this.#el?.querySelector('[data-table]');
    if (!box) return;
    const rows = this.#series.filter((s) => s.year % 10 === 0);
    const t = this.#today;
    box.innerHTML = html`<table class="years-tbl">
      <caption class="visually-hidden">Lookouts standing each decade${this.#d.filtersActive() ? ', with your filters' : ''}</caption>
      <thead><tr><th scope="col">Year</th><th scope="col" class="num">Standing by the records</th><th scope="col" class="num">Built, end not recorded</th><th scope="col" class="num">No build year</th><th scope="col" class="num">No dates</th></tr></thead>
      <tbody>${rows.map((r) => html`<tr><th scope="row">${r.year}</th><td class="num">${formatCount(r.stood)}</td><td class="num">${formatCount(r.built)}</td><td class="num">${formatCount(r.nostart)}</td><td class="num">${formatCount(r.nodates)}</td></tr>`)}
      ${t ? html`<tr><th scope="row">Today</th><td class="num">${formatCount(t.stood)}</td><td class="num" colspan="3">${formatCount(t.built + t.nostart + t.nodates)} status unknown</td></tr>` : ''}</tbody>
    </table>`.value;
  }

  #renderNotes(): void {
    const box = this.#el?.querySelector('[data-notes]');
    const h = this.#d.history();
    if (!box) return;
    const all = this.#d.all();
    const starts = all.filter((f) => f.properties.y0 !== undefined);
    const thirties = starts.filter((f) => f.properties.y0! >= 1930 && f.properties.y0! < 1940).length;
    box.innerHTML = html`
      <p><strong>How it is worked out.</strong> A lookout counts as standing in a year if it was built in or before that year and had not yet come down. “Built” is a recorded build, rebuild or first staffing; “came down” is a recorded destruction, fire, removal or abandonment. Today's count uses each lookout's current status instead.</p>
      ${h
        ? html`<p><strong>The records are thin.</strong> Of ${formatCount(h.total)} lookouts, ${formatCount(h.with_start)} have a recorded build year and only ${formatCount(h.with_end)} a recorded end; ${formatCount(h.no_dates)} have neither (${formatCount(h.standing_no_start)} of those still stand). Lookouts without dates are never left out silently: they are counted above as “may have”, and you can show them faded.</p>`
        : ''}
      <p>So the line is a floor, not a census. It shows the burst of building in the 1930s (${formatCount(thirties)} of the ${formatCount(starts.length)} recorded build years), but hardly any of the decline after the 1950s, because few removal dates were ever written down where we can find them. The numbers will change as sources and stories are added.</p>`.value;
  }
}

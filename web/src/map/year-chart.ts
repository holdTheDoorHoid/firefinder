/**
 * The small "lookouts standing each year" chart in the year view. Plain SVG drawn at the
 * container's width, themed by CSS (map.css .yc-*). Two layers, never told apart by colour
 * alone: a solid area for lookouts the records place in each year, and a hatched band above
 * it for those built by then whose end was never recorded. Today stands apart on the right,
 * counted by current status. Hover (or touch-drag) shows the numbers for a year; a click
 * picks that year. The same numbers are in the table under the chart.
 */
import { formatCount } from '../lib/format.ts';
import type { YearCounts } from '../lib/history.ts';

const SVG = 'http://www.w3.org/2000/svg';
const H = 112;
const M = { top: 10, right: 6, bottom: 20, left: 40 };
const TODAY_W = 30;

function niceMax(v: number): number {
  if (v <= 0) return 10;
  const step = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * step >= v) return m * step;
  return 10 * step;
}

export class YearChart {
  readonly el: HTMLDivElement;
  #svg: SVGSVGElement;
  #tip: HTMLDivElement;
  #series: YearCounts[] = [];
  #today: YearCounts | null = null;
  #selected = 1935;
  #onPick: (year: number) => void;
  #width = 0;
  #observer: ResizeObserver | null = null;
  #dragging = false;

  constructor(onPick: (year: number) => void) {
    this.#onPick = onPick;
    this.el = document.createElement('div');
    this.el.className = 'yc';
    this.#svg = document.createElementNS(SVG, 'svg');
    this.#svg.setAttribute('class', 'yc-svg');
    this.#svg.setAttribute('height', String(H));
    this.#svg.setAttribute('aria-hidden', 'true');
    this.#tip = document.createElement('div');
    this.#tip.className = 'yc-tip';
    this.#tip.hidden = true;
    this.el.append(this.#svg, this.#tip);
    if ('ResizeObserver' in window) {
      this.#observer = new ResizeObserver(() => {
        if (this.el.clientWidth && this.el.clientWidth !== this.#width) this.#draw();
      });
      this.#observer.observe(this.el);
    }
    this.#svg.addEventListener('pointermove', (e) => this.#hover(e));
    this.#svg.addEventListener('pointerleave', () => {
      if (!this.#dragging) this.#tip.hidden = true;
    });
    this.#svg.addEventListener('pointerdown', (e) => {
      this.#dragging = true;
      this.#svg.setPointerCapture(e.pointerId);
      this.#pick(e);
    });
    this.#svg.addEventListener('pointerup', (e) => {
      this.#dragging = false;
      this.#svg.releasePointerCapture(e.pointerId);
      this.#tip.hidden = true;
    });
  }

  destroy(): void {
    this.#observer?.disconnect();
  }

  update(series: YearCounts[], today: YearCounts, selected: number): void {
    this.#series = series;
    this.#today = today;
    this.#selected = selected;
    this.#draw();
  }

  select(year: number): void {
    this.#selected = year;
    this.#draw();
  }

  #scales() {
    const W = this.#width;
    const first = this.#series[0]?.year ?? 1900;
    const last = this.#series.at(-1)?.year ?? first + 1;
    const plotW = Math.max(40, W - M.left - M.right - TODAY_W);
    const max = niceMax(Math.max(1, ...this.#series.map((s) => s.stood + s.built), this.#today?.stood ?? 0));
    const x = (year: number) => M.left + ((year - first) / Math.max(1, last - first)) * plotW;
    const y = (v: number) => M.top + (1 - v / max) * (H - M.top - M.bottom);
    const todayX = M.left + plotW + TODAY_W / 2 + 4;
    return { W, first, last, plotW, max, x, y, todayX };
  }

  #draw(): void {
    this.#width = this.el.clientWidth || 320;
    const svg = this.#svg;
    svg.setAttribute('width', String(this.#width));
    svg.setAttribute('viewBox', `0 0 ${this.#width} ${H}`);
    if (!this.#series.length) {
      svg.replaceChildren();
      return;
    }
    const { first, last, max, x, y, todayX } = this.#scales();
    const base = y(0);
    const pts = (f: (s: YearCounts) => number) => this.#series.map((s) => `${x(s.year).toFixed(1)},${y(f(s)).toFixed(1)}`);
    const stoodTop = pts((s) => s.stood);
    const bandTop = pts((s) => s.stood + s.built);
    const ticks = [0, max / 2, max];
    const decades = [1900, 1925, 1950, 1975, 2000].filter((d) => d >= first && d <= last);
    const sel = Math.min(Math.max(this.#selected, first), last + 1);
    const selIsToday = this.#selected > last;
    const selX = selIsToday ? todayX : x(sel);
    const selCounts = selIsToday ? this.#today : this.#series[sel - first];
    const t = this.#today;
    svg.innerHTML = `
      <defs><pattern id="yc-hatch" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">
        <rect width="5" height="5" class="yc-hatch-bg"/><line x1="0" y1="0" x2="0" y2="5" class="yc-hatch-line"/></pattern></defs>
      ${ticks.map((v) => `<line class="yc-grid" x1="${M.left}" x2="${todayX + TODAY_W / 2}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="yc-tick" x="${M.left - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${formatCount(Math.round(v))}</text>`).join('')}
      <polygon class="yc-band" points="${[...bandTop, ...[...stoodTop].reverse()].join(' ')}"/>
      <polyline class="yc-band-top" points="${bandTop.join(' ')}"/>
      <polygon class="yc-area" points="${[`${x(first).toFixed(1)},${base}`, ...stoodTop, `${x(last).toFixed(1)},${base}`].join(' ')}"/>
      <polyline class="yc-line" points="${stoodTop.join(' ')}"/>
      ${t ? `<rect class="yc-today" x="${todayX - 7}" width="14" y="${y(t.stood).toFixed(1)}" height="${Math.max(0, base - y(t.stood)).toFixed(1)}" rx="3"/>` : ''}
      ${decades.map((d) => `<text class="yc-tick" x="${x(d).toFixed(1)}" y="${H - 5}" text-anchor="middle">${d}</text>`).join('')}
      <text class="yc-tick yc-tick-today" x="${todayX}" y="${H - 5}" text-anchor="middle">Today</text>
      <line class="yc-sel" x1="${selX.toFixed(1)}" x2="${selX.toFixed(1)}" y1="${M.top - 4}" y2="${base}"/>
      ${selCounts ? `<circle class="yc-dot" cx="${selX.toFixed(1)}" cy="${y(selCounts.stood).toFixed(1)}" r="4"/>` : ''}
      <rect class="yc-hit" x="0" y="0" width="${this.#width}" height="${H}"/>`;
  }

  #yearAt(e: PointerEvent): number | 'today' {
    const r = this.#svg.getBoundingClientRect();
    const px = e.clientX - r.left;
    const { first, last, plotW, todayX } = this.#scales();
    if (px > M.left + plotW + 2 && px > todayX - TODAY_W / 2) return 'today';
    const year = Math.round(first + ((px - M.left) / plotW) * (last - first));
    return Math.min(Math.max(year, first), last);
  }

  #hover(e: PointerEvent): void {
    if (this.#dragging) this.#pick(e);
    const at = this.#yearAt(e);
    const c = at === 'today' ? this.#today : this.#series[at - (this.#series[0]?.year ?? 0)];
    if (!c) return;
    const tip = this.#tip;
    tip.replaceChildren();
    const head = document.createElement('p');
    head.className = 'yc-tip-year';
    head.textContent = at === 'today' ? 'Today' : String(at);
    const row = (cls: string, value: number, label: string) => {
      const p = document.createElement('p');
      p.className = `yc-tip-row ${cls}`;
      const v = document.createElement('strong');
      v.textContent = formatCount(value);
      p.append(document.createElement('span'), v, document.createTextNode(` ${label}`));
      return p;
    };
    tip.append(
      head,
      row('yc-k-stood', c.stood, at === 'today' ? 'standing now' : 'standing by the records'),
      at === 'today'
        ? row('yc-k-band', c.built + c.nodates, 'status unknown')
        : row('yc-k-band', c.built, 'built by then, end not recorded'),
    );
    tip.hidden = false;
    const r = this.#svg.getBoundingClientRect();
    const px = e.clientX - r.left;
    tip.style.left = `${Math.min(Math.max(px + 12, 0), r.width - tip.offsetWidth)}px`;
    tip.classList.toggle('flip', px + 12 + tip.offsetWidth > r.width);
    if (px + 12 + tip.offsetWidth > r.width) tip.style.left = `${Math.max(0, px - 12 - tip.offsetWidth)}px`;
  }

  #pick(e: PointerEvent): void {
    const at = this.#yearAt(e);
    const year = at === 'today' ? (this.#series.at(-1)?.year ?? 2025) + 1 : at;
    if (year !== this.#selected) this.#onPick(year);
  }
}

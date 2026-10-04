/**
 * The tower page's then-and-now timeline: a drawn line of the lookout's life (years on a line,
 * built -> staffed -> gone or restored, a "today" marker, dashed where nothing is recorded)
 * and, underneath, the same history as an ordered list with its sources and honest gaps
 * ("No record between 1934 and 1987"). The drawing is decoration for sighted readers
 * (aria-hidden); the list says everything in words. Pure string rendering: used by the
 * prerendered pages, no JavaScript needed.
 */
import { html, raw, type SafeHtml } from '../lib/html.ts';
import { labelRows, timelineModel, yearPosition, type EventShape, type TimelineModel } from '../lib/history.ts';
import type { TowerEvent } from '../lib/types.ts';
import { eventLabel, statusWording } from '../lib/vocab.ts';

/** Marker shapes, 14 x 14, drawn in currentColor. The legend repeats them with words. */
const SHAPE_SVG: Record<EventShape | 'today', string> = {
  start: '<path d="M7 1.6 12.6 12H1.4Z" fill="currentColor"/>',
  staff: '<circle cx="7" cy="7" r="4.6" fill="currentColor"/>',
  record: '<path d="M3 1.8h8v10.6L7 9.6l-4 2.8Z" fill="currentColor"/>',
  care: '<path d="M7 1.2 12.8 7 7 12.8 1.2 7Z" fill="currentColor"/>',
  end: '<path d="m2.6 2.6 8.8 8.8M11.4 2.6l-8.8 8.8" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',
  move: '<path d="M1.8 7h9M8 3.4 11.8 7 8 10.6" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>',
  other: '<circle cx="7" cy="7" r="4.2" fill="none" stroke="currentColor" stroke-width="2"/>',
  today: '<path d="M7 1v12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="7" cy="7" r="3.4" fill="currentColor"/>',
};

const SHAPE_WORDS: Record<EventShape, string> = {
  start: 'built or rebuilt',
  staff: 'staffing',
  record: 'listed on a register',
  care: 'restored or opened to stay',
  end: 'came down or abandoned',
  move: 'moved',
  other: 'other event',
};

function shapeSvg(shape: EventShape | 'today'): SafeHtml {
  return raw(`<svg class="tl-shape" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">${SHAPE_SVG[shape]}</svg>`);
}

/** Percent offsets keep labels on screen near the ends of the line. */
function edgeClass(x: number): string {
  return x < 7 ? ' at-start' : x > 93 ? ' at-end' : '';
}

function drawing(m: TimelineModel, status: string): SafeHtml {
  const xs = m.marks.map((k) => yearPosition(k.year, m.first, m.last));
  // One marker per year on the line; the list underneath has every event.
  const byYear = new Map<number, { x: number; shapes: EventShape[]; labels: string[] }>();
  m.marks.forEach((k, i) => {
    const slot = byYear.get(k.year) ?? { x: xs[i]!, shapes: [], labels: [] };
    if (!slot.shapes.includes(k.shape)) slot.shapes.push(k.shape);
    slot.labels.push(k.label);
    byYear.set(k.year, slot);
  });
  const slots = [...byYear.entries()];
  const todayX = 100;
  const rows = labelRows([...slots.map(([, s]) => s.x), todayX], 9, 3);
  const used = [...new Set(m.marks.map((k) => k.shape))];
  const segs = m.segments.map(
    (s) => html`<span class="tl-seg tl-seg-${s.kind}" style="left:${yearPosition(s.from, m.first, m.last).toFixed(2)}%;width:${(yearPosition(s.to, m.first, m.last) - yearPosition(s.from, m.first, m.last)).toFixed(2)}%"></span>`,
  );
  const st = statusWording(status).label;
  return html`<div class="tl-figure" aria-hidden="true">
    <div class="tl-track" style="--rows:${Math.max(...rows) + 1}">
      ${segs}
      ${slots.map(([year, s], i) => html`<span class="tl-mark tl-row-${rows[i]}${edgeClass(s.x)}${s.shapes.map((sh) => ` tl-has-${sh}`).join('')}" style="left:${s.x.toFixed(2)}%" title="${year}: ${s.labels.join(', ')}">${s.shapes.slice(0, 2).map((sh) => shapeSvg(sh))}<span class="tl-mark-year">${year}</span></span>`)}
      <span class="tl-mark tl-mark-today tl-row-${rows.at(-1)} at-end" style="left:${todayX}%">${shapeSvg('today')}<span class="tl-mark-year">Today</span></span>
    </div>
    <div class="tl-axis"><span>${m.startUnknown ? 'Built: not recorded' : ''}</span><span>Today: ${st.toLowerCase()}</span></div>
    <ul class="tl-legend">
      ${used.map((sh) => html`<li>${shapeSvg(sh)}${SHAPE_WORDS[sh]}</li>`)}
      <li><span class="tl-key tl-key-stood"></span>standing, by the records</li>
      ${m.segments.some((s) => s.kind === 'unknown') ? html`<li><span class="tl-key tl-key-unknown"></span>no record</li>` : ''}
      ${m.segments.some((s) => s.kind === 'gone') ? html`<li><span class="tl-key tl-key-gone"></span>gone</li>` : ''}
    </ul>
  </div>`;
}

function todayText(status: string, m: TimelineModel): SafeHtml {
  if (status === 'standing') return html`<span class="tl-what">Standing</span><span class="tl-note">It still stands, as far as our sources know.</span>`;
  if (status === 'replica') return html`<span class="tl-what">A replica stands</span><span class="tl-note">A copy stands here, not the original structure.</span>`;
  if (status === 'unknown') return html`<span class="tl-what">Status unknown</span><span class="tl-note">We do not know whether it still stands.</span>`;
  const st = statusWording(status);
  return html`<span class="tl-what">${st.label}</span><span class="tl-note">${st.meaning}${m.endUnknown ? ' When it came down is not recorded.' : ''}</span>`;
}

export interface TimelineDeps {
  /** "Source: …" for one event (a link to the cited page or to the source in the list below). */
  source: (e: TowerEvent) => SafeHtml | string;
  thisYear: number;
}

export function renderTimeline(events: readonly TowerEvent[] | null | undefined, status: string, d: TimelineDeps): SafeHtml {
  const m = timelineModel(events, status, d.thisYear);
  if (!m) {
    return html`<p class="muted">No dated events recorded yet: nobody has recorded when this lookout was built${status === 'standing' ? '' : ' or when it came down'}.</p>${(events ?? []).length ? list(null, events ?? [], d) : ''}`;
  }
  return html`${drawing(m, status)}${list(m, events ?? [], d)}`;
}

function list(m: TimelineModel | null, events: readonly TowerEvent[], d: TimelineDeps): SafeHtml {
  const items = m
    ? m.items
    : events.map((event, index) => ({ type: 'event' as const, year: event.year ?? null, event, index }));
  return html`<ol class="timeline">${items.map((it) => {
    if (it.type === 'gap') {
      return html`<li class="tl-gap"><span class="tl-year"></span><span class="tl-body">No record between ${it.from} and ${it.to}</span></li>`;
    }
    if (it.type === 'today') {
      return html`<li class="tl-today"><span class="tl-year">Today</span><span class="tl-body">${todayText(it.status, m!)}</span></li>`;
    }
    const e = it.event;
    return html`<li class="tl-event"><span class="tl-year">${e.year ?? 'Date unknown'}</span>
      <span class="tl-body"><span class="tl-what">${eventLabel(e.event)}</span>${e.note ? html`<span class="tl-note">${e.note}</span>` : ''}${d.source(e)}</span></li>`;
  })}</ol>`;
}

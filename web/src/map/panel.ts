/** The lookout details panel: a side panel on wide screens, a bottom sheet on phones. */
import { renderPanel, renderPanelStub, type RenderContext } from '../render/tower.ts';
import type { TowerProps, TowerRecord } from '../lib/types.ts';
import { isTowerId } from '../lib/checklist.ts';

export interface PanelDeps {
  el: HTMLElement;
  body: HTMLElement;
  closeBtn: HTMLButtonElement;
  ctx: RenderContext;
  isHiddenByFilters: (id: string) => boolean;
  /** True while the year view narrows the map (the "hidden" notice says so). */
  yearView?: () => boolean;
  /** Called after the panel content changes (to bind checklist buttons etc.). */
  onRender: (root: HTMLElement) => void;
  onClose: () => void;
}

export class Panel {
  #d: PanelDeps;
  #cache = new Map<string, TowerRecord>();
  #current: string | null = null;
  #returnFocus: HTMLElement | null = null;

  constructor(d: PanelDeps) {
    this.#d = d;
    d.closeBtn.addEventListener('click', () => this.close());
    d.el.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        this.close();
      }
    });
  }

  get current(): string | null {
    return this.#current;
  }

  get isOpen(): boolean {
    return !this.#d.el.hidden;
  }

  /** Height the panel covers at the bottom (phones) or width at the right (wide screens). */
  coverage(): { right: number; bottom: number } {
    if (this.#d.el.hidden) return { right: 0, bottom: 0 };
    const r = this.#d.el.getBoundingClientRect();
    const sheet = matchMedia('(max-width: 899px)').matches;
    // The sheet grows when the full record replaces the loading stub; plan for its full height.
    return sheet ? { right: 0, bottom: Math.max(r.height, window.innerHeight * 0.62) } : { right: r.width + 16, bottom: 0 };
  }

  async open(id: string, props: TowerProps | null, opts: { focus?: boolean } = {}): Promise<void> {
    if (!isTowerId(id)) return;
    const d = this.#d;
    if (opts.focus !== false && !this.isOpen) this.#returnFocus = document.activeElement as HTMLElement | null;
    this.#current = id;
    d.el.hidden = false;
    const cached = this.#cache.get(id);
    if (cached) {
      this.#show(cached, opts.focus !== false);
      return;
    }
    if (props) {
      d.body.innerHTML = renderPanelStub(props, d.ctx, 'Loading details…').value;
      if (opts.focus !== false) this.#focusTitle();
    }
    try {
      const res = await fetch(`${d.ctx.base}data/t/${id}.json`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const rec = (await res.json()) as TowerRecord;
      this.#cache.set(id, rec);
      if (this.#current === id) this.#show(rec, opts.focus !== false && !props);
    } catch {
      if (this.#current !== id) return;
      if (props) {
        d.body.innerHTML = renderPanelStub(props, d.ctx, 'Could not load the details. Check your connection, or open the full page.').value;
      } else {
        d.body.innerHTML = '<p class="muted">Could not load this lookout. Check your connection and try again.</p>';
      }
    }
  }

  /** Re-render the open panel (e.g. after filters changed). */
  refresh(): void {
    const id = this.#current;
    const rec = id ? this.#cache.get(id) : null;
    if (rec && this.isOpen) this.#show(rec, false);
  }

  close(): void {
    const d = this.#d;
    if (d.el.hidden) return;
    d.el.hidden = true;
    this.#current = null;
    d.onClose();
    const back = this.#returnFocus;
    this.#returnFocus = null;
    if (back && document.contains(back)) back.focus();
  }

  #show(rec: TowerRecord, focus: boolean): void {
    const d = this.#d;
    // Replacing the markup would drop focus to <body>; keep it in the panel if it was there.
    const hadFocus = d.body.contains(document.activeElement);
    d.body.innerHTML = renderPanel(rec, d.ctx, { hiddenByFilters: d.isHiddenByFilters(rec.id), yearView: d.yearView?.() ?? false }).value;
    d.el.scrollTop = 0;
    d.onRender(d.body);
    if (focus || hadFocus) this.#focusTitle();
  }

  #focusTitle(): void {
    this.#d.body.querySelector<HTMLElement>('#panel-title')?.focus({ preventScroll: true });
  }
}

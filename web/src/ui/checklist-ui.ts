/**
 * Checklist controls shared by the map and tower pages:
 *  - toggle buttons inside any element with [data-checklist="<tower id>"]
 *  - the "Download or import my checklist" dialog, opened by [data-open-checklist-dialog]
 */
import { Checklist, MARKS, MARK_LABELS, browserStorage, STORAGE_KEY, type Mark } from '../lib/checklist.ts';
import { html } from '../lib/html.ts';

let shared: Checklist | null = null;

/** One checklist per page, kept in sync with other tabs. */
export function getChecklist(): Checklist {
  if (shared) return shared;
  const list = new Checklist(browserStorage());
  try {
    window.addEventListener('storage', (e) => {
      if (e.key === STORAGE_KEY) list.reload();
    });
  } catch {
    /* ignore */
  }
  shared = list;
  return list;
}

/** Bring every [data-checklist] group under `root` up to date and wire its buttons. */
export function bindChecklistButtons(root: ParentNode, list: Checklist): void {
  for (const group of root.querySelectorAll<HTMLElement>('[data-checklist]')) {
    const id = group.dataset.checklist!;
    const marks = list.marks(id);
    for (const btn of group.querySelectorAll<HTMLButtonElement>('button[data-mark]')) {
      const mark = btn.dataset.mark as Mark;
      btn.disabled = false;
      btn.setAttribute('aria-pressed', String(marks[mark]));
      if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => list.toggle(id, mark));
      }
    }
  }
  for (const p of document.querySelectorAll<HTMLElement>('[data-checklist-problem]')) {
    p.hidden = !list.problem;
    p.textContent = list.problem ?? '';
  }
}

function summary(list: Checklist): string {
  const c = list.counts();
  if (c.towers === 0) return 'Your checklist is empty. Mark lookouts as Visited, Stayed overnight or Want to go on the map or on their pages.';
  const parts = MARKS.map((m) => `${c[m]} ${MARK_LABELS[m].toLowerCase()}`);
  return `You have marked ${c.towers} lookout${c.towers === 1 ? '' : 's'}: ${parts.join(', ')}.`;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function initChecklistDialog(list: Checklist): void {
  const dialog = document.getElementById('checklist-dialog') as HTMLDialogElement | null;
  if (!dialog) return;
  dialog.innerHTML = html`<form method="dialog" class="dialog-inner">
    <div class="dialog-head">
      <h2 id="checklist-dialog-h">My checklist</h2>
      <button type="submit" class="icon-btn" value="close" aria-label="Close">
        <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m5 5 10 10M15 5 5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
    </div>
    <p data-cl-summary></p>
    <p class="notice tone-caution" data-cl-problem hidden></p>
    <h3 class="h-small">Download a copy</h3>
    <p class="fine">Saves a small file you can keep as a backup or open on another device. Your checklist lives only in this browser, so clearing browsing data deletes it.</p>
    <p><button type="button" class="btn btn-primary" data-cl-download>Download my checklist</button></p>
    <h3 class="h-small">Import a copy</h3>
    <p class="fine">Adds the lookouts from a Firefinder checklist file to this one. Nothing already here is removed.</p>
    <p><label class="btn file-btn"><input type="file" accept=".json,application/json" data-cl-file class="visually-hidden">Choose a checklist file…</label></p>
    <p role="status" aria-live="polite" data-cl-result></p>
    <div class="dialog-foot"><button type="submit" class="btn" value="close">Done</button></div>
  </form>`.value;

  const refresh = () => {
    dialog.querySelector('[data-cl-summary]')!.textContent = summary(list);
    const prob = dialog.querySelector<HTMLElement>('[data-cl-problem]')!;
    prob.hidden = !list.problem;
    prob.textContent = list.problem ?? '';
  };
  const result = dialog.querySelector<HTMLElement>('[data-cl-result]')!;

  dialog.querySelector('[data-cl-download]')!.addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(list.toFile(), null, 2) + '\n'], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `firefinder-checklist-${today()}.json`;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    result.textContent = `Downloaded ${a.download}.`;
  });

  const file = dialog.querySelector<HTMLInputElement>('[data-cl-file]')!;
  file.addEventListener('change', async () => {
    const f = file.files?.[0];
    file.value = '';
    if (!f) return;
    if (f.size > 5_000_000) {
      result.textContent = 'That file is too large to be a Firefinder checklist.';
      return;
    }
    const r = list.importText(await f.text());
    if (!r.ok) {
      result.textContent = r.error;
    } else {
      const total = r.added.visited + r.added.stayed + r.added.want;
      result.textContent =
        total === 0
          ? 'Everything in that file was already on your checklist.'
          : `Added ${r.added.visited} visited, ${r.added.stayed} stayed overnight and ${r.added.want} want to go.` +
            (r.ignored ? ` ${r.ignored} entries were not lookout ids and were skipped.` : '');
    }
    refresh();
  });

  list.subscribe(refresh);
  document.addEventListener('click', (e) => {
    const opener = (e.target as Element | null)?.closest?.('[data-open-checklist-dialog]');
    if (!opener) return;
    result.textContent = '';
    refresh();
    dialog.showModal();
  });
}

/** Everything a non-map page needs. */
export function initChecklistOnPage(): Checklist {
  const list = getChecklist();
  const sync = () => bindChecklistButtons(document, list);
  sync();
  list.subscribe(sync);
  initChecklistDialog(list);
  return list;
}

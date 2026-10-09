import { describe, expect, it } from 'vitest';
import { Checklist, STORAGE_KEY, browserStorage, type StorageLike } from '../src/lib/checklist.ts';
import type { RedirectsFile } from '../src/lib/redirects.ts';

class MemoryStorage implements StorageLike {
  data = new Map<string, string>();
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
}

class ThrowingStorage implements StorageLike {
  getItem(): string | null {
    throw new DOMException('denied', 'SecurityError');
  }
  setItem(): void {
    throw new DOMException('denied', 'SecurityError');
  }
}

class FullStorage extends MemoryStorage {
  override setItem(): void {
    throw new DOMException('full', 'QuotaExceededError');
  }
}

describe('checklist storage', () => {
  it('saves under firefinder.checklist.v1 and loads it back', () => {
    const store = new MemoryStorage();
    const a = new Checklist(store);
    a.set('us-or-warner-mountain', 'visited', true);
    a.set('us-ca-hirz-mountain', 'want', true);
    expect(JSON.parse(store.getItem(STORAGE_KEY)!)).toEqual({
      version: 1,
      visited: ['us-or-warner-mountain'],
      stayed: [],
      want: ['us-ca-hirz-mountain'],
    });
    const b = new Checklist(store);
    expect(b.marks('us-or-warner-mountain')).toEqual({ visited: true, stayed: false, want: false });
    expect(b.persistent).toBe(true);
    expect(b.problem).toBeNull();
  });

  it('marking "stayed" also marks "visited"; clearing "visited" clears "stayed"', () => {
    const c = new Checklist(new MemoryStorage());
    c.set('us-mt-garnet-mountain', 'stayed', true);
    expect(c.marks('us-mt-garnet-mountain')).toEqual({ visited: true, stayed: true, want: false });
    c.set('us-mt-garnet-mountain', 'visited', false);
    expect(c.marks('us-mt-garnet-mountain')).toEqual({ visited: false, stayed: false, want: false });
  });

  it('keeps working in memory when storage throws on every access', () => {
    const c = new Checklist(new ThrowingStorage());
    expect(c.persistent).toBe(false);
    expect(c.problem).toMatch(/blocked/);
    c.set('us-or-warner-mountain', 'want', true);
    expect(c.has('us-or-warner-mountain', 'want')).toBe(true);
    expect(c.counts()).toEqual({ visited: 0, stayed: 0, want: 1, towers: 1 });
  });

  it('warns but keeps the change when saving fails (quota full)', () => {
    const c = new Checklist(new FullStorage());
    c.set('us-or-warner-mountain', 'visited', true);
    expect(c.has('us-or-warner-mountain', 'visited')).toBe(true);
    expect(c.persistent).toBe(false);
    expect(c.problem).toMatch(/lost/);
  });

  it('works with no storage at all', () => {
    const c = new Checklist(null);
    c.toggle('us-or-warner-mountain', 'visited');
    expect(c.has('us-or-warner-mountain', 'visited')).toBe(true);
    expect(c.persistent).toBe(false);
  });

  it('browserStorage() never throws, even if reading localStorage does', () => {
    const desc = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get() {
        throw new DOMException('denied', 'SecurityError');
      },
    });
    try {
      expect(browserStorage()).toBeNull();
    } finally {
      if (desc) Object.defineProperty(globalThis, 'localStorage', desc);
      else delete (globalThis as { localStorage?: unknown }).localStorage;
    }
  });

  it('keeps a backup of unreadable saved data instead of silently losing it', () => {
    const store = new MemoryStorage();
    store.setItem(STORAGE_KEY, '{not json');
    const c = new Checklist(store);
    expect(c.problem).toMatch(/could not be read/);
    expect(store.getItem(`${STORAGE_KEY}.unreadable-backup`)).toBe('{not json');
  });

  it('ignores ids that are not tower ids', () => {
    const store = new MemoryStorage();
    store.setItem(STORAGE_KEY, JSON.stringify({ visited: ['us-or-ok', '<script>', 42, '../x'] }));
    expect(new Checklist(store).ids('visited')).toEqual(['us-or-ok']);
  });
});

describe('checklist export and import', () => {
  it('exports a self-describing file', () => {
    const c = new Checklist(new MemoryStorage());
    c.set('us-or-a', 'visited', true);
    const file = c.toFile(new Date('2026-10-04T12:00:00Z'));
    expect(file).toEqual({ app: 'firefinder', kind: 'checklist', version: 1, exported: '2026-10-04T12:00:00.000Z', visited: ['us-or-a'], stayed: [], want: [] });
  });

  it('import merges and never removes', () => {
    const c = new Checklist(new MemoryStorage());
    c.set('us-or-a', 'want', true);
    const r = c.importText(JSON.stringify({ app: 'firefinder', visited: ['us-or-b'], stayed: ['us-or-c'], want: ['us-or-a', 'bad id'] }));
    expect(r).toEqual({ ok: true, added: { visited: 2, stayed: 1, want: 0 }, ignored: 1 });
    expect(c.ids('want')).toEqual(['us-or-a']);
    expect(c.ids('visited')).toEqual(['us-or-b', 'us-or-c']);
  });

  it('a round trip through export and import is lossless', () => {
    const a = new Checklist(new MemoryStorage());
    a.set('us-or-a', 'stayed', true);
    a.set('us-wa-b', 'want', true);
    const b = new Checklist(new MemoryStorage());
    b.importData(JSON.parse(JSON.stringify(a.toFile())));
    expect(b.toFile(new Date(0))).toEqual(a.toFile(new Date(0)));
  });

  it('rejects files that are not checklists, with a plain message', () => {
    const c = new Checklist(new MemoryStorage());
    expect(c.importText('not json')).toMatchObject({ ok: false, error: expect.stringMatching(/not valid JSON/) });
    expect(c.importText('[1,2]')).toMatchObject({ ok: false });
    expect(c.importText('{"app":"other","visited":[]}')).toMatchObject({ ok: false, error: expect.stringMatching(/different app/) });
    expect(c.importText('{"hello":1}')).toMatchObject({ ok: false });
  });
});

describe('checklist ticks on retired towers', () => {
  // as written by build_site_data.py: the merge folded the old lookout into the new one
  const file: RedirectsFile = {
    redirects: {
      'us-or-mount-emily': 'us-or-mount-emily-lookout-site-snf',
      'us-id-black-butte-3': 'us-id-black-butte',
      'us-xx-a': 'us-xx-b',
      'us-xx-b': 'us-xx-c',
    },
  };
  const OLD = 'us-or-mount-emily';
  const NEW = 'us-or-mount-emily-lookout-site-snf';

  function saved(store: MemoryStorage) {
    return JSON.parse(store.getItem(STORAGE_KEY)!) as { visited: string[]; stayed: string[]; want: string[] };
  }
  function storeWith(data: Partial<Record<'visited' | 'stayed' | 'want', string[]>>) {
    const store = new MemoryStorage();
    store.setItem(STORAGE_KEY, JSON.stringify({ version: 1, visited: [], stayed: [], want: [], ...data }));
    return store;
  }

  it('moves ticks from a retired id to the survivor and saves them', () => {
    const store = storeWith({ visited: [OLD, 'us-or-other'], want: [OLD] });
    const c = new Checklist(store);
    expect(c.marks(OLD)).toEqual({ visited: true, stayed: false, want: true }); // not known yet
    expect(c.setRedirects(file)).toBe(1);
    expect(c.marks(OLD)).toEqual({ visited: false, stayed: false, want: false });
    expect(c.marks(NEW)).toEqual({ visited: true, stayed: false, want: true });
    expect(c.marks('us-or-other').visited).toBe(true);
    expect(saved(store)).toEqual({ version: 1, visited: [NEW, 'us-or-other'], stayed: [], want: [NEW] });
    // a later page load reads the migrated list as it is
    expect(new Checklist(store).ids('visited')).toEqual([NEW, 'us-or-other']);
  });

  it('notifies listeners once when something moved, and not at all when nothing did', () => {
    const c = new Checklist(storeWith({ visited: [OLD] }));
    let calls = 0;
    c.subscribe(() => calls++);
    c.setRedirects(file);
    expect(calls).toBe(1);
    expect(c.setRedirects(file)).toBe(0);
    expect(calls).toBe(1);
  });

  it('writes nothing when no tick is on a retired id', () => {
    const store = storeWith({ visited: ['us-or-other'] });
    let writes = 0;
    const counting: StorageLike = { getItem: (k) => store.getItem(k), setItem: (k, v) => (writes++, store.setItem(k, v)) };
    const c = new Checklist(counting);
    expect(c.setRedirects(file)).toBe(0);
    expect(writes).toBe(0);
  });

  it('keeps the strongest state when both ids are on the list', () => {
    // stayed (which includes visited) on the old id, plain visited on the survivor
    let c = new Checklist(storeWith({ visited: [OLD, NEW], stayed: [OLD] }));
    c.setRedirects(file);
    expect(c.marks(NEW)).toEqual({ visited: true, stayed: true, want: false });
    // plain visited on the old id, stayed on the survivor
    c = new Checklist(storeWith({ visited: [OLD, NEW], stayed: [NEW] }));
    c.setRedirects(file);
    expect(c.marks(NEW)).toEqual({ visited: true, stayed: true, want: false });
    // want on one, visited on the other: both marks are kept, nothing is lost
    c = new Checklist(storeWith({ want: [OLD], visited: [NEW] }));
    c.setRedirects(file);
    expect(c.marks(NEW)).toEqual({ visited: true, stayed: false, want: true });
    expect(c.counts()).toEqual({ visited: 1, stayed: 0, want: 1, towers: 1 });
  });

  it('follows a chain of retired towers', () => {
    const c = new Checklist(storeWith({ stayed: ['us-xx-a'], visited: ['us-xx-a', 'us-xx-b'] }));
    c.setRedirects(file);
    expect(c.ids('stayed')).toEqual(['us-xx-c']);
    expect(c.ids('visited')).toEqual(['us-xx-c']);
  });

  it('a list that cannot be loaded changes nothing', () => {
    const store = storeWith({ visited: [OLD] });
    const c = new Checklist(store);
    expect(c.setRedirects(null)).toBe(0);
    expect(c.setRedirects(undefined)).toBe(0);
    expect(c.setRedirects({} as RedirectsFile)).toBe(0);
    expect(saved(store).visited).toEqual([OLD]);
  });

  it('marking a retired id marks the survivor', () => {
    const store = new MemoryStorage();
    const c = new Checklist(store);
    c.setRedirects(file);
    c.set(OLD, 'stayed', true);
    expect(c.marks(NEW)).toEqual({ visited: true, stayed: true, want: false });
    expect(saved(store)).toEqual({ version: 1, visited: [NEW], stayed: [NEW], want: [] });
  });

  it('moves ticks that another tab saved under a retired id when the page reloads', () => {
    const store = new MemoryStorage();
    const c = new Checklist(store);
    c.setRedirects(file);
    store.setItem(STORAGE_KEY, JSON.stringify({ version: 1, visited: [OLD], stayed: [], want: [] })); // an old tab
    c.reload();
    expect(c.ids('visited')).toEqual([NEW]);
    expect(saved(store).visited).toEqual([NEW]);
  });

  it('exports retired ids under the survivor, once', () => {
    const c = new Checklist(storeWith({ visited: [OLD, NEW, 'us-id-black-butte-3'], stayed: [OLD], want: ['us-id-black-butte-3'] }));
    // before the list is known the file can only say what is stored
    expect(c.toFile(new Date(0)).visited).toContain(OLD);
    c.setRedirects(file);
    expect(c.toFile(new Date(0))).toEqual({
      app: 'firefinder',
      kind: 'checklist',
      version: 1,
      exported: '1970-01-01T00:00:00.000Z',
      visited: ['us-id-black-butte', NEW],
      stayed: [NEW],
      want: ['us-id-black-butte'],
    });
  });

  it('imports a file made before the merge: retired ids land on the survivor', () => {
    const store = new MemoryStorage();
    const c = new Checklist(store);
    c.setRedirects(file);
    c.set(NEW, 'visited', true);
    const r = c.importData({ app: 'firefinder', visited: [OLD, 'us-or-other'], stayed: [OLD], want: ['us-id-black-butte-3', 'bad id'] });
    // OLD was already visited as NEW; only the stayed mark, the other lookout and the Idaho want are new
    expect(r).toEqual({ ok: true, added: { visited: 1, stayed: 1, want: 1 }, ignored: 1 });
    expect(c.marks(NEW)).toEqual({ visited: true, stayed: true, want: false });
    expect(c.ids('want')).toEqual(['us-id-black-butte']);
    expect(c.has(OLD, 'visited')).toBe(false);
    expect(saved(store).visited).toEqual([NEW, 'us-or-other']);
  });

  it('a file with the old and the new id counts the lookout once', () => {
    const c = new Checklist(new MemoryStorage());
    c.setRedirects(file);
    const r = c.importData({ visited: [OLD, NEW] });
    expect(r).toEqual({ ok: true, added: { visited: 1, stayed: 0, want: 0 }, ignored: 0 });
  });

  it('a round trip between two checklists that both know the list is lossless', () => {
    const a = new Checklist(storeWith({ stayed: [OLD], visited: [OLD], want: ['us-or-other'] }));
    a.setRedirects(file);
    const b = new Checklist(new MemoryStorage());
    b.setRedirects(file);
    b.importData(JSON.parse(JSON.stringify(a.toFile())));
    expect(b.toFile(new Date(0))).toEqual(a.toFile(new Date(0)));
  });

  it('without a list, import and export behave as before', () => {
    const c = new Checklist(new MemoryStorage());
    c.importData({ visited: [OLD] });
    expect(c.toFile(new Date(0)).visited).toEqual([OLD]);
  });
});

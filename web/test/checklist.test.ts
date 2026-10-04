import { describe, expect, it } from 'vitest';
import { Checklist, STORAGE_KEY, browserStorage, type StorageLike } from '../src/lib/checklist.ts';

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

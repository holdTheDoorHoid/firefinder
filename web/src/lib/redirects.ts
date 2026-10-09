/**
 * Lookouts the merge folded into others (data/towers files with `merged_into`, written by
 * pipeline/merge.py when two sources' towers turn out to be one lookout). A tower id is a URL and
 * a checklist key and never changes, so the old id keeps working: pipeline/build_site_data.py
 * lists old id -> new id in redirects.json, the prerender step writes a redirecting page at each
 * old address, and the map follows the same list for `?t=<old id>`.
 */
import { isTowerId } from './tower-id.ts';

export interface RedirectsFile {
  note?: string;
  /** Old tower id -> the id of the tower that has its records now. */
  redirects: Record<string, string>;
}

/** The id to show for `id`: the tower it was folded into, or `id` itself. Follows a chain, never loops. */
export function resolveRedirect(id: string, file: RedirectsFile | null | undefined): string {
  const map = file?.redirects ?? {};
  const seen = new Set<string>();
  let at = id;
  while (Object.hasOwn(map, at) && !seen.has(at)) {
    seen.add(at);
    const next = map[at];
    if (!isTowerId(next)) break;
    at = next;
  }
  return at;
}

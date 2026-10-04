/**
 * Data contracts the site consumes. They are produced by pipeline/build_site_data.py.
 *
 * towers.geojson: one Point feature per visible lookout. Property names are short to keep the
 * file small at ~9,000 features. Absent optional keys mean null / false.
 *
 *   i   id                    "us-or-warner-mountain"   (always)
 *   n   name                  "Warner Mountain Lookout" (always)
 *   r   region (state code)   "OR"                      (always)
 *   k   kind                  vocab.kind                (always)
 *   s   status                vocab.status              (always)
 *   v   verification          vocab.verification        (always)
 *   a   access level          vocab.access              (always)
 *   b   built year            1933                      (absent = unknown)
 *   rt  rentable              1                         (absent = not rentable)
 *   rg  on a register         1  (NHLR, FFLOS, ...)     (absent = not listed)
 *   o   other names           "Old name|Another"        (absent = none)
 *   c   county                "Lane"                    (absent = unknown)
 *
 * Coordinates are [lon, lat] rounded to 5 decimal places (about 1 m).
 */

export interface TowerProps {
  i: string;
  n: string;
  r: string;
  k: string;
  s: string;
  v: string;
  a: string;
  b?: number;
  rt?: 1;
  rg?: 1;
  o?: string;
  c?: string;
}

export interface TowerFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: TowerProps;
}

export interface TowerCollection {
  type: 'FeatureCollection';
  features: TowerFeature[];
}

export interface Register {
  register: string;
  number?: string | null;
  state_number?: string | null;
  url?: string | null;
}

export interface Rental {
  available?: boolean | null;
  provider?: string | null;
  url?: string | null;
  ridb_facility_id?: string | null;
  season?: string | null;
  max_occupancy?: number | null;
  pets?: string | null;
  fee?: string | null;
  rules?: string[] | null;
  access_note?: string | null;
  description?: string | null;
  checked?: string | null;
  /**
   * Set when another source records the lookout as gone or burned while recreation.gov still
   * lists it ("FFLA reports this lookout burned in 2026, but recreation.gov still lists it.
   * Check with the forest before booking."). `available` is then false: the listing is shown
   * with this warning above its link, and the lookout is not counted as rentable.
   */
  warning?: string | null;
}

export interface TowerEvent {
  year?: number | null;
  event: string;
  note?: string | null;
  /** Source id the event comes from. */
  from?: string | null;
  /** For "relocated": the place the structure was moved from, and to. */
  moved_from?: string | null;
  moved_to?: string | null;
}

export interface Photo {
  /** Mirrored copy, relative to the data folder ("photos/<id>/1.jpg"). Preferred. */
  file?: string | null;
  /** Smaller copy for grids, relative to the data folder. */
  thumb?: string | null;
  /** Original image URL; used when there is no mirrored file. */
  url?: string | null;
  /** The page the photo came from (for the credit link). */
  source_url?: string | null;
  credit?: string | null;
  license?: string | null;
  caption?: string | null;
  year?: number | null;
}

export interface Link {
  label: string;
  url: string;
  /** "relocated_from" / "relocated_to" link two tower pages (by `id`); others are external. */
  kind?: string | null;
  /** Tower id, for links to another Firefinder tower page. */
  id?: string | null;
}

export interface SourceRef {
  source: string;
  key?: string | null;
  fields?: string[] | null;
  url?: string | null;
}

export interface ConflictValue {
  source: string;
  value: unknown;
}

export interface Conflict {
  field: string;
  values?: ConflictValue[] | null;
  distance_m?: number | null;
  note?: string | null;
}

export interface TowerRecord {
  id: string;
  name: string;
  other_names?: string[] | null;
  country?: string | null;
  region: string;
  county?: string | null;
  location: { lat: number; lon: number; precision?: string | null; from?: string | null };
  elevation_m?: number | null;
  kind: string;
  design?: string | null;
  height_m?: number | null;
  status: string;
  registers?: Register[] | null;
  agency?: string | null;
  ownership?: string | null;
  access?: { level: string; note?: string | null } | null;
  staffing?: { status: string; as_of?: string | null } | null;
  visit?: { climbable?: boolean | null; drive_up?: boolean | null; trail_note?: string | null } | null;
  rental?: Rental | null;
  events?: TowerEvent[] | null;
  photos?: Photo[] | null;
  links?: Link[] | null;
  sources?: SourceRef[] | null;
  conflicts?: Conflict[] | null;
  verification: string;
  updated?: string | null;
  /** True for sample records in web/fixtures. */
  fixture?: boolean;
  /** Added by the pipeline from data/stories/<id>.md, already converted and escaped. */
  story_html?: string | null;
}

export interface SourceInfo {
  id: string;
  title: string;
  url?: string | null;
  license?: string | null;
  credit?: string | null;
  retrieved?: string | null;
  records?: number | null;
  towers?: number | null;
}

export interface Meta {
  built: string;
  fixtures: boolean;
  counts: {
    total: number;
    hidden?: number;
    rentable?: number;
    registered?: number;
    stories?: number;
    by_status?: Record<string, number>;
    by_kind?: Record<string, number>;
    by_region?: Record<string, number>;
    by_verification?: Record<string, number>;
  };
  sources: SourceInfo[];
}

export function isRentable(r: Pick<TowerRecord, 'rental'>): boolean {
  return !!r.rental && r.rental.available !== false;
}

export function builtYear(r: Pick<TowerRecord, 'events'>): number | null {
  let best: number | null = null;
  for (const e of r.events ?? []) {
    if (e.event === 'built' && typeof e.year === 'number' && (best === null || e.year < best)) best = e.year;
  }
  return best;
}

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
 *   y0  first year it stood   1933 (built, rebuilt, replaced, first staffed)  (absent = unknown)
 *   y1  year it came down     1975 (destroyed, burned, removed, abandoned)
 *                             (absent = still standing, or not recorded: see lib/history.ts)
 *   d   design ids            "l4" or "l4|r6" (designs.json ids)            (absent = none recognised)
 *   m   material              vocab.material ("steel")                      (absent = not recorded)
 *
 * Sites with no structure (k = camp, tree or point: vocab.ts NO_STRUCTURE_KINDS) are in the
 * file too; the map leaves them off until the visitor switches them on.
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
  y0?: number;
  y1?: number;
  d?: string;
  m?: string;
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
   * Where this rental record came from. Missing means recreation.gov (RIDB); "ffla" means the
   * Forest Fire Lookout Association's rentals list (firelookout.org/resources/rentals/), which is
   * the only source for rentals booked elsewhere (state parks, private owners on Airbnb).
   */
  source?: string | null;
  /** Who runs the rental when it is not the Forest Service ("private owner", "MT DNRC"). */
  manager?: string | null;
  /**
   * A closure or unavailability the FFLA's rentals list notes ("Maintenance Closure 2026",
   * "Currently Unavailable"). The lookout stays a rental (`available` is not touched); the page
   * shows the note beside the booking link. `status_note_from` names who said it ("ffla").
   */
  status_note?: string | null;
  status_note_from?: string | null;
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
  /** The page that supports the event (research events cite one). */
  source_url?: string | null;
  source_urls?: string[] | null;
  /** For "relocated": the place the structure was moved from, and to. */
  moved_from?: string | null;
  moved_to?: string | null;
}

export interface Photo {
  /** Mirrored copy, relative to site.config.json's "photosBase" (e.g. "ab/abc123.webp"). */
  file?: string | null;
  /** Smaller copy for grids, relative to "photosBase" the same way. */
  thumb?: string | null;
  /** Original image URL; used when there is no mirrored file, or photosBase is not set. */
  url?: string | null;
  /** The page the photo came from (for the credit link). */
  source_url?: string | null;
  credit?: string | null;
  license?: string | null;
  caption?: string | null;
  year?: number | null;
  /** Pixel size of the original (from data/photos_manifest.json), for the <img> attributes. */
  w?: number | null;
  h?: number | null;
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

export interface ResearchStamp {
  researched?: string | null;
  checked?: string | null;
  verdict?: 'pass' | 'fixed' | 'fail' | null;
  confidence?: string | null;
}

export interface TowerRecord {
  id: string;
  name: string;
  /** One-sentence teaser from research, shown on the map panel and page header. */
  summary?: string | null;
  /** When the story was researched and fact-checked (pipeline research overlay). */
  research?: ResearchStamp | null;
  other_names?: string[] | null;
  country?: string | null;
  region: string;
  county?: string | null;
  location: { lat: number; lon: number; precision?: string | null; from?: string | null };
  elevation_m?: number | null;
  kind: string;
  /** What the main structure is built of (vocab.material), or null when no source says. */
  material?: string | null;
  /** Where the material came from: a source id, or "design" (read off a recognised design). */
  material_from?: string | null;
  /** Jobs the site did that are not a kind of building (vocab.role: "aws"). */
  roles?: string[] | null;
  design?: string | null;
  height_m?: number | null;
  status: string;
  /** A note on the status, shown beside it ("Sources suggest it is gone."). */
  status_note?: string | null;
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
  /** Plain summary written from the record alone (no research); only when there is no story. */
  auto_summary?: string | null;
  /** Standard designs recognised by the pipeline (designs.json ids, e.g. ["l4"]). */
  design_ids?: string[] | null;
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
    /** Every site on the map, including sites with no structure. */
    total: number;
    /** Towers and buildings (the map's default view). */
    structures?: number;
    /** Camps, lookout trees and bare points. */
    no_structure?: number;
    hidden?: number;
    rentable?: number;
    registered?: number;
    stories?: number;
    by_status?: Record<string, number>;
    by_kind?: Record<string, number>;
    by_region?: Record<string, number>;
    by_verification?: Record<string, number>;
    by_material?: Record<string, number>;
  };
  sources: SourceInfo[];
  /** How many lookouts can be placed in time (pipeline build_site_data.history_counts). */
  history?: HistoryCounts;
  /** How many lookouts have a recognisable design (pipeline build_site_data.write_designs). */
  designs?: DesignCoverage;
}

/** structure_kinds.json: the "Structure types" guide (pipeline/build_site_data.write_structure_kinds). */
export interface StructureKind {
  id: string;
  label: string;
  group: string;
  about?: string | null;
  count: number;
  /** The sources' own words for this kind ("Rooftop", "Grain Elevator"). */
  source_words?: string[] | null;
}

export interface StructureGroup {
  id: string;
  label: string;
  shown_by_default?: boolean | null;
  about?: string | null;
  count: number;
}

export interface StructureKindsFile {
  title?: string | null;
  updated?: string | null;
  groups: StructureGroup[];
  kinds: StructureKind[];
  materials: { id: string; label: string; about?: string | null; count: number }[];
  roles?: { id: string; label: string; about?: string | null }[] | null;
  counts?: { structures: number; no_structure: number; with_material: number } | null;
}

/** Counts over lookout structures only: sites with no structure are left out. */
export interface HistoryCounts {
  this_year: number;
  total: number;
  with_start: number;
  with_end: number;
  standing_now: number;
  complete: number;
  start_no_end: number;
  end_no_start: number;
  standing_no_start: number;
  no_dates: number;
  no_dates_not_standing: number;
  first_year: number | null;
}

export interface DesignCoverage {
  total: number;
  with_design_text: number;
  recognised: number;
  by_design: Record<string, number>;
}

/** One lookout in designs.json: id, name, state, status, kind, source wording, Aermotor models. */
export interface DesignTower {
  i: string;
  n: string;
  r: string;
  s: string;
  k: string;
  w?: string;
  m?: string[];
}

export interface DesignSource {
  title: string;
  publisher?: string | null;
  url?: string | null;
  licence?: string | null;
  supports?: string[] | null;
}

export interface Design {
  id: string;
  name: string;
  aka?: string[] | null;
  kind?: string | null;
  schematic?: string | null;
  summary?: string | null;
  years_in_use?: { from?: number | null; to?: number | null; text?: string | null } | null;
  cab_size?: string | null;
  tower_heights?: string | null;
  materials?: string | null;
  makers?: string[] | null;
  models?: string[] | null;
  regions?: string | null;
  features?: string[] | null;
  uncertain?: string | null;
  sources?: DesignSource[] | null;
  towers: DesignTower[];
  count: number;
  by_status: Record<string, number>;
}

export interface DesignsFile {
  title?: string | null;
  note?: string | null;
  updated?: string | null;
  sources?: DesignSource[];
  coverage: DesignCoverage;
  designs: Design[];
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

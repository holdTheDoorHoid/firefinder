/**
 * Countries and their regions (states, provinces, territories), mirroring pipeline/regions.py
 * (DESIGN.md 3.3, "Countries and regions"; owner decision 2026-10-20: Alaska, Hawaii and Canada
 * join the lower 48). Region codes are unique across the countries listed, so a tower's region
 * code alone says its country.
 *
 * Units (DESIGN.md 4, "Units"): a US lookout's page reads feet first with metres alongside; a
 * lookout anywhere else reads metres first with feet alongside. Distances follow the same rule
 * (miles first in the US, kilometres first elsewhere).
 */

export const COUNTRY_NAMES: Record<string, string> = { US: 'United States', CA: 'Canada' };
/** As running text says it: "in the United States", "in Canada". */
export const COUNTRY_IN_TEXT: Record<string, string> = { US: 'the United States', CA: 'Canada' };
/** Listed in this order: the US's states first, then Canada's provinces and territories. */
export const COUNTRY_ORDER = ['US', 'CA'] as const;

export const US_REGIONS: Record<string, string> = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado',
  CT: 'Connecticut', DE: 'Delaware', DC: 'District of Columbia', FL: 'Florida', GA: 'Georgia',
  HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas',
  KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts',
  MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri', MT: 'Montana',
  NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico',
  NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma',
  OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota',
  TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington',
  WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming', PR: 'Puerto Rico', GU: 'Guam',
  VI: 'U.S. Virgin Islands', AS: 'American Samoa', MP: 'Northern Mariana Islands',
};

export const CA_REGIONS: Record<string, string> = {
  AB: 'Alberta', BC: 'British Columbia', MB: 'Manitoba', NB: 'New Brunswick',
  NL: 'Newfoundland and Labrador', NS: 'Nova Scotia', NT: 'Northwest Territories', NU: 'Nunavut',
  ON: 'Ontario', PE: 'Prince Edward Island', QC: 'Quebec', SK: 'Saskatchewan', YT: 'Yukon',
};

export const REGIONS_BY_COUNTRY: Record<string, Record<string, string>> = { US: US_REGIONS, CA: CA_REGIONS };

/** Every region code and its English name. */
export const REGIONS: Record<string, string> = { ...US_REGIONS, ...CA_REGIONS };

const REGION_COUNTRY: Record<string, string> = Object.fromEntries(
  Object.entries(REGIONS_BY_COUNTRY).flatMap(([c, tbl]) => Object.keys(tbl).map((code) => [code, c])),
);

/** "ON" -> "CA", "OR" -> "US"; null for an unknown code. */
export function countryOf(region: string | null | undefined): string | null {
  return region ? (REGION_COUNTRY[region.toUpperCase()] ?? null) : null;
}

/** The country of a tower: its own field, else its region's, else the US. */
export function towerCountry(r: { country?: string | null; region?: string | null; cc?: string }): string {
  return r.country || r.cc || countryOf(r.region) || 'US';
}

export function regionName(code: string | null | undefined): string {
  if (!code) return 'Unknown region';
  return REGIONS[code.toUpperCase()] ?? code;
}

/** "Oregon"; "Ontario, Canada" outside the US. */
export function regionWithCountry(code: string | null | undefined): string {
  const name = regionName(code);
  const c = countryOf(code);
  return c && c !== 'US' ? `${name}, ${COUNTRY_NAMES[c]}` : name;
}

/** "state" / "states" in the US, "province or territory" / "provinces and territories" in Canada. */
export function regionWord(country: string | null | undefined, plural = false): string {
  if (country === 'CA') return plural ? 'provinces and territories' : 'province or territory';
  return plural ? 'states' : 'state';
}

/** The word for one region: "state", "province" or "territory". */
export function regionKind(code: string | null | undefined): string {
  const c = (code ?? '').toUpperCase();
  if (countryOf(c) === 'CA') return ['NT', 'NU', 'YT'].includes(c) ? 'territory' : 'province';
  if (['PR', 'GU', 'VI', 'AS', 'MP'].includes(c)) return 'territory';
  return 'state';
}

export interface RegionGroup {
  country: string;
  name: string;
  regions: { code: string; name: string }[];
}

/**
 * The regions to list, grouped by country (US first, then Canada), each alphabetical by name.
 * `only` keeps the ones present (codes with towers); omit it for every region.
 */
export function regionGroups(only?: Iterable<string>): RegionGroup[] {
  const keep = only ? new Set([...only].map((c) => c.toUpperCase())) : null;
  return COUNTRY_ORDER.map((country) => ({
    country,
    name: COUNTRY_NAMES[country]!,
    regions: Object.entries(REGIONS_BY_COUNTRY[country]!)
      .filter(([code]) => !keep || keep.has(code))
      .map(([code, name]) => ({ code, name }))
      .sort((a, b) => a.name.localeCompare(b.name)),
  })).filter((g) => g.regions.length > 0);
}

/** Feet first in the US, metres first everywhere else. */
export function metricFirst(country: string | null | undefined): boolean {
  return (country ?? 'US') !== 'US';
}

/* Alaska's census areas (the rest of its units are boroughs or carry their own words). */
const AK_CENSUS_AREAS = new Set([
  'aleutians west', 'bethel', 'chugach', 'copper river', 'dillingham', 'hoonah-angoon', 'kusilvak', 'nome',
  'prince of wales-hyder', 'southeast fairbanks', 'yukon-koyukuk', 'valdez-cordova', 'wade hampton',
  'skagway-hoonah-angoon', 'wrangell-petersburg', 'prince of wales-outer ketchikan',
]);

/**
 * A local unit as a page writes it: "Jefferson County", "Caddo Parish", "Bethel Census Area",
 * "Matanuska-Susitna Borough". Canadian units carry their own words ("Sudbury District",
 * "Regional District of Central Kootenay", "Division No. 18") and are shown as given.
 */
export function localUnitLabel(country: string | null | undefined, region: string | null | undefined, county: string): string {
  const c = county.trim();
  if ((country ?? countryOf(region) ?? 'US') !== 'US') return c;
  if (/\b(County|Parish|Borough|Census Area|Municipality|City)$/i.test(c)) return c;
  if (region === 'LA') return `${c} Parish`;
  if (region === 'AK') return AK_CENSUS_AREAS.has(c.toLowerCase()) ? `${c} Census Area` : `${c} Borough`;
  return `${c} County`;
}

/* ---------- Map views ---------- */

export interface MapView {
  id: string;
  label: string;
  /** [[west, south], [east, north]] */
  bounds: [[number, number], [number, number]];
}

/**
 * Quick-jumps on the map. The default view is the lower 48 with southern Canada; Alaska, Hawaii
 * and the north are a click away (one box holding Hawaii, Alaska and Newfoundland would show
 * mostly ocean at phone width).
 */
export const MAP_VIEWS: MapView[] = [
  { id: 'all', label: 'All', bounds: [[-170, 17], [-50, 72]] },
  { id: 'us', label: 'Lower 48', bounds: [[-125.5, 24.0], [-66.5, 49.6]] },
  { id: 'ak', label: 'Alaska', bounds: [[-170, 51], [-129.5, 71.5]] },
  { id: 'hi', label: 'Hawaii', bounds: [[-160.6, 18.7], [-154.6, 22.4]] },
  { id: 'ca', label: 'Canada', bounds: [[-141, 41.6], [-52.6, 70]] },
];

/** The default map view: the lower 48 and the populated south of Canada. */
export const DEFAULT_VIEW: [[number, number], [number, number]] = [[-126, 24.5], [-60, 55]];

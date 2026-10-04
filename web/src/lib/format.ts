/** Formatting helpers shared by the map and the prerendered pages. Pure, no DOM. */

const nf = new Intl.NumberFormat('en-US');

export function formatCount(n: number): string {
  return nf.format(n);
}

/** "5,930 ft (1,807 m)". US visitors read feet first; metres stay alongside. */
export function feetAndMetres(metres: number | null | undefined, decimals = 0): string | null {
  if (typeof metres !== 'number' || !Number.isFinite(metres)) return null;
  const feet = Math.round(metres / 0.3048);
  const m = decimals ? metres.toFixed(decimals) : nf.format(Math.round(metres));
  return `${nf.format(feet)} ft (${m} m)`;
}

/** "44.55774, −121.70876" with a real minus sign. */
export function formatCoords(lat: number, lon: number): string {
  const f = (v: number) => v.toFixed(5).replace('-', '−');
  return `${f(lat)}, ${f(lon)}`;
}

/** Plain "44.55774,-121.70876" for copying into other apps. */
export function plainCoords(lat: number, lon: number): string {
  return `${lat.toFixed(5)},${lon.toFixed(5)}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-10-03" -> "3 Oct 2026". Anything else is returned unchanged. */
export function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}`;
}

/** Distance in metres between two WGS84 points (haversine). */
export function distanceMetres(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371008.8;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/** "820 m" or "2.4 km" (and miles alongside for long distances). */
export function formatDistance(metres: number): string {
  if (metres < 1000) return `${nf.format(Math.round(metres / 10) * 10 || Math.round(metres))} m`;
  const km = metres / 1000;
  const mi = metres / 1609.344;
  return `${km.toFixed(km < 10 ? 1 : 0)} km (${mi.toFixed(mi < 10 ? 1 : 0)} mi)`;
}

export function yesNo(v: boolean | null | undefined, yes: string, no: string, unknown = 'Unknown'): string {
  return v === true ? yes : v === false ? no : unknown;
}

/**
 * Plain-language pieces of the 3D views: how high the eye is (and why), bearings the way a
 * lookout says them, distances. Pure functions, no DOM; tested in test/view3d.test.ts.
 */

const nf = new Intl.NumberFormat('en-US');

/** A person standing in the cab: eyes about 1.6 m above the floor. */
export const EYE_ABOVE_FLOOR_M = 1.6;

/** Lookouts east of about 100°W are mostly tall steel towers; western ones mostly short. */
export const EAST_WEST_LONGITUDE = -100;

export type EyeSource = 'recorded' | 'typical' | 'custom';

export interface EyeHeight {
  /** Floor of the cab (or platform) above the ground, m. */
  floorM: number;
  /** Eye above the ground, m. */
  eyeM: number;
  source: EyeSource;
  /** One sentence for the page: the height and where it comes from. */
  sentence: string;
  /** A short label for the control: "Typical 30-ft western tower". */
  short: string;
}

interface Typical {
  floorM: number;
  why: string;
  short: string;
}

/** The documented defaults, by kind of structure and region. */
export function typicalFloor(kind: string, lon: number): Typical {
  const east = lon > EAST_WEST_LONGITUDE;
  switch (kind) {
    case 'ground':
      return { floorM: 2.5 - EYE_ABOVE_FLOOR_M, why: 'typical for a ground-level cab', short: 'Typical ground cab' };
    case 'two_story':
      return { floorM: 6 - EYE_ABOVE_FLOOR_M, why: 'typical for the upper floor of a two-story lookout', short: 'Typical two-story lookout' };
    case 'three_story':
      return { floorM: 9 - EYE_ABOVE_FLOOR_M, why: 'typical for the top floor of a three-story lookout', short: 'Typical three-story lookout' };
    case 'mobile':
      return { floorM: 2.5 - EYE_ABOVE_FLOOR_M, why: 'typical for a trailer or portable cab', short: 'Typical trailer cab' };
    case 'rooftop':
      return { floorM: 6 - EYE_ABOVE_FLOOR_M, why: 'about two stories up, for a cab on a building roof', short: 'Typical rooftop cab' };
    case 'tree':
      return { floorM: 15, why: 'a platform about 50 ft up a tree, a middling height for the lookout trees in our sources', short: 'Typical lookout tree' };
    case 'camp':
    case 'point':
      return { floorM: 0, why: 'a person standing on the ground: nothing was built here', short: 'Standing on the ground' };
    default: {
      const unknown = !['tower', 'enclosed_tower', 'platform'].includes(kind);
      const lead = unknown ? "the kind of structure isn't recorded, so this assumes " : '';
      return east
        ? {
            floorM: 20,
            why: `${lead}a typical steel tower east of the Great Plains, with the cab about 66 ft up`,
            short: 'Typical 66-ft eastern steel tower',
          }
        : {
            floorM: 9.1,
            why: `${lead}a typical western tower, with the cab about 30 ft up`,
            short: 'Typical 30-ft western tower',
          };
    }
  }
}

/** "10.7 m (35 ft)" */
export function metresFeet(m: number, decimals = 1): string {
  const ft = Math.round(m / 0.3048);
  return `${m >= 100 ? nf.format(Math.round(m)) : m.toFixed(decimals)} m (${nf.format(ft)} ft)`;
}

/**
 * The eye height for a lookout: its recorded height to the cab floor plus 1.6 m, or a typical
 * height for its kind and region when the height is not recorded. `customEyeM` overrides both.
 */
export function eyeHeight(r: { kind: string; height_m?: number | null; lon: number }, customEyeM?: number | null): EyeHeight {
  if (typeof customEyeM === 'number' && Number.isFinite(customEyeM) && customEyeM > 0) {
    const eye = Math.min(customEyeM, 500);
    return {
      floorM: Math.max(eye - EYE_ABOVE_FLOOR_M, 0),
      eyeM: eye,
      source: 'custom',
      sentence: `Eye height ${metresFeet(eye)} above the ground, as you set it.`,
      short: 'Your height',
    };
  }
  const h = r.height_m;
  if (typeof h === 'number' && Number.isFinite(h) && h > 0 && h < 200) {
    const eye = h + EYE_ABOVE_FLOOR_M;
    return {
      floorM: h,
      eyeM: eye,
      source: 'recorded',
      sentence: `Eye height ${metresFeet(eye)} above the ground: the recorded height of the structure, ${metresFeet(h)}, taken as the cab floor, plus ${EYE_ABOVE_FLOOR_M} m for a person standing in the cab.`,
      short: 'Recorded height',
    };
  }
  const t = typicalFloor(r.kind, r.lon);
  const eye = t.floorM + EYE_ABOVE_FLOOR_M;
  return {
    floorM: t.floorM,
    eyeM: eye,
    source: 'typical',
    sentence: `Eye height ${metresFeet(eye)} above the ground (${t.why}; the real height isn't recorded).`,
    short: t.short,
  };
}

/** How a lookout's view is grounded in fact, for gone and moved structures. */
export function reconstructionNote(status: string, source: EyeSource): string | null {
  const height = source === 'recorded' ? 'its recorded height' : 'a typical height for a lookout like it';
  if (status === 'gone' || status === 'ruins') {
    return `This lookout is gone. The view is reconstructed from its recorded site and ${height}.`;
  }
  if (status === 'relocated') {
    return `The structure was moved. This view is from the position Firefinder shows for this record, at ${height}.`;
  }
  if (status === 'replica') return `A replica stands here. The view is from its site at ${height}.`;
  return null;
}

/* ---------- Bearings ---------- */

export function wrap360(a: number): number {
  const r = ((a % 360) + 360) % 360;
  return r >= 360 ? 0 : r;
}

const CARDINAL_WORDS: Record<number, string> = { 0: 'due north', 90: 'due east', 180: 'due south', 270: 'due west' };

/**
 * A quadrant bearing as lookouts and surveyors say it: 45° -> "N 45° E", 200° -> "S 20° W".
 * Whole degrees by default; exact cardinal directions read "due north" etc.
 */
export function quadrantBearing(az: number, decimals = 0): string {
  const f = 10 ** decimals;
  const a = wrap360(Math.round(az * f) / f);
  if (CARDINAL_WORDS[a]) return CARDINAL_WORDS[a]!;
  let ns: 'N' | 'S';
  let ew: 'E' | 'W';
  let angle: number;
  if (a < 90) [ns, ew, angle] = ['N', 'E', a];
  else if (a < 180) [ns, ew, angle] = ['S', 'E', 180 - a];
  else if (a < 270) [ns, ew, angle] = ['S', 'W', a - 180];
  else [ns, ew, angle] = ['N', 'W', 360 - a];
  return `${ns} ${angle.toFixed(decimals)}° ${ew}`;
}

/** "045°" style azimuth, as read off the Firefinder's ring. */
export function azimuthText(az: number, decimals = 0): string {
  const f = 10 ** decimals;
  const a = wrap360(Math.round(az * f) / f);
  const s = a.toFixed(decimals);
  const [int, frac] = s.split('.');
  return `${int!.padStart(3, '0')}${frac ? `.${frac}` : ''}°`;
}

const POINTS16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
export function compassPoint(az: number): string {
  return POINTS16[Math.round(wrap360(az) / 22.5) % 16]!;
}

/** Signed difference b - a in degrees, in -180..180. */
export function angleDiff(a: number, b: number): number {
  return ((b - a + 540) % 360) - 180;
}

/* ---------- Distances ---------- */

/** "21 mi (34 km)" for the list; miles first for US readers. */
export function milesKm(m: number): string {
  if (m < 300) return `${nf.format(Math.round(m / 0.3048 / 10) * 10)} ft (${nf.format(Math.round(m / 10) * 10)} m)`;
  const mi = m / 1609.344;
  const km = m / 1000;
  const d = (v: number) => (v < 10 ? v.toFixed(1) : nf.format(Math.round(v)));
  return `${d(mi)} mi (${d(km)} km)`;
}

/** "21 mi" for compact labels. */
export function milesShort(m: number): string {
  const mi = m / 1609.344;
  return `${mi < 10 ? mi.toFixed(1) : nf.format(Math.round(mi))} mi`;
}

/** "about 6,960 ft" from metres. */
export function aboutFeet(m: number): string {
  return `about ${nf.format(Math.round(m / 0.3048 / 10) * 10)} ft`;
}

/** "412 sq mi (1,067 km²)" */
export function areaText(m2: number): string {
  const km2 = m2 / 1e6;
  const mi2 = m2 / 2_589_988.11;
  const r = (v: number) => nf.format(v < 10 ? Math.round(v * 10) / 10 : Math.round(v));
  return `${r(mi2)} sq mi (${r(km2)} km²)`;
}

/** "2.4 MB" */
export function megabytes(bytes: number): string {
  const mb = bytes / 1_048_576;
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`;
}

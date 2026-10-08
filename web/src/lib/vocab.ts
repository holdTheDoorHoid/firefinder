/**
 * Plain-language wording for the controlled vocabularies in data/vocab.json.
 * data/vocab.json is the data contract; this file is how the site says it to people.
 * test/vocab.test.ts checks that every code in data/vocab.json has wording here.
 * Unknown codes (added to the data later) fall back to the raw code, never a crash.
 */

export interface Wording {
  label: string;
  /** One sentence a first-time visitor understands. */
  meaning: string;
}

export const STATUS: Record<string, Wording> = {
  standing: { label: 'Standing', meaning: 'The lookout still stands.' },
  gone: { label: 'Gone', meaning: 'The lookout no longer stands. Only the site is left.' },
  ruins: { label: 'Ruins', meaning: 'Only footings or remains are left.' },
  relocated: {
    label: 'Moved',
    meaning: 'The structure was moved. The map shows where it stands now; the timeline says where it came from.',
  },
  replica: { label: 'Replica', meaning: 'A replica stands here, not the original structure.' },
  unknown: { label: 'Status unknown', meaning: 'We do not know yet whether it still stands.' },
};

/**
 * Kinds of structure. Labels match data/structure_kinds.json (the "Structure types" guide's
 * own file, with a paragraph per kind); test/vocab-and-search checks they agree.
 */
export const KIND: Record<string, Wording> = {
  tower: { label: 'Cab on a tower', meaning: 'A lookout cab (or platform) raised on a tower.' },
  enclosed_tower: { label: 'Enclosed tower', meaning: 'A tower enclosed from the ground up.' },
  platform: { label: 'Open platform tower', meaning: 'An open tower or raised platform with no cab, including crow\'s nests.' },
  ground: { label: 'Ground-level cab', meaning: 'A lookout cab or house built at ground level.' },
  two_story: { label: 'Two-story building', meaning: 'A two-story lookout building.' },
  three_story: { label: 'Three-story building', meaning: 'A three-story lookout building.' },
  rooftop: { label: 'Cab on a rooftop', meaning: 'A lookout cab on the roof of another building, such as a ranger station or hotel.' },
  mobile: { label: 'Trailer or portable cab', meaning: 'A trailer, converted bus or portable cab used as a lookout.' },
  unknown: { label: 'Type unknown', meaning: 'We do not know what kind of structure it was.' },
  camp: { label: 'Summit camp', meaning: 'No structure: the observer watched from a summit and lived in a tent.' },
  tree: { label: 'Lookout tree', meaning: 'No structure: a tall tree with a ladder and a platform near the top.' },
  point: { label: 'Bare lookout point', meaning: 'No structure: a summit with only a firefinder or map board to take bearings.' },
};

/** Sites where nothing was built to stand in. The map leaves them off until switched on. */
export const NO_STRUCTURE_KINDS: readonly string[] = ['camp', 'tree', 'point'];
export const NO_STRUCTURE_LABEL = 'Sites with no structure';
export const NO_STRUCTURE_MEANING = 'Summit camps, lookout trees and bare lookout points: places a lookout kept watch without a tower or building.';

export function isNoStructure(kind: string): boolean {
  return NO_STRUCTURE_KINDS.includes(kind);
}

/** What the main structure is built of (the tower for a tower, the walls for a building). */
export const MATERIAL: Record<string, Wording> = {
  steel: { label: 'Steel', meaning: 'A steel or iron frame, usually galvanized.' },
  wood: { label: 'Wood', meaning: 'Timber, poles or a wood frame.' },
  log: { label: 'Logs', meaning: 'Logs, as in a log cabin or a log crib under the cab.' },
  stone: { label: 'Stone', meaning: 'Stone or rock walls.' },
  concrete: { label: 'Concrete', meaning: 'Poured concrete.' },
  masonry: { label: 'Brick or block', meaning: 'Brick, cinder block or concrete block.' },
  mixed: { label: 'Mixed', meaning: 'A source names two main materials, such as stone and logs.' },
};

/** Jobs a site did that are not a kind of building. */
export const ROLE: Record<string, Wording> = {
  aws: {
    label: 'Aircraft Warning Service post',
    meaning: 'During the Second World War it was staffed to spot and report aircraft.',
  },
};

export const ACCESS: Record<string, Wording & { tone: 'ok' | 'caution' | 'stop' | 'unknown' }> = {
  public: { label: 'Open to the public', meaning: 'Anyone may visit.', tone: 'ok' },
  restricted: {
    label: 'Restricted access',
    meaning: 'Access is seasonal, gated or needs a permit. Check before you go.',
    tone: 'caution',
  },
  permission: {
    label: 'Permission required',
    meaning: 'You need permission from the tribe or landowner before visiting.',
    tone: 'stop',
  },
  private: {
    label: 'Private land',
    meaning: 'No public access. Please do not trespass; view it only from public land.',
    tone: 'stop',
  },
  closed: { label: 'Closed', meaning: 'The site is closed to visitors.', tone: 'stop' },
  unknown: {
    label: 'Access unknown',
    meaning: 'We do not know the access rules. Check with the land manager before you go.',
    tone: 'unknown',
  },
};

/** Tribal land gets its own wording; the data says it via ownership = tribal. */
export const TRIBAL_ACCESS: Wording = {
  label: 'Tribal land: permission required',
  meaning: 'This site is on tribal land. Ask the tribe for permission before visiting, and follow its rules.',
};

export const VERIFICATION: Record<string, Wording> = {
  unverified: {
    label: 'Unverified',
    meaning: 'From a single source and not yet checked. Details may be wrong.',
  },
  facts: { label: 'Facts agree', meaning: 'Two or more independent sources agree on the location and status.' },
  researched: { label: 'Researched', meaning: 'Its history has been researched and written up.' },
  verified: { label: 'Verified', meaning: 'Researched, then checked independently.' },
};

export const STAFFING: Record<string, string> = {
  staffed: 'Staffed during fire season',
  emergency: 'Staffed only in emergencies',
  volunteer: 'Staffed by volunteers',
  unstaffed: 'Not staffed',
  unknown: 'Unknown',
};

export const OWNERSHIP: Record<string, string> = {
  federal: 'Federal land',
  state: 'State land',
  tribal: 'Tribal land',
  local: 'County or city land',
  private: 'Private land',
  unknown: 'Unknown',
};

export const EVENT: Record<string, string> = {
  built: 'Built',
  rebuilt: 'Rebuilt',
  replaced: 'Replaced by a new structure',
  staffed_first: 'First staffed',
  staffed_last: 'Last staffed',
  abandoned: 'Abandoned',
  destroyed: 'Destroyed',
  burned: 'Burned',
  removed: 'Removed',
  relocated: 'Moved',
  restored: 'Restored',
  rental_opened: 'Opened as a rental',
  nrhp_listed: 'Listed on the National Register of Historic Places',
  nhlr_registered: 'Added to the National Historic Lookout Register',
  fflos_registered: 'Added to the Former Fire Lookout Sites Register',
  staffed: 'Staffed',
  modified: 'Altered',
  fire: 'Fire',
  closed: 'Closed',
  assessed: 'Condition assessment',
  other: 'Event',
};

export const REGISTER_NAMES: Record<string, string> = {
  NHLR: 'National Historic Lookout Register',
  FFLOS: 'Former Fire Lookout Sites Register',
  NRHP: 'National Register of Historic Places',
};

export const REGIONS: Record<string, string> = {
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

export function regionName(code: string | null | undefined): string {
  if (!code) return 'Unknown state';
  return REGIONS[code.toUpperCase()] ?? code;
}

export function statusWording(code: string): Wording {
  return STATUS[code] ?? { label: code, meaning: '' };
}
export function kindWording(code: string): Wording {
  return KIND[code] ?? { label: code, meaning: '' };
}
export function materialWording(code: string): Wording {
  return MATERIAL[code] ?? { label: code, meaning: '' };
}
export function roleWording(code: string): Wording {
  return ROLE[code] ?? { label: code.replace(/_/g, ' '), meaning: '' };
}
export function verificationWording(code: string): Wording {
  return VERIFICATION[code] ?? { label: code, meaning: '' };
}
export function eventLabel(code: string): string {
  return EVENT[code] ?? code.replace(/_/g, ' ');
}

/**
 * Standard lookout designs recognised by the pipeline (pipeline/designs.py DESIGN_NAMES; the
 * guide's own names and facts come from designs.json). test/vocab-and-search checks the two
 * lists match.
 */
export const DESIGN_NAMES: Record<string, string> = {
  l4: 'L-4',
  r6: 'R-6',
  l5: 'L-5',
  l6: 'L-6',
  l2: 'L-2 house',
  l20: 'L-20 cab',
  r1_towers: 'Region 1 log towers T-10 to T-50',
  r1_cupola_towers: 'Region 1 towers with cupola (T-1, T-2)',
  r1_patrol_tower: 'Region 1 patrol tower (T-3)',
  d6: 'D-6',
  d1: 'D-1',
  cupola: 'Cupola house',
  r6_7x7_cab: 'Region 6 7 x 7 cab',
  r6_timber_towers: 'Region 6 timber towers (CT, TT)',
  r5_lookouts: 'California (Region 5) plan',
  plan_4a: 'Plan 4-A',
  d5: 'D-5 (4-AR)',
  c3: 'C-3',
  bc301: 'BC-301',
  bc201: 'BC-201',
  plan_81a: 'Plan 81-A',
  plan_86: 'Plan 86',
  sitpa: 'SITPA log lookout',
  r3_cab: 'Region 3 cab',
  aermotor: 'Aermotor',
  aermotor_ls40: 'Aermotor LS-40',
  aermotor_mc39: 'Aermotor MC-39',
  aermotor_ll25: 'Aermotor LL-25',
  aermotor_lx: 'Aermotor LX-24 / LX-25',
  aermotor_mc24: 'Aermotor MC-24',
  ideco: 'IDECO',
  usfs_7x7_1932: 'USFS 7 x 7 steel tower (1932)',
  l1401: 'L-1400 steel tower',
  l1600: 'L-1600 steel tower',
  cl100: 'CL-100',
  d3_log_tower: 'District 3 log tower',
  r9_mast: 'Region 9 pole mast',
  other_steel: 'Other steel maker',
  blaw_knox: 'Blaw-Knox',
  mcclintic_marshall: 'McClintic-Marshall',
  pacific_coast_steel: 'Pacific Coast Steel',
  wisconsin_standard: 'Wisconsin standard tower',
  stone_lookouts: 'Stone lookouts',
  chimney_rock: 'Chimney Rock plan',
  nps_rustic: 'National Park Service lookout',
  cdf_809r: 'CDF 809R',
  cdf_732_6a: 'CDF 732-6A',
};

/** What each design is built of (data/designs.json "material"), to group the map's design filter. */
export const DESIGN_MATERIAL: Record<string, string> = {
  l4: 'wood',
  r6: 'wood',
  l5: 'wood',
  l6: 'wood',
  l2: 'wood',
  l20: 'mixed',
  r1_towers: 'log',
  r1_cupola_towers: 'log',
  r1_patrol_tower: 'log',
  d6: 'wood',
  d1: 'log',
  cupola: 'wood',
  r6_7x7_cab: 'wood',
  r6_timber_towers: 'wood',
  r5_lookouts: 'wood',
  plan_4a: 'wood',
  d5: 'wood',
  c3: 'wood',
  bc301: 'wood',
  bc201: 'wood',
  plan_81a: 'log',
  plan_86: 'mixed',
  sitpa: 'log',
  r3_cab: 'wood',
  aermotor: 'steel',
  aermotor_ls40: 'steel',
  aermotor_mc39: 'steel',
  aermotor_ll25: 'steel',
  aermotor_lx: 'steel',
  aermotor_mc24: 'steel',
  ideco: 'steel',
  usfs_7x7_1932: 'steel',
  l1401: 'steel',
  l1600: 'steel',
  cl100: 'steel',
  d3_log_tower: 'log',
  r9_mast: 'wood',
  other_steel: 'steel',
  blaw_knox: 'steel',
  mcclintic_marshall: 'steel',
  pacific_coast_steel: 'steel',
  wisconsin_standard: 'steel',
  stone_lookouts: 'stone',
  chimney_rock: 'stone',
  nps_rustic: 'mixed',
  cdf_809r: 'mixed',
  cdf_732_6a: 'mixed',
};

/** Labels for those groups, in display order (data/designs.json "groups"). */
export const DESIGN_MATERIAL_LABEL: Record<string, string> = {
  wood: 'Wooden cabs, houses and towers',
  log: 'Log lookouts',
  steel: 'Steel towers and cabs',
  stone: 'Stone lookouts',
  concrete: 'Concrete lookouts',
  mixed: 'Mixed construction',
};

export function designName(id: string): string {
  return DESIGN_NAMES[id] ?? id;
}

/** Values offered as map filters, in display order. */
export const STATUS_ORDER = ['standing', 'gone', 'ruins', 'relocated', 'replica', 'unknown'];
/** Structure kinds offered in the "Type of structure" filter; sites with no structure have their own switch. */
export const KIND_ORDER = ['tower', 'enclosed_tower', 'platform', 'ground', 'two_story', 'three_story', 'rooftop', 'mobile', 'unknown'];
export const MATERIAL_ORDER = ['steel', 'wood', 'log', 'stone', 'concrete', 'masonry', 'mixed'];
export const VERIFICATION_ORDER = ['unverified', 'facts', 'researched', 'verified'];

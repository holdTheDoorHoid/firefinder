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

export const KIND: Record<string, Wording> = {
  tower: { label: 'Cab on a tower', meaning: 'A lookout cab (or platform) raised on a tower.' },
  enclosed_tower: { label: 'Enclosed tower', meaning: 'A tower enclosed from the ground up.' },
  platform: { label: 'Open platform tower', meaning: 'An open tower with a platform and no cab.' },
  ground: { label: 'Ground-level cab', meaning: 'A lookout cab or house built at ground level.' },
  two_story: { label: 'Two-story building', meaning: 'A two-story lookout building.' },
  three_story: { label: 'Three-story building', meaning: 'A three-story lookout building.' },
  tree: { label: 'Tree platform', meaning: 'A platform in a tree.' },
  camp: { label: 'Camp', meaning: 'A camp or tent site.' },
  unknown: { label: 'Type unknown', meaning: 'We do not know what kind of structure it was.' },
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
  l5: 'L-5',
  l6: 'L-6',
  r6: 'R-6',
  d6: 'D-6',
  d1: 'D-1',
  cupola: 'Cupola house',
  r5_lookouts: 'California (Region 5) plan',
  aermotor: 'Aermotor',
  ideco: 'IDECO',
  other_steel: 'Other steel maker',
};

export function designName(id: string): string {
  return DESIGN_NAMES[id] ?? id;
}

/** Values offered as map filters, in display order. */
export const STATUS_ORDER = ['standing', 'gone', 'ruins', 'relocated', 'replica', 'unknown'];
export const KIND_ORDER = ['tower', 'enclosed_tower', 'platform', 'ground', 'two_story', 'three_story', 'unknown'];
export const VERIFICATION_ORDER = ['unverified', 'facts', 'researched', 'verified'];

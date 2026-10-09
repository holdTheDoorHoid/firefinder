/** The shape of a tower id ("us-or-warner-mountain"). Ids are URLs and checklist keys; they never change. */
const ID_RE = /^[a-z]{2}-[a-z0-9]{1,3}-[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function isTowerId(value: unknown): value is string {
  return typeof value === 'string' && value.length <= 120 && ID_RE.test(value);
}

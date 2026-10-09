/**
 * The page at the address of a tower that was folded into another (src/lib/redirects.ts): an
 * instant redirect to the new page, with a link for browsers that do not follow it. A pure
 * function returning a complete HTML document, used by scripts/prerender.ts.
 */
import { escapeHtml } from '../lib/html.ts';
import { towerPath, towerUrl, type RenderContext } from './tower.ts';

export function renderRedirectPage(
  target: { id: string; name: string },
  ctx: Pick<RenderContext, 'base' | 'siteUrl'>,
): string {
  const to = escapeHtml(towerPath(target.id, ctx));
  const canonical = escapeHtml(towerUrl(target.id, ctx));
  const name = escapeHtml(target.name);
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>${name} has moved · Firefinder</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="${canonical}">
<meta http-equiv="refresh" content="0; url=${to}">
<link rel="icon" href="${escapeHtml(ctx.base)}favicon.svg" type="image/svg+xml">
</head>
<body style="font-family: system-ui, sans-serif; max-width: 36rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.5">
<main>
<h1>This lookout has moved</h1>
<p>Two sources listed it as separate lookouts; it is one. Its page is now <a href="${to}">${name}</a>.</p>
</main>
</body>
</html>
`;
}

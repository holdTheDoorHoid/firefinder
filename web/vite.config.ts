import { defineConfig } from 'vitest/config';
import type { Plugin } from 'vite';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import siteConfig from './site.config.json' with { type: 'json' };

const root = import.meta.dirname;

/**
 * Shared page chrome. Every HTML entry writes `<!--ff:header-->` and `<!--ff:footer-->`;
 * this plugin swaps in `src/partials/*.html`, fills `{{base}}` and marks the current nav link.
 */
function partials(): Plugin {
  const read = (name: string) => readFileSync(resolve(root, 'src/partials', name), 'utf8');
  return {
    name: 'firefinder-partials',
    transformIndexHtml: {
      order: 'pre',
      handler(html, ctx) {
        const page = ctx.path.includes('about') ? 'about' : ctx.path.includes('tower') ? 'tower' : 'map';
        let header = read('header.html');
        header = header.replace(`data-nav="${page}"`, `data-nav="${page}" aria-current="page"`);
        return html
          .replace('<!--ff:header-->', header)
          .replace('<!--ff:footer-->', read('footer.html'))
          .replaceAll('{{base}}', siteConfig.base)
          .replaceAll('{{repo}}', siteConfig.repo);
      },
    },
  };
}

export default defineConfig({
  base: siteConfig.base,
  plugins: [partials()],
  worker: { format: 'es' },
  build: {
    target: 'es2022',
    // MapLibre GL is ~1 MB minified (300 KB gzipped) and only loads on the map page.
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      input: {
        map: resolve(root, 'index.html'),
        about: resolve(root, 'about/index.html'),
        tower: resolve(root, 'tower.html'),
        notfound: resolve(root, '404.html'),
      },
    },
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
  },
});

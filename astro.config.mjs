import { defineConfig } from 'astro/config';

export default defineConfig({
  // 独自ドメインを取ったらここを書き換えてください。
  // サイトマップや絶対URLの生成に使われます。
  site: 'https://example.jp',
  build: { format: 'directory' },
});

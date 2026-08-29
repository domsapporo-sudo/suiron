import fs from 'node:fs';
import path from 'node:path';

const DATA_DIR = path.join(process.cwd(), 'data');

/** CSV を読んでオブジェクトの配列にする。ファイルが無ければ空配列。 */
export function readCsv(file) {
  const p = path.join(DATA_DIR, file);
  if (!fs.existsSync(p)) return [];
  const text = fs.readFileSync(p, 'utf8').trim();
  if (!text) return [];
  const lines = text.split(/\r?\n/).filter(Boolean);
  const keys = lines[0].split(',').map((k) => k.trim());
  return lines.slice(1).map((line) => {
    const cells = line.split(',');
    const row = {};
    keys.forEach((k, i) => (row[k] = (cells[i] ?? '').trim()));
    return row;
  });
}

/** 最新行を返す。 */
export function latest(file) {
  const rows = readCsv(file);
  return rows.length ? rows[rows.length - 1] : null;
}

/**
 * 最新値と、その1つ前との変化率（%）を返す。
 * データが1行しか無いときは変化率を null にする（0%と偽らない）。
 */
export function latestWithDelta(file, key) {
  const rows = readCsv(file);
  if (!rows.length) return null;
  const last = rows[rows.length - 1];
  const value = Number(last[key]);
  if (!Number.isFinite(value)) return null;
  let deltaPct = null;
  if (rows.length >= 2) {
    const prev = Number(rows[rows.length - 2][key]);
    if (Number.isFinite(prev) && prev !== 0) {
      deltaPct = ((value - prev) / prev) * 100;
    }
  }
  return { value, deltaPct, row: last };
}

/** 記事を新しい順に返す。 */
export function allPosts() {
  const modules = import.meta.glob('../pages/posts/*.md', { eager: true });
  return Object.values(modules)
    .map((m) => ({ ...m.frontmatter, url: m.url }))
    .filter((p) => p.title && !p.draft)
    .sort((a, b) => String(b.published).localeCompare(String(a.published)));
}

export function fmt(n, digits = 2) {
  if (n === null || n === undefined || !Number.isFinite(Number(n))) return '—';
  return Number(n).toLocaleString('ja-JP', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

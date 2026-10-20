import { readFileSync } from 'node:fs';
import path from 'node:path';

/** Read maintained regression inputs independently of the invoking working directory. */
export function readDashboardFixture<T = any>(name: string): T {
  return JSON.parse(readFileSync(path.join(__dirname, 'fixtures', name), 'utf8')) as T;
}

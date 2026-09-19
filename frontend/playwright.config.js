import {defineConfig} from '@playwright/test';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
export default defineConfig({
  testDir: './e2e', fullyParallel: true,
  use: {baseURL: 'http://127.0.0.1:18765', viewport: {width: 1280, height: 900}, trace: 'retain-on-failure'},
  webServer: {command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 18765`, cwd: root, url: 'http://127.0.0.1:18765', reuseExistingServer: false},
});

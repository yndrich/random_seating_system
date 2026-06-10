import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// 설정 파일(frontend/) 기준 경로. 백엔드는 ../backend 에서 띄운다
// (uvicorn `app.main:app` 가 import 되려면 cwd 가 backend 여야 하고,
//  venv 는 레포 루트 .venv 라 backend 기준 ../.venv/bin/python — dev-up 과 동일 규약).
const __dirname = dirname(fileURLToPath(import.meta.url));
const backendDir = resolve(__dirname, "..", "backend");

export default defineConfig({
  testDir: "./e2e",
  // 백엔드는 프로세스 1개 인메모리 세션이라 라운드 상태가 공유된다 → 직렬 실행.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  // 솔버(어닐링) preview 가 있는 흐름이라 여유를 둔다.
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],

  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    // WSL/헤드리스 크롬 안정화.
    launchOptions: { args: ["--no-sandbox"] },
  },

  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],

  // 두 서버를 함께 띄운다(이 프로젝트의 핵심 규약). 이미 떠 있으면 재사용.
  // 백엔드(8000)가 없으면 Vite 프록시가 /api 에 500 을 내므로 둘 다 필수.
  webServer: [
    {
      command: "../.venv/bin/python -m uvicorn app.main:app --port 8000",
      cwd: backendDir,
      url: "http://127.0.0.1:8000/api/health",
      timeout: 60_000,
      reuseExistingServer: true,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      timeout: 60_000,
      reuseExistingServer: true,
    },
  ],
});

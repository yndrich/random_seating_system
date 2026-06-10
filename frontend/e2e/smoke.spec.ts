import { test, expect, type Page } from "@playwright/test";

/**
 * 프론트엔드 E2E 스모크 — 실제 브라우저로 UI 를 구동해 전 흐름을 검증한다.
 *
 * 백엔드 smoke_api.py 가 HTTP 계약을 검증한다면, 이쪽은 그 위의 "동작" 을 본다:
 * 폼 입력 → addParticipant, 편성(preview=solver), 확정(commit), 이력, 롤백 까지
 * App.tsx / client.ts / 컴포넌트가 실제로 연결돼 동작하는지 DOM 으로 확인한다.
 * (npm run build 는 타입만 본다 — 이 테스트가 동작 사각지대를 닫는다.)
 *
 * 실행: cd frontend && npm run test:e2e   (두 서버는 playwright.config 가 자동 기동)
 */

// 회사 4개 × 3명 = 12명. 4조(기본)로 나누면 회사 완전 분리가 가능 → 하드 위반 0 기대.
const COMPANIES = ["Acme", "Globex", "Initech", "Umbrella"];
const GENDERS = ["male", "female", "other"] as const;
const AGES = ["20s", "30s", "40s", "50s"];
const MBTIS = ["INTJ", "ENFP", "ISTJ", "ESFP", "INFP", "ESTJ", "ENTP", "ISFJ"];

const PEOPLE = Array.from({ length: 12 }, (_, i) => ({
  name: `P${String(i + 1).padStart(2, "0")}`,
  company: COMPANIES[i % COMPANIES.length],
  gender: GENDERS[i % GENDERS.length],
  age: AGES[i % AGES.length],
  mbti: MBTIS[i % MBTIS.length],
}));

async function addParticipant(page: Page, p: (typeof PEOPLE)[number]) {
  const form = page.locator(".participant-form");
  await form.getByPlaceholder("이름").fill(p.name);
  await form.getByPlaceholder("회사/소속").fill(p.company);
  const selects = form.locator("select");
  await selects.nth(0).selectOption(p.gender); // 성별
  await selects.nth(1).selectOption(p.age); // 연령대
  await selects.nth(2).selectOption(p.mbti); // MBTI
  await form.getByRole("button", { name: "+ 추가" }).click();
}

const tab = (page: Page, name: RegExp) =>
  page.getByRole("button", { name });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  // 백엔드 인메모리 상태가 이전 실행에서 남아있을 수 있으니 세션을 새로 강제 →
  // reload 시 client.ts 가 빈 세션을 새로 만든다(깨끗한 출발점).
  await page.evaluate(() => localStorage.removeItem("seating.session_id"));
  await page.reload();
  await expect(tab(page, /참가자/)).toContainText("(0)");
});

test("참가자 추가 → 편성 → 확정 → 롤백 전체 흐름", async ({ page }) => {
  // 1) 참가자 추가 (폼 → addParticipant). 매 추가마다 테이블 행 증가로 비동기 완료 대기.
  for (let i = 0; i < PEOPLE.length; i++) {
    await addParticipant(page, PEOPLE[i]);
    await expect(page.locator(".participant-table tbody tr")).toHaveCount(i + 1);
  }
  await expect(tab(page, /참가자/)).toContainText("(12)");
  await expect(page.getByText("총 12명")).toBeVisible();

  // 2) 배정 탭 → 시드 고정(결정적) → 편성(preview = 솔버 실행)
  await tab(page, /배정/).click();
  await page.locator('.config-form input[placeholder="랜덤"]').fill("42");
  await page.getByRole("button", { name: "이번 회차 편성" }).click();

  // 미리보기 등장 + 구조 검증: 4조, 12명 전원 착석
  await expect(page.getByRole("heading", { name: "1회차 미리보기" })).toBeVisible();
  await expect(page.locator(".table-grid .table-card")).toHaveCount(4);
  await expect(page.locator(".table-grid .member-chip")).toHaveCount(12);
  // 회사 4개가 4조에 분리 가능 → 하드 위반 0
  await expect(page.locator(".result .pill").first()).toHaveText("하드 위반 0");

  // 3) 확정(commit) → 이력 탭으로 전환되고 (1) 로 집계
  await page.getByRole("button", { name: "이 결과로 확정" }).click();
  await expect(tab(page, /결과·이력/)).toContainText("(1)");
  await expect(page.getByRole("heading", { name: "1회차", exact: true })).toBeVisible();
  await expect(page.locator(".result .table-card")).toHaveCount(4);

  // 4) 롤백 → 이력 비워지고 (0)
  await page.getByRole("button", { name: "롤백" }).click();
  await expect(page.getByText("아직 확정된 라운드가 없습니다.")).toBeVisible();
  await expect(tab(page, /결과·이력/)).toContainText("(0)");
});

import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

export async function login(page: Page, secondary = false) {
  const username = secondary ? process.env.E2E_SECOND_USERNAME : process.env.E2E_USERNAME;
  const password = secondary ? process.env.E2E_SECOND_PASSWORD : process.env.E2E_PASSWORD;
  if (!username || !password)
    throw new Error(
      'Ustaw jawne konta testowe E2E_USERNAME/PASSWORD oraz E2E_SECOND_USERNAME/PASSWORD.',
    );
  await page.goto('/');
  await page.getByLabel('Nazwa użytkownika').fill(username);
  await page.getByLabel(/^Hasło/).fill(password);
  await page.getByRole('button', { name: 'Zaloguj się', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Dzień dobry. Co dziś na biurku?' }),
  ).toBeVisible();
}
export async function acknowledgeWarnings(page: Page) {
  const acknowledgment = page.getByLabel(/Zapoznałem się z aktualnymi ostrzeżeniami/);
  if (await acknowledgment.isVisible()) {
    await acknowledgment.check();
    await page
      .getByRole('textbox', { name: /^Notatka do zatwierdzenia/ })
      .fill('DANE TESTOWE: wartości sprawdzono ze źródłem; braki pozostają jawne.');
  }
}
export async function csrfHeaders(page: Page) {
  const cookies = await page.context().cookies();
  return { 'X-CSRFToken': cookies.find((cookie) => cookie.name === 'csrftoken')?.value ?? '' };
}

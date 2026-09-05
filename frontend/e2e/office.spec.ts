import { expect, test } from '@playwright/test';
import path from 'node:path';

test('logowanie → klient → dokument → lokalny odczyt → korekta → zatwierdzenie → XLSX', async ({
  page,
}) => {
  const username = process.env.E2E_USERNAME,
    password = process.env.E2E_PASSWORD;
  if (!username || !password)
    throw new Error(
      'Ustaw E2E_USERNAME i E2E_PASSWORD na jawnie utworzone konto developerskie. Test nie tworzy domyślnych haseł.',
    );
  const stamp = Date.now().toString();
  await page.goto('/');
  await page.getByLabel('Nazwa użytkownika').fill(username);
  await page.getByLabel(/^Hasło/).fill(password);
  await page.getByRole('button', { name: 'Zaloguj się', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Dzień dobry. Co dziś na biurku?' }),
  ).toBeVisible();
  await page
    .getByRole('navigation', { name: 'Główne menu' })
    .getByRole('link', { name: 'Klienci', exact: true })
    .click();
  await page.getByRole('link', { name: 'Dodaj klienta', exact: true }).click();
  await page.getByLabel('Imię', { exact: false }).fill('DANE TESTOWE');
  await page.getByLabel('Nazwisko', { exact: false }).fill(`Przegląd ${stamp}`);
  await page.getByLabel('E-mail', { exact: false }).fill(`review.${stamp}@example.invalid`);
  await page.getByRole('button', { name: 'Zapisz klienta', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: `DANE TESTOWE Przegląd ${stamp}`, exact: true }),
  ).toBeVisible();
  const clientUrl = page.url();
  await page.getByRole('link', { name: 'Dodaj dokument', exact: true }).click();
  await page
    .getByLabel('Plik dokumentu', { exact: true })
    .setInputFiles(
      path.resolve(import.meta.dirname, '../../fixtures/synthetic/application_text.pdf'),
    );
  await page.getByRole('button', { name: 'Wgraj dokument', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'application_text.pdf', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Uruchom odczyt', exact: true }).click();
  const applicationNumber = page.getByLabel('Numer wniosku', { exact: true });
  await expect(applicationNumber).toBeVisible({ timeout: 120_000 });
  await applicationNumber.fill(`DANE TESTOWE E2E ${stamp}`);
  await expect(page.getByText('Niezapisane zmiany', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Zatwierdź wersję', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Zapisz wersję roboczą', exact: true }).click();
  await expect(page.getByText('Wersja robocza została zapisana.')).toBeVisible();
  await page.getByRole('button', { name: 'Zatwierdź wersję', exact: true }).click();
  await page.getByRole('button', { name: 'Potwierdź zatwierdzenie', exact: true }).click();
  await expect(page.getByText('Rewizja 1', { exact: true })).toBeVisible();
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Eksport XLSX · rew. 1' }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
  expect(await download.failure()).toBeNull();
  await page.reload();
  await expect(applicationNumber).toHaveValue(`DANE TESTOWE E2E ${stamp}`);
  await expect(page.getByRole('button', { name: 'Zatwierdź wersję', exact: true })).toBeDisabled();
  await page.goto(clientUrl);
  await expect(page.getByRole('link', { name: /application_text.pdf/ }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Wyloguj się' }).click();
  await expect(page.getByRole('button', { name: 'Zaloguj się', exact: true })).toBeVisible();
});

test('niezapisana kartoteka wymaga świadomego opuszczenia formularza', async ({ page }) => {
  const username = process.env.E2E_USERNAME,
    password = process.env.E2E_PASSWORD;
  if (!username || !password) throw new Error('Brak konta E2E.');
  await page.goto('/');
  await page.getByLabel('Nazwa użytkownika').fill(username);
  await page.getByLabel(/^Hasło/).fill(password);
  await page.getByRole('button', { name: 'Zaloguj się', exact: true }).click();
  await page
    .getByRole('navigation', { name: 'Główne menu' })
    .getByRole('link', { name: 'Klienci', exact: true })
    .click();
  await page.getByRole('link', { name: 'Dodaj klienta', exact: true }).click();
  await page.getByLabel('Imię', { exact: false }).fill('DANE TESTOWE');
  await page
    .getByRole('navigation', { name: 'Główne menu' })
    .getByRole('link', { name: 'Polisy', exact: true })
    .click();
  await expect(page.getByRole('heading', { name: 'Masz niezapisane zmiany' })).toBeVisible();
  await page.getByRole('button', { name: 'Zostań w formularzu' }).click();
  await expect(page.getByLabel('Imię', { exact: false })).toHaveValue('DANE TESTOWE');
  await page
    .getByRole('navigation', { name: 'Główne menu' })
    .getByRole('link', { name: 'Polisy', exact: true })
    .click();
  await page.getByRole('button', { name: 'Odrzuć zmiany i wyjdź' }).click();
  await expect(page.getByRole('heading', { name: 'Polisy', exact: true })).toBeVisible();
});

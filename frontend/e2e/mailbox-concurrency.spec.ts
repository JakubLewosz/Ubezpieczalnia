import { expect, test } from '@playwright/test';
import { login } from './helpers';
import { injectFixture, prepareSource } from './mail-helpers';
import type { MailMessage } from '../src/mail-types';

test('poczta: równoczesne przejęcia, ADMIN przekazuje podczas zapisu, konflikt zachowuje notatkę', async ({
  page,
  browser,
}) => {
  await prepareSource(browser);
  await login(page);
  const mail = await injectFixture(page, 'no-client');
  expect(mail.client).toBeNull();
  const secondContext = await browser.newContext({
      baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
    }),
    adminContext = await browser.newContext({
      baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
    });
  const second = await secondContext.newPage(),
    admin = await adminContext.newPage();
  await login(second, true);
  await login(admin, 'admin');
  try {
    await page.goto(`/mailbox/${mail.id}`);
    await second.goto(`/mailbox/${mail.id}`);
    await expect(page.getByRole('button', { name: 'Zajmij się', exact: true })).toBeEnabled();
    await expect(second.getByRole('button', { name: 'Zajmij się', exact: true })).toBeEnabled();
    await Promise.all([
      page.getByRole('button', { name: 'Zajmij się', exact: true }).click(),
      second.getByRole('button', { name: 'Zajmij się', exact: true }).click(),
    ]);
    let claimed: MailMessage = mail;
    await expect
      .poll(async () => {
        claimed = (await (
          await page.request.get(`/api/messages/${mail.id}/`)
        ).json()) as MailMessage;
        return claimed.owner !== null;
      })
      .toBe(true);
    const primaryWon = claimed.owner?.username === process.env.E2E_USERNAME;
    const winner = primaryWon ? page : second,
      loser = primaryWon ? second : page;
    const targetName = primaryWon ? process.env.E2E_SECOND_USERNAME! : process.env.E2E_USERNAME!;
    await expect(winner.getByText('Przejęto obsługę wiadomości.')).toBeVisible();
    await expect(loser.getByText(/Konflikt wersji/)).toBeVisible();
    await expect(
      loser.getByText(`Odpowiedzialny: ${claimed.owner?.username}`, { exact: true }),
    ).toBeVisible();
    const note = 'DANE TESTOWE: notatka właściciela, zachowana mimo konfliktu.';
    await winner.getByRole('textbox', { name: /^Notatka obsługi/ }).fill(note);
    let release!: () => void;
    let workRequests = 0;
    await winner.route(`**/api/messages/${mail.id}/work/`, async (route) => {
      if (route.request().method() === 'POST') {
        workRequests++;
        await new Promise<void>((resolve) => {
          release = resolve;
        });
      }
      await route.continue();
    });
    await winner.getByRole('button', { name: 'Zapisz obsługę', exact: true }).click();
    await expect(winner.getByRole('textbox', { name: /^Notatka obsługi/ })).toBeDisabled();
    await admin.goto(`/mailbox/${mail.id}`);
    await admin.getByRole('button', { name: 'Przypisz / przekaż', exact: true }).click();
    const picker = admin.getByRole('dialog', { name: 'Przypisz wiadomość pracownikowi' });
    await picker
      .getByRole('textbox', { name: 'Szukaj aktywnego pracownika', exact: true })
      .fill(targetName);
    await picker.getByRole('button', { name: targetName, exact: true }).click();
    await expect(admin.getByText('Zapisano stan obsługi i historię zmiany.')).toBeVisible();
    await expect.poll(() => typeof release).toBe('function');
    release();
    await expect(winner.getByText(/Konflikt wersji/)).toBeVisible();
    await expect(winner.getByRole('textbox', { name: /^Notatka obsługi/ })).toHaveValue(note);
    await expect(
      winner.getByRole('textbox', { name: /^Kopia Twojej niezapisanej notatki/ }),
    ).toHaveValue(note);
    await winner.getByRole('textbox', { name: /^Kopia Twojej niezapisanej notatki/ }).focus();
    await expect(
      winner.getByRole('textbox', { name: /^Kopia Twojej niezapisanej notatki/ }),
    ).toBeFocused();
    await winner.getByRole('button', { name: 'Wczytaj ponownie', exact: true }).click();
    await expect(winner.getByRole('dialog', { name: 'Wczytaj aktualną wiadomość' })).toBeVisible();
    await winner.getByRole('button', { name: 'Zachowaj moje wpisy', exact: true }).click();
    expect(workRequests).toBe(1);
    await expect(loser.getByText(`Odpowiedzialny: ${targetName}`, { exact: true })).toBeVisible();
    const current = (await (
      await admin.request.get(`/api/messages/${mail.id}/`)
    ).json()) as MailMessage;
    expect(current.owner?.username).toBe(targetName);
    expect(current.note).toBe('');
    expect(current.status).toBe('in_progress');
  } finally {
    await secondContext.close();
    await adminContext.close();
  }
});

test('poczta: HTML-only jest tekstem, bez zewnętrznych żądań; wąski ekran i klawiatura', async ({
  page,
  browser,
}, testInfo) => {
  await prepareSource(browser);
  await login(page);
  const mail = await injectFixture(page, 'html-only');
  const external: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (
      ['http:', 'https:'].includes(url.protocol) &&
      !['127.0.0.1', 'localhost'].includes(url.hostname)
    )
      external.push(url.origin);
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/mailbox/${mail.id}`);
  await expect(page.getByLabel('Pełna treść wiadomości')).toBeVisible();
  await expect(
    page.locator('.message-body img,.message-body iframe,.message-body script'),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Zajmij się', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Przejęto obsługę wiadomości.')).toBeVisible();
  const chooseClient = page.getByRole('button', { name: 'Wybierz klienta', exact: true });
  await expect(chooseClient).toBeEnabled();
  await chooseClient.focus();
  await expect(chooseClient).toBeFocused();
  await page.keyboard.press('Space');
  await expect(page.getByRole('dialog', { name: 'Powiąż istniejącą kartotekę' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.getByLabel('Pełna treść wiadomości').scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath('DANE-TESTOWE-mail-mobile.png'),
    animations: 'disabled',
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/mailbox/${mail.id}`);
  await expect(page.getByLabel('Pełna treść wiadomości')).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('DANE-TESTOWE-mail-desktop.png'),
    animations: 'disabled',
  });
  expect(external).toEqual([]);
  const current = (await (
    await page.request.get(`/api/messages/${mail.id}/`)
  ).json()) as MailMessage;
  expect(current.status).toBe('in_progress');
  expect(current.client).toBeNull();
});

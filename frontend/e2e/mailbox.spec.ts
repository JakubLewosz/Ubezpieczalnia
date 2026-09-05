import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { acknowledgeWarnings, csrfHeaders, login } from './helpers';
import type { Client, DocumentRecord } from '../src/types';
import type { MailMessage } from '../src/mail-types';

import { injectFixture, prepareSource, python, source } from './mail-helpers';

test('poczta: nowe źródło → obsługa dwóch pracowników → klient z drugiej strony → załącznik → OCR/XLSX → done → nowa odpowiedź todo', async ({
  page,
  browser,
}, testInfo) => {
  testInfo.annotations.push({
    type: 'Źródło E2E',
    description:
      source === 'imap'
        ? 'lokalny Dovecot TLS, rzeczywisty worker'
        : 'jawny import offline demo; ten wariant nie potwierdza workera poczty',
  });
  await prepareSource(browser);
  await login(page);
  await page.goto('/mailbox?ordering=-received_at');
  const message = await injectFixture(page, 'application');
  expect(message.status).toBe('todo');
  expect(message.owner).toBeNull();
  expect(message.client).toBeNull();
  const row = page
    .getByRole('row')
    .filter({ has: page.locator(`a[href="/mailbox/${message.id}"]`) });
  await expect(row).toBeVisible({ timeout: 20_000 });
  await expect(row.getByText('Do obsłużenia', { exact: true })).toBeVisible();
  await row.locator(`a[href="/mailbox/${message.id}"]`).click();
  await expect(page.getByRole('button', { name: 'Zajmij się', exact: true })).toBeVisible();
  await expect
    .poll(async () => {
      const current = (await (
        await page.request.get(`/api/messages/${message.id}/`)
      ).json()) as MailMessage;
      return [current.status, current.owner, current.is_read, current.version];
    })
    .toEqual(['todo', null, true, message.version]);
  await page.getByRole('button', { name: 'Zajmij się', exact: true }).click();
  await expect(page.getByText('Przejęto obsługę wiadomości.')).toBeVisible();
  const secondContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
  });
  const second = await secondContext.newPage();
  await login(second, true);
  try {
    const unopened = (await (
      await second.request.get(`/api/messages/${message.id}/`)
    ).json()) as MailMessage;
    expect(unopened.is_read).toBe(false);
    await second.goto(`/mailbox/${message.id}`);
    await expect(
      second.getByText(`Odpowiedzialny: ${process.env.E2E_USERNAME}`, { exact: true }),
    ).toBeVisible();
    await expect(second.getByRole('textbox', { name: /^Notatka obsługi/ })).toBeDisabled();
    const stamp = Date.now().toString();
    let target: Client | undefined;
    for (let index = 1; index <= 26; index++) {
      const response = await page.request.post('/api/clients/', {
        headers: await csrfHeaders(page),
        data: {
          kind: 'person',
          first_name: 'DANE TESTOWE',
          last_name: `Poczta ${stamp} ${String(index).padStart(2, '0')}`,
          email: `mail.${stamp}.${index}@example.invalid`,
        },
      });
      expect(response.status()).toBe(201);
      if (index === 26) target = (await response.json()) as Client;
    }
    await page.getByRole('button', { name: 'Wybierz klienta', exact: true }).click();
    const picker = page.getByRole('dialog');
    await picker.getByLabel('Znajdź klienta').fill(stamp);
    await expect(picker.getByText('1–20 z 26', { exact: true })).toBeVisible();
    await picker.getByRole('button', { name: 'Następna strona', exact: true }).click();
    await picker
      .getByRole('button', { name: new RegExp(`^DANE TESTOWE Poczta ${stamp} 26`) })
      .click();
    await page
      .getByRole('textbox', { name: /^Notatka obsługi/ })
      .fill('DANE TESTOWE: sprawdzono nadawcę i wybrano klienta świadomie.');
    await page.getByRole('button', { name: 'Zapisz obsługę', exact: true }).click();
    await expect(page.getByText('Zapisano stan obsługi i historię zmiany.')).toBeVisible();
    const saved = (await (
      await page.request.get(`/api/messages/${message.id}/`)
    ).json()) as MailMessage;
    expect(saved.client).toBe(target!.id);
    expect(saved.status).toBe('in_progress');
    await page.getByRole('button', { name: 'Dodaj do dokumentów klienta', exact: true }).click();
    await page.getByRole('link', { name: 'Otwórz dokument i odczyt', exact: true }).click();
    const documentId = page.url().split('/').at(-1)!;
    const document = (await (
      await page.request.get(`/api/documents/${documentId}/`)
    ).json()) as DocumentRecord;
    expect(document.mail_source?.message).toBe(message.id);
    await page.getByRole('button', { name: 'Uruchom odczyt', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Numer wniosku', exact: true })).toBeVisible({
      timeout: 120_000,
    });
    await page.getByRole('button', { name: 'Zatwierdź wersję', exact: true }).click();
    await acknowledgeWarnings(page);
    await page.getByRole('button', { name: 'Potwierdź zatwierdzenie', exact: true }).click();
    await expect(page.getByText('Rewizja 1', { exact: true })).toBeVisible();
    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Eksport XLSX · rew. 1', exact: true }).click();
    const download = await downloadEvent;
    const output = testInfo.outputPath('DANE-TESTOWE-mail-review.xlsx');
    await download.saveAs(output);
    expect(await download.failure()).toBeNull();
    execFileSync(
      python,
      [
        '-c',
        `import sys\nfrom openpyxl import load_workbook\nw=load_workbook(sys.argv[1]); assert 'Dane' in w.sheetnames\nrows=list(w['Dane'].iter_rows(min_row=2,values_only=True))\nassert any(r[2]=='application_number' and r[4]=='TEST/2026/001' for r in rows)\nassert any(r[0]=='participants' and r[2]=='name' and r[4]=='Anna Demonstracyjna' for r in rows)\nassert not any(c.data_type=='f' for row in w['Dane'] for c in row)`,
        output,
      ],
      { stdio: 'pipe' },
    );
    await page.getByRole('link', { name: 'Wróć do obsługi wiadomości', exact: true }).click();
    await page.getByRole('combobox', { name: 'Stan obsługi', exact: true }).selectOption('done');
    await page
      .getByRole('textbox', { name: /^Notatka obsługi/ })
      .fill('DANE TESTOWE: zakończono sprawdzenie; wynik odnotowany bez wysyłki z aplikacji.');
    await page.getByRole('button', { name: 'Zapisz obsługę', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Otwórz ponownie', exact: true })).toBeVisible();
    const finished = (await (
      await page.request.get(`/api/messages/${message.id}/`)
    ).json()) as MailMessage;
    expect(finished.status).toBe('done');
    expect(finished.completed_by?.username).toBe(process.env.E2E_USERNAME);
    expect(finished.completed_at).toBeTruthy();
    await page.goto('/mailbox?ordering=-received_at');
    const reply = await injectFixture(page, 'reply');
    expect(reply.id).not.toBe(message.id);
    expect(reply.status).toBe('todo');
    expect(reply.owner).toBeNull();
    await expect(page.locator(`a[href="/mailbox/${reply.id}"]`)).toBeVisible({ timeout: 20_000 });
    expect(
      ((await (await page.request.get(`/api/messages/${message.id}/`)).json()) as MailMessage)
        .status,
    ).toBe('done');
  } finally {
    await secondContext.close();
  }
});

test('poczta: newsletter nie wymaga działania dopiero po jawnej decyzji i powodzie', async ({
  page,
  browser,
}) => {
  await prepareSource(browser);
  await login(page);
  const message = await injectFixture(page, 'newsletter');
  await page.goto(`/mailbox/${message.id}`);
  await page.getByRole('button', { name: 'Zajmij się', exact: true }).click();
  await expect(page.getByText('Przejęto obsługę wiadomości.')).toBeVisible();
  await page.getByRole('combobox', { name: 'Stan obsługi', exact: true }).selectOption('no_action');
  await expect(page.getByRole('button', { name: 'Zapisz obsługę', exact: true })).toBeDisabled();
  await page
    .getByRole('textbox', { name: /^Notatka obsługi/ })
    .fill('DANE TESTOWE: newsletter informacyjny, bez zlecenia obsługi.');
  await page.getByRole('button', { name: 'Zapisz obsługę', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Otwórz ponownie', exact: true })).toBeVisible();
  const latest = (await (
    await page.request.get(`/api/messages/${message.id}/`)
  ).json()) as MailMessage;
  expect(latest.status).toBe('no_action');
  expect(latest.note).toContain('newsletter');
  expect(latest.client).toBeNull();
});

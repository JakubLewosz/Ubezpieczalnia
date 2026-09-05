import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { acknowledgeWarnings, csrfHeaders, login } from './helpers';
import type { Client, Review } from '../src/types';

test('A: numerowany wniosek → grupy i role → ostrzeżenia → niezmienna rewizja → rzeczywisty XLSX', async ({
  page,
}, testInfo) => {
  await login(page);
  const stamp = Date.now().toString();
  const response = await page.request.post('/api/clients/', {
    headers: await csrfHeaders(page),
    data: {
      kind: 'person',
      first_name: 'DANE TESTOWE',
      last_name: `Wniosek ${stamp}`,
      email: `numbered.${stamp}@example.invalid`,
    },
  });
  expect(response.status()).toBe(201);
  const client = (await response.json()) as Client;
  await page.goto(`/clients/${client.id}/upload`);
  await page
    .getByLabel('Plik dokumentu', { exact: true })
    .setInputFiles(path.resolve(import.meta.dirname, '../../fixtures/remediation/numbered.pdf'));
  await page.getByRole('button', { name: 'Wgraj dokument', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'numbered.pdf', exact: true })).toBeVisible();
  const documentUrl = page.url();
  const documentId = documentUrl.split('/').at(-1)!;
  await page.getByRole('button', { name: 'Uruchom odczyt', exact: true }).click();
  await expect(page.getByLabel('Numer wniosku', { exact: true })).toHaveValue('TEST/2026/001', {
    timeout: 120_000,
  });
  await expect(
    page
      .locator('.repeat-group')
      .filter({ has: page.getByRole('heading', { name: 'Uczestnik 1', exact: true }) })
      .getByRole('combobox', { name: /Rola/ }),
  ).toHaveValue('policyholder,insured');
  await page.getByRole('button', { name: 'Zatwierdź wersję', exact: true }).click();
  await acknowledgeWarnings(page);
  await page.getByRole('button', { name: 'Potwierdź zatwierdzenie', exact: true }).click();
  await expect(page.getByText('Rewizja 1', { exact: true })).toBeVisible();
  const before = (await (
    await page.request.get(`/api/documents/${documentId}/review/`)
  ).json()) as Review;
  const oldRevision = (await (
    await page.request.get(`/api/revisions/${before.revisions[0]!.id}/`)
  ).json()) as unknown;
  await page.getByRole('button', { name: 'Dodaj uczestnika ręcznie' }).click();
  const participant = page
    .locator('.repeat-group')
    .filter({ has: page.getByRole('heading', { name: 'Uczestnik 2', exact: true }) });
  await participant
    .getByRole('textbox', { name: /Nazwa \/ imię i nazwisko/ })
    .fill(`DANE TESTOWE Druga osoba ${stamp}`);
  await participant.getByRole('combobox', { name: /Rola/ }).selectOption('insured');
  await page.getByRole('button', { name: 'Zapisz wersję roboczą', exact: true }).click();
  await expect(page.getByText('Wersja robocza została zapisana.')).toBeVisible();
  await page.getByRole('button', { name: 'Dodaj element ochrony ręcznie' }).click();
  const coverage = page
    .locator('.repeat-group')
    .filter({ has: page.getByRole('heading', { name: 'Element ochrony 4', exact: true }) });
  await coverage.getByRole('textbox', { name: /Żądany zakres/ }).fill('DANE TESTOWE Szyby');
  await coverage.getByRole('textbox', { name: /Suma żądanego zakresu/ }).fill('2500');
  await page.getByRole('button', { name: 'Zapisz wersję roboczą', exact: true }).click();
  await expect(page.getByText('Wersja robocza została zapisana.')).toBeVisible();
  await page.getByRole('button', { name: 'Zatwierdź wersję', exact: true }).click();
  await acknowledgeWarnings(page);
  await page.getByRole('button', { name: 'Potwierdź zatwierdzenie', exact: true }).click();
  await expect(page.getByText('Rewizja 2', { exact: true })).toBeVisible();
  expect(
    await (await page.request.get(`/api/revisions/${before.revisions[0]!.id}/`)).json(),
  ).toEqual(oldRevision);
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Eksport XLSX · rew. 2' }).click();
  const download = await downloadEvent;
  const output = testInfo.outputPath('DANE-TESTOWE-review.xlsx');
  await download.saveAs(output);
  expect(await download.failure()).toBeNull();
  const python =
    process.env.E2E_PYTHON ||
    path.resolve(
      import.meta.dirname,
      `../../backend/.venv/${process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'}`,
    );
  execFileSync(
    python,
    [
      '-c',
      `import sys\nfrom openpyxl import load_workbook\nw=load_workbook(sys.argv[1]); rows=list(w['Dane'].iter_rows(min_row=2,values_only=True))\nassert any(r[0]=='participants' and r[2]=='name' and r[4]=='Anna Demonstracyjna' for r in rows)\nassert any(r[0]=='participants' and r[2]=='name' and r[4]==sys.argv[2] for r in rows)\nassert any(r[0]=='participants' and r[2]=='role' and r[4]=='policyholder,insured' for r in rows)\nassert any(r[0]=='coverage_items' and r[2]=='insured_sum' and r[4]==10000 for r in rows)\nassert any(r[0]=='coverage_items' and r[2]=='insured_sum' and r[4]==2500 for r in rows)\nassert any(r[0]=='previous' and r[2]=='policy_number' and r[4]=='000123' for r in rows)\nassert not any(c.data_type=='f' for row in w['Dane'] for c in row)`,
      output,
      `DANE TESTOWE Druga osoba ${stamp}`,
    ],
    { stdio: 'pipe' },
  );
  await page.reload();
  await expect(participant.getByRole('textbox', { name: /Nazwa \/ imię i nazwisko/ })).toHaveValue(
    `DANE TESTOWE Druga osoba ${stamp}`,
  );
});

test('A07/A08: dwa konta, opóźniony PATCH i konflikt bez utraty notatki lub dodatkowego zapisu', async ({
  page,
  browser,
}) => {
  await login(page);
  const stamp = Date.now().toString();
  const created = await page.request.post('/api/clients/', {
    headers: await csrfHeaders(page),
    data: { kind: 'person', first_name: 'DANE TESTOWE', last_name: `Konflikt ${stamp}` },
  });
  expect(created.status()).toBe(201);
  const client = (await created.json()) as Client;
  const secondContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
  });
  const second = await secondContext.newPage();
  await login(second, true);
  try {
    await page.goto(`/clients/${client.id}/edit`);
    await second.goto(`/clients/${client.id}/edit`);
    await page
      .getByRole('textbox', { name: 'Notatka', exact: true })
      .fill('DANE TESTOWE korekta pierwszego pracownika');
    await second
      .getByRole('textbox', { name: 'Notatka', exact: true })
      .fill('DANE TESTOWE korekta drugiego pracownika');
    let release!: () => void;
    let patchCount = 0;
    await page.route(`**/api/clients/${client.id}/`, async (route) => {
      if (route.request().method() === 'PATCH') {
        patchCount++;
        await new Promise<void>((resolve) => {
          release = resolve;
        });
      }
      await route.continue();
    });
    await page.getByRole('button', { name: 'Zapisz klienta', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Notatka', exact: true })).toBeDisabled();
    await second.getByRole('button', { name: 'Zapisz klienta', exact: true }).click();
    await expect(
      second.getByRole('heading', { name: client.display_name, exact: true }),
    ).toBeVisible();
    await expect.poll(() => typeof release).toBe('function');
    release();
    await expect(page.getByText(/Konflikt wersji/)).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Notatka', exact: true })).toHaveValue(
      'DANE TESTOWE korekta pierwszego pracownika',
    );
    await page.getByRole('button', { name: 'Wczytaj ponownie', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Wczytać nowszą kartotekę?' })).toBeVisible();
    expect(patchCount).toBe(1);
    await page.getByRole('button', { name: 'Anuluj', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Notatka', exact: true })).toHaveValue(
      'DANE TESTOWE korekta pierwszego pracownika',
    );
    await page.getByRole('button', { name: 'Wczytaj ponownie', exact: true }).click();
    await page.getByRole('button', { name: 'Wczytaj aktualne dane', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Notatka', exact: true })).toHaveValue(
      'DANE TESTOWE korekta drugiego pracownika',
    );
    expect(patchCount).toBe(1);
  } finally {
    await secondContext.close();
  }
});

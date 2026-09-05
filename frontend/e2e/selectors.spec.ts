import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { csrfHeaders, login } from './helpers';
import type { Client, DocumentRecord, Policy } from '../src/types';

test('A04: dalsze strony polis i dokumentów, archiwum oraz zachowanie zaznaczeń', async ({
  page,
}) => {
  await login(page);
  const stamp = Date.now().toString();
  const headers = await csrfHeaders(page);
  const created = await page.request.post('/api/clients/', {
    headers,
    data: { kind: 'person', first_name: 'DANE TESTOWE', last_name: `Selektory ${stamp}` },
  });
  expect(created.status()).toBe(201);
  const client = (await created.json()) as Client;
  let targetPolicy: Policy | undefined;
  for (let index = 1; index <= 27; index++) {
    const response = await page.request.post('/api/policies/', {
      headers,
      data: {
        insurer: 'DANE TESTOWE',
        number: `TEST/${stamp}/${String(index).padStart(2, '0')}`,
        insurance_type: 'OC',
        start_date: '2026-09-05',
        end_date: '2027-09-04',
        premium: null,
        currency: 'PLN',
        archived: index === 27,
        participants: [
          { client: client.id, role: 'policyholder' },
          { client: client.id, role: 'insured' },
        ],
        document_ids: [],
      },
    });
    expect(response.status()).toBe(201);
    if (index === 26) targetPolicy = (await response.json()) as Policy;
  }
  await page.goto(`/clients/${client.id}/upload`);
  const policySelect = page.getByRole('combobox', { name: /^Powiązana polisa/ });
  await expect(page.getByText('1–20 z 26', { exact: true })).toBeVisible();
  await expect(
    policySelect.getByRole('option', { name: `TEST/${stamp}/26 · DANE TESTOWE`, exact: true }),
  ).toHaveCount(0);
  await expect(
    policySelect.getByRole('option', { name: `TEST/${stamp}/27 · DANE TESTOWE`, exact: true }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Następna strona', exact: true }).click();
  await policySelect.selectOption(String(targetPolicy!.id));
  await page.getByLabel('Szukaj polisy klienta', { exact: true }).fill(`${stamp}/01`);
  await expect(policySelect).toHaveValue(String(targetPolicy!.id));
  await page
    .getByLabel('Plik dokumentu', { exact: true })
    .setInputFiles(path.resolve(import.meta.dirname, '../../fixtures/remediation/numbered.pdf'));
  await page.getByRole('button', { name: 'Wgraj dokument', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'numbered.pdf', exact: true })).toBeVisible();
  const uploadedId = page.url().split('/').at(-1)!;
  const uploaded = (await (
    await page.request.get(`/api/documents/${uploadedId}/`)
  ).json()) as DocumentRecord;
  expect(uploaded.policy).toBe(targetPolicy!.id);
  const buffer = readFileSync(
    path.resolve(import.meta.dirname, '../../fixtures/remediation/numbered.pdf'),
  );
  let targetDocument: DocumentRecord | undefined;
  for (let index = 1; index <= 26; index++) {
    const response = await page.request.post('/api/documents/', {
      headers,
      multipart: {
        client: String(client.id),
        category: 'DANE TESTOWE',
        file: {
          name: `DANE TESTOWE ${stamp} plik ${String(index).padStart(2, '0')}.pdf`,
          mimeType: 'application/pdf',
          buffer,
        },
      },
    });
    expect(response.status()).toBe(201);
    if (index === 1) targetDocument = (await response.json()) as DocumentRecord;
  }
  await page.goto(`/policies/new?client=${client.id}`);
  await page.getByLabel('Numer polisy', { exact: false }).fill(`TEST/${stamp}/NOWA`);
  await page.getByLabel('Ubezpieczyciel', { exact: false }).fill('DANE TESTOWE');
  await page.getByLabel('Rodzaj ubezpieczenia', { exact: false }).fill('OC');
  await page.getByLabel('Początek ochrony', { exact: false }).fill('2026-09-05');
  await page.getByLabel('Koniec ochrony', { exact: false }).fill('2027-09-04');
  await page.getByRole('button', { name: 'Dodaj uczestnika', exact: true }).click();
  await page.getByLabel('Szukaj uczestnika polisy').fill(stamp);
  await page
    .getByRole('dialog')
    .getByRole('button', { name: new RegExp(`^DANE TESTOWE Selektory ${stamp}`) })
    .click();
  const region = page.getByRole('region', { name: 'Powiązane dokumenty' });
  await region.getByLabel('Szukaj dokumentów do polisy').fill(stamp);
  await expect(region.getByText('1–20 z 26', { exact: true })).toBeVisible();
  await region.getByRole('button', { name: 'Następna strona', exact: true }).click();
  await region.getByRole('checkbox', { name: new RegExp(`${stamp} plik 01.pdf`) }).check();
  await expect(region.getByRole('heading', { name: 'Wybrane dokumenty (1)' })).toBeVisible();
  await region.getByLabel('Szukaj dokumentów do polisy').fill('brak-kandydata-testowego');
  await expect(region.getByText('Brak wyników', { exact: true })).toBeVisible();
  await expect(
    region.getByRole('checkbox', { name: new RegExp(`${stamp} plik 01.pdf`) }),
  ).toBeChecked();
  await page.getByRole('button', { name: 'Zapisz polisę', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: `TEST/${stamp}/NOWA`, exact: true }),
  ).toBeVisible();
  const savedId = page.url().split('/').at(-1)!;
  const saved = (await (await page.request.get(`/api/policies/${savedId}/`)).json()) as Policy;
  expect(saved.document_ids).toEqual([targetDocument!.id]);
});

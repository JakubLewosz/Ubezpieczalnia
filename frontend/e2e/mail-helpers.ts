import { expect } from '@playwright/test';
import type { Browser, Page as BrowserPage } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { csrfHeaders, login } from './helpers';
import type { Mailbox, MailMessage, MailPage } from '../src/mail-types';

const root = path.resolve(import.meta.dirname, '../..');
export const python =
  process.env.E2E_PYTHON ||
  path.join(
    root,
    `backend/.venv/${process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'}`,
  );
export const source = process.env.E2E_MAIL_SOURCE;
export async function prepareSource(browser: Browser) {
  if (source !== 'imap') return;
  const context = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
  });
  const admin = await context.newPage();
  try {
    await login(admin, 'admin');
    const boxes = (await (await admin.request.get('/api/mailboxes/')).json()) as {
      results: Mailbox[];
    };
    const box = boxes.results.find((item) => item.kind === 'imap' && item.is_current);
    if (!box)
      throw new Error(
        'Brak lokalnego źródła IMAP. Uruchom dev przez scripts/local_imap.py run-dev.',
      );
    if (!box.enabled) {
      const started = await admin.request.post(`/api/mailboxes/${box.id}/control/`, {
        headers: await csrfHeaders(admin),
        data: { action: 'start', version: box.version },
      });
      expect(started.status()).toBeLessThan(300);
    }
    await expect
      .poll(
        async () => {
          const current = (await (await admin.request.get('/api/mailboxes/')).json()) as {
            results: Mailbox[];
          };
          const target = current.results.find((item) => item.id === box.id);
          return !!target?.last_success && target.boundary_uid !== null;
        },
        {
          timeout: 120_000,
          message: 'Lokalny worker musi utrwalić początkową granicę IMAP przed dodaniem fixture.',
        },
      )
      .toBe(true);
  } finally {
    await context.close();
  }
}
export async function injectFixture(page: BrowserPage, fixture: string) {
  if (source !== 'demo' && source !== 'imap')
    throw new Error(
      'Wybierz jawnie E2E_MAIL_SOURCE=demo (offline) lub imap (lokalny Dovecot z aktywnym workerem).',
    );
  const before = (await (
    await page.request.get('/api/messages/?queue=all&ordering=-received_at')
  ).json()) as MailPage;
  const known = new Set(before.results.map((item) => item.id));
  const args =
    source === 'demo'
      ? ['backend/manage.py', 'seed_mail', '--fixture', fixture]
      : ['scripts/local_imap.py', 'inject', '--fixture', `fixtures/mail/${fixture}.eml`];
  try {
    execFileSync(python, args, { cwd: root, stdio: 'pipe' });
  } catch {
    throw new Error(
      'Nie udało się dodać syntetycznej fixture. Sprawdź lokalną konfigurację źródła i bezpieczne logi; test nie kontaktuje się z Interią.',
    );
  }
  let added: MailMessage | undefined;
  await expect
    .poll(
      async () => {
        const result = (await (
          await page.request.get('/api/messages/?queue=all&ordering=-received_at')
        ).json()) as MailPage;
        const row = result.results.find(
          (item) =>
            !known.has(item.id) && item.source_kind === (source === 'demo' ? 'demo' : 'imap'),
        );
        if (row && row.fetch_state === 'ready') {
          added = (await (
            await page.request.get(`/api/messages/${row.id}/`)
          ).json()) as MailMessage;
          return true;
        }
        return false;
      },
      {
        timeout: 120_000,
        message: 'Worker powinien zaimportować nową wiadomość ze źródła testowego.',
      },
    )
    .toBe(true);
  return added!;
}

import { useState } from 'react';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, post } from '../src/api';
import { MessageWorkspace, MailboxPage, MailboxSources } from '../src/mailbox';
import type { Mailbox, MailMessage } from '../src/mail-types';

const session = vi.hoisted(() => ({ role: 'EMPLOYEE' }));

vi.mock('../src/api', async (original) => ({
  ...(await original<object>()),
  api: vi.fn(),
  post: vi.fn(),
}));
vi.mock('../src/auth', async (original) => ({
  ...(await original<object>()),
  useAuth: () => ({ user: { id: 1, username: 'DANE TESTOWE jeden', role: session.role } }),
}));
const initial: MailMessage = {
  id: 1,
  subject: 'DANE TESTOWE wniosek',
  sender_name: 'DANE TESTOWE',
  sender_address: 'test@example.invalid',
  received_at: '2026-09-05T12:00:00Z',
  declared_at: null,
  imported_at: '2026-09-05T12:01:00Z',
  status: 'todo',
  owner: null,
  claimed_at: null,
  completed_by: null,
  completed_at: null,
  client: null,
  client_name: '',
  policy: null,
  version: 1,
  is_read: false,
  attachment_count: 0,
  fetch_state: 'ready',
  fetch_error: '',
  mailbox: 1,
  source_kind: 'demo',
  body_text: 'DANE TESTOWE\n<img src="https://tracking.example.invalid/pixel" onerror="alert(1)">',
  note: '',
  headers: [],
  warnings: [],
  attachments: [],
  history: [],
  client_candidates: [],
  related_messages: [],
};
const owned: MailMessage = {
  ...initial,
  status: 'in_progress',
  owner: { id: 1, username: 'DANE TESTOWE jeden', is_active: true },
};
function show(message: MailMessage) {
  let replace!: (message: MailMessage) => void;
  function Host() {
    const [current, setCurrent] = useState(message);
    replace = setCurrent;
    return <MessageWorkspace message={current} refresh={vi.fn()} networkError="" />;
  }
  render(<RouterProvider router={createMemoryRouter([{ path: '*', element: <Host /> }])} />);
  return (value: MailMessage) => act(async () => replace(value));
}
beforeEach(() => {
  session.role = 'EMPLOYEE';
  vi.mocked(api).mockReset();
  vi.mocked(api).mockResolvedValue({ count: 0, results: [], next: null, previous: null });
  vi.mocked(post).mockReset();
  vi.mocked(post).mockResolvedValue({ is_read: true });
});
describe('Wspólna skrzynka i niezależny stan pracy', () => {
  it('otwarcie wywołuje tylko osobisty read; polling nie powtarza go ani nie przejmuje wiadomości', async () => {
    const replace = show(initial);
    expect(post).toHaveBeenCalledWith('/api/messages/1/read/');
    expect(screen.getByRole('button', { name: 'Zajmij się' })).toBeEnabled();
    expect(screen.getByRole('textbox', { name: /^Notatka obsługi/ })).toBeDisabled();
    await replace({ ...initial, is_read: true });
    expect(post).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Do obsłużenia', { selector: '.badge' })).toBeVisible();
  });
  it('wyświetla HTML jako tekst bez obrazu i wykonywania kodu', () => {
    show(initial);
    expect(screen.getByLabelText('Pełna treść wiadomości')).toHaveTextContent(
      '<img src="https://tracking.example.invalid/pixel" onerror="alert(1)">',
    );
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(document.querySelector('img[src*="tracking.example.invalid"]')).toBeNull();
  });
  it('opóźniony zapis blokuje notatkę, a konflikt zachowuje wpis i nie wywołuje dodatkowego POST', async () => {
    let reject!: (error: Error) => void;
    vi.mocked(post).mockImplementation((path) =>
      String(path).endsWith('/read/')
        ? Promise.resolve({ is_read: true })
        : new Promise((_, fail) => {
            reject = fail;
          }),
    );
    const replace = show(owned);
    const note = screen.getByRole('textbox', { name: /^Notatka obsługi/ });
    await userEvent.type(note, 'DANE TESTOWE moja robocza notatka');
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz obsługę' }));
    expect(note).toBeDisabled();
    await replace({ ...owned, version: 2, note: 'DANE TESTOWE inna notatka' });
    expect(note).toHaveValue('DANE TESTOWE moja robocza notatka');
    await act(async () => reject(new ApiError(409, 'Nowsza wersja wiadomości.')));
    expect(note).toHaveValue('DANE TESTOWE moja robocza notatka');
    await userEvent.click(screen.getByRole('button', { name: 'Wczytaj ponownie' }));
    expect(
      vi.mocked(post).mock.calls.filter(([path]) => String(path).endsWith('/work/')),
    ).toHaveLength(1);
    await userEvent.click(screen.getByRole('button', { name: 'Zachowaj moje wpisy' }));
    expect(note).toHaveValue('DANE TESTOWE moja robocza notatka');
  });
  it('przekazanie własności w pollingu blokuje edycję bez kasowania wpisanej notatki', async () => {
    const replace = show(owned);
    const note = screen.getByRole('textbox', { name: /^Notatka obsługi/ });
    await userEvent.type(note, 'DANE TESTOWE notatka sprzed przekazania');
    await replace({
      ...owned,
      version: 2,
      owner: { id: 2, username: 'DANE TESTOWE dwa', is_active: true },
    });
    expect(note).toBeDisabled();
    expect(note).toHaveValue('DANE TESTOWE notatka sprzed przekazania');
    expect(screen.getByText(/Inny pracownik zapisał nowszą wersję/)).toBeVisible();
    const copy = screen.getByRole('textbox', { name: /^Kopia Twojej niezapisanej notatki/ });
    expect(copy).toHaveValue('DANE TESTOWE notatka sprzed przekazania');
    expect(copy).toHaveAttribute('readonly');
    expect(copy).toBeEnabled();
    await userEvent.click(copy);
    expect(copy).toHaveFocus();
  });
  it('odmowa zapisu po wygaśnięciu sesji zostawia roboczą notatkę', async () => {
    show(owned);
    vi.mocked(post).mockRejectedValueOnce(new ApiError(403, 'Sesja wygasła.'));
    const note = screen.getByRole('textbox', { name: /^Notatka obsługi/ });
    await userEvent.type(note, 'DANE TESTOWE tekst do zachowania');
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz obsługę' }));
    expect(await screen.findByText('Sesja wygasła.')).toBeVisible();
    expect(note).toHaveValue('DANE TESTOWE tekst do zachowania');
    expect(note).toBeEnabled();
  });
  it('Oczekujemy wymaga notatki, a zapis ma konkretną wersję i nie zawiera akcji wysyłki', async () => {
    show(owned);
    vi.mocked(post).mockResolvedValueOnce({
      ...owned,
      version: 2,
      status: 'waiting',
      note: 'DANE TESTOWE czekamy na dane',
    });
    await userEvent.selectOptions(screen.getByLabelText('Stan obsługi'), 'waiting');
    expect(screen.getByRole('button', { name: 'Zapisz obsługę' })).toBeDisabled();
    await userEvent.type(
      screen.getByRole('textbox', { name: /^Notatka obsługi/ }),
      'DANE TESTOWE czekamy na dane',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz obsługę' }));
    expect(post).toHaveBeenCalledWith('/api/messages/1/work/', {
      version: 1,
      action: 'update',
      status: 'waiting',
      note: 'DANE TESTOWE czekamy na dane',
      client: null,
      policy: null,
    });
    expect(
      screen.queryByRole('button', { name: /Wyślij|Odpowiedz|Przekaż dalej/ }),
    ).not.toBeInTheDocument();
  });
  it('liczniki listy pochodzą z całego zbioru API', async () => {
    vi.mocked(api).mockImplementation(async (path) =>
      String(path).startsWith('/api/mailboxes/')
        ? { results: [] }
        : {
            count: 29,
            next: 'next',
            previous: null,
            results: [initial],
            counts: { total: 29, todo: 20, in_progress: 5, waiting: 4, done: 0, no_action: 0 },
          },
    );
    render(
      <RouterProvider router={createMemoryRouter([{ path: '*', element: <MailboxPage /> }])} />,
    );
    expect(await screen.findByText('Cały filtrowany zbiór: 29')).toBeVisible();
    expect(screen.getByText('Do obsłużenia: 20')).toBeVisible();
  });
});

describe('Operacje administratora na źródle poczty', () => {
  const mailbox: Mailbox = {
    id: 1,
    is_current: true,
    kind: 'imap',
    folder: 'INBOX',
    enabled: false,
    state: 'paused',
    error_message: '',
    last_success: null,
    last_attempt: null,
    boundary_uid: null,
    uidvalidity: null,
    pending_count: 0,
    error_count: 0,
    version: 7,
  };
  function sources(boxes = [mailbox]) {
    session.role = 'ADMIN';
    vi.mocked(api).mockResolvedValue({ results: boxes });
    render(
      <RouterProvider router={createMemoryRouter([{ path: '*', element: <MailboxSources /> }])} />,
    );
  }
  it('nie przedstawia HTTP 200 z nieudanym testem połączenia jako sukcesu i nie aktywuje importu', async () => {
    sources();
    vi.mocked(post).mockResolvedValue({
      ok: false,
      error_message: 'DANE TESTOWE certyfikat odrzucony.',
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Test połączenia' }));
    expect(await screen.findByText('DANE TESTOWE certyfikat odrzucony.')).toBeVisible();
    expect(screen.queryByText(/Zakończono test połączenia/)).not.toBeInTheDocument();
    expect(post).toHaveBeenCalledExactlyOnceWith('/api/mailboxes/1/control/', {
      action: 'test',
      version: 7,
    });
    expect(screen.getByRole('button', { name: 'Rozpocznij import' })).toBeEnabled();
  });
  it('historyczne źródło jest zwinięte i nie ma własnych przycisków sterujących', async () => {
    sources([mailbox, { ...mailbox, id: 2, is_current: false }]);
    expect(await screen.findByText(/Wcześniejsze źródła/)).toBeVisible();
    expect(screen.getAllByRole('button', { name: 'Test połączenia' })).toHaveLength(1);
    expect(document.querySelector('details')).not.toHaveAttribute('open');
  });
});

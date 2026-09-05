import { act, renderHook, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, patch, ApiError } from '../src/api';
import { useApi } from '../src/hooks';
import { ClientForm } from '../src/clients';
import { PolicyForm } from '../src/policies';
import type { Client, Policy } from '../src/types';
vi.mock('../src/api', async (original) => ({
  ...(await original<object>()),
  api: vi.fn(),
  patch: vi.fn(),
}));
const client: Client = {
  id: 1,
  kind: 'person',
  first_name: 'DANE TESTOWE',
  last_name: 'Osoba',
  organization_name: '',
  display_name: 'DANE TESTOWE Osoba',
  pesel: '',
  nip: '',
  email: 'dane@example.invalid',
  phone: '',
  address: '',
  note: '',
  archived: false,
  version: 1,
  created_at: '2026-09-05T12:00:00Z',
  duplicate_warnings: [],
};
const policy: Policy = {
  id: 1,
  number: 'TEST/1',
  insurer: 'DANE TESTOWE',
  insurance_type: 'OC',
  start_date: '2026-09-05',
  end_date: '2027-09-04',
  premium: null,
  currency: 'PLN',
  subject: '',
  archived: false,
  version: 1,
  participants: [
    { client: 1, client_name: client.display_name, role: 'insured' },
    { client: 1, client_name: client.display_name, role: 'policyholder' },
  ],
  document_ids: [],
  coverage_status: 'active',
  duplicate_warnings: [],
};
beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.mocked(api).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});
describe('Izolacja odpowiedzi rekordów', () => {
  it('ignoruje opóźnioną odpowiedź poprzedniego rekordu nawet gdy transport zignorował abort', async () => {
    let first!: (v: { id: number }) => void;
    let second!: (v: { id: number }) => void;
    vi.mocked(api)
      .mockImplementationOnce(
        () =>
          new Promise((done) => {
            first = done;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((done) => {
            second = done;
          }),
      );
    const { result, rerender } = renderHook(({ path }) => useApi<{ id: number }>(path), {
      initialProps: { path: '/api/clients/1/' },
    });
    rerender({ path: '/api/clients/2/' });
    expect(result.current.data).toBeNull();
    await act(async () => second({ id: 2 }));
    await act(async () => first({ id: 1 }));
    expect(result.current.data).toEqual({ id: 2 });
  });
  it('nowy formularz nie otrzymuje danych starego rekordu po zmianie path na null', async () => {
    vi.mocked(api).mockResolvedValueOnce({ id: 1 });
    const { result, rerender } = renderHook(
      ({ path }: { path: string | null }) => useApi<{ id: number }>(path),
      { initialProps: { path: '/api/clients/1/' as string | null } },
    );
    await act(async () => {});
    expect(result.current.data).toEqual({ id: 1 });
    rerender({ path: null });
    expect(result.current.data).toBeNull();
  });
});
describe('Zapis klienta i polisy', () => {
  it.each(['klient', 'polisa'] as const)(
    '%s blokuje pola podczas opóźnionego PATCH i zachowuje treść po konflikcie',
    async (kind) => {
      let reject!: (e: Error) => void;
      vi.mocked(patch).mockImplementationOnce(
        () =>
          new Promise((_, fail) => {
            reject = fail;
          }),
      );
      const element =
        kind === 'klient' ? (
          <ClientForm initial={client} reload={vi.fn()} />
        ) : (
          <PolicyForm initial={policy} initialClient={null} reload={vi.fn()} />
        );
      render(<RouterProvider router={createMemoryRouter([{ path: '*', element }])} />);
      const input = screen.getByLabelText(
        kind === 'klient' ? 'Notatka' : 'Opis przedmiotu ubezpieczenia',
      );
      await userEvent.type(input, 'DANE TESTOWE korekta');
      await userEvent.click(
        screen.getByRole('button', {
          name: kind === 'klient' ? 'Zapisz klienta' : 'Zapisz polisę',
        }),
      );
      expect(input).toBeDisabled();
      await userEvent.type(input, ' utracona');
      expect(input).toHaveValue('DANE TESTOWE korekta');
      await act(async () => reject(new ApiError(409, 'Drugi pracownik zapisał zmiany.')));
      expect(input).toBeEnabled();
      expect(input).toHaveValue('DANE TESTOWE korekta');
      expect(screen.getByText(/Konflikt wersji/)).toBeVisible();
    },
  );
  it('wygaśnięcie sesji pozostawia notatkę oraz czytelny komunikat', async () => {
    vi.mocked(patch).mockRejectedValueOnce(new ApiError(403, 'Sesja wymaga logowania.'));
    render(
      <RouterProvider
        router={createMemoryRouter([
          { path: '*', element: <ClientForm initial={client} reload={vi.fn()} /> },
        ])}
      />,
    );
    await userEvent.type(screen.getByLabelText('Notatka'), 'DANE TESTOWE przed wygaśnięciem');
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz klienta' }));
    expect(screen.getByLabelText('Notatka')).toHaveValue('DANE TESTOWE przed wygaśnięciem');
    expect(screen.getByText(/Sesja wygasła lub nie masz uprawnień/)).toBeVisible();
  });
});

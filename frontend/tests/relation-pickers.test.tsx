import { useState } from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/api';
import { ClientPicker } from '../src/clients';
import { PolicyDocuments, PolicyPicker } from '../src/policies';
import type { Policy } from '../src/types';
vi.mock('../src/api', async (original) => ({ ...(await original<object>()), api: vi.fn() }));
beforeEach(() => vi.mocked(api).mockReset());
describe('Selektory relacji', () => {
  it('wykluczenia klientów trafiają do serwera, dalsza strona pozostaje dostępna', async () => {
    vi.mocked(api).mockImplementation(async (path) => {
      const page = new URL(String(path), 'http://localhost').searchParams.get('page');
      return {
        count: 26,
        next: page === '1' ? 'next' : null,
        previous: page === '2' ? 'previous' : null,
        results: [
          {
            id: page === '1' ? 21 : 46,
            display_name: `DANE TESTOWE klient ${page}`,
            email: 'test@example.invalid',
            phone: '',
          },
        ],
      };
    });
    const select = vi.fn();
    render(
      <ClientPicker onSelect={select} exclude={Array.from({ length: 20 }, (_, i) => i + 1)} />,
    );
    await screen.findByText('DANE TESTOWE klient 1');
    expect(String(vi.mocked(api).mock.calls[0]?.[0])).toContain('exclude=1%2C2%2C3');
    await userEvent.click(screen.getByRole('button', { name: 'Następna strona' }));
    await userEvent.click(await screen.findByRole('button', { name: /DANE TESTOWE klient 2/ }));
    expect(select).toHaveBeenCalledWith(expect.objectContaining({ id: 46 }));
  });
  it('polisa wybrana z drugiej strony pozostaje wybrana po zmianie wyszukiwania', async () => {
    vi.mocked(api).mockImplementation(async (path) => {
      const query = new URL(String(path), 'http://localhost').searchParams;
      const second = query.get('page') === '2';
      return {
        count: 26,
        next: second ? null : 'next',
        previous: second ? 'previous' : null,
        results: query.get('search')
          ? [{ id: 3, number: 'TEST/INNA', insurer: 'DANE TESTOWE' }]
          : [
              {
                id: second ? 26 : 1,
                number: second ? 'TEST/26' : 'TEST/1',
                insurer: 'DANE TESTOWE',
              },
            ],
      };
    });
    function Host() {
      const [selected, setSelected] = useState<Policy | null>(null);
      return <PolicyPicker clientId={9} selected={selected} onSelect={setSelected} />;
    }
    render(<Host />);
    await screen.findByRole('option', { name: 'TEST/1 · DANE TESTOWE' });
    await userEvent.click(screen.getByRole('button', { name: 'Następna strona' }));
    await screen.findByRole('option', { name: 'TEST/26 · DANE TESTOWE' });
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /^Powiązana polisa/ }),
      '26',
    );
    await userEvent.type(screen.getByLabelText('Szukaj polisy klienta'), 'INNA');
    await screen.findByRole('option', { name: 'TEST/INNA · DANE TESTOWE' });
    expect(screen.getByRole('combobox', { name: /^Powiązana polisa/ })).toHaveValue('26');
    expect(String(vi.mocked(api).mock.calls[0]?.[0])).toContain('client=9&archived=false');
  });
  it('wybrane dokumenty nie znikają po zmianie strony lub uczestnika', async () => {
    vi.mocked(api).mockImplementation(async (path) => {
      const query = new URL(String(path), 'http://localhost').searchParams;
      const selected = query.has('ids');
      const page = query.get('page');
      return {
        count: selected ? 1 : 26,
        next: page === '1' ? 'next' : null,
        previous: page === '2' ? 'previous' : null,
        results: [
          {
            id: selected ? 26 : page === '2' ? 26 : 1,
            original_name:
              selected || page === '2'
                ? 'DANE TESTOWE dokument 26.pdf'
                : 'DANE TESTOWE dokument 1.pdf',
            client: 9,
            client_name: 'DANE TESTOWE klient',
          },
        ],
      };
    });
    function Host() {
      const [selected, setSelected] = useState<number[]>([]);
      const [participants, setParticipants] = useState([9]);
      return (
        <>
          <button onClick={() => setParticipants([10])}>Zmień uczestnika testowo</button>
          <PolicyDocuments
            participants={participants}
            participantsChanged={participants[0] === 10}
            selected={selected}
            onChange={setSelected}
          />
        </>
      );
    }
    render(<Host />);
    await screen.findByText('DANE TESTOWE dokument 1.pdf');
    await userEvent.click(screen.getByRole('button', { name: 'Następna strona' }));
    await userEvent.click(await screen.findByRole('checkbox', { name: /dokument 26.pdf/ }));
    await screen.findByRole('heading', { name: 'Wybrane dokumenty (1)' });
    await userEvent.click(screen.getByRole('button', { name: 'Zmień uczestnika testowo' }));
    await waitFor(() =>
      expect(screen.getByText(/Konflikt: klient nie jest uczestnikiem/)).toBeVisible(),
    );
    const selectedRegion = screen.getByRole('heading', {
      name: 'Wybrane dokumenty (1)',
    }).parentElement!;
    expect(within(selectedRegion).getByRole('checkbox', { name: /dokument 26.pdf/ })).toBeChecked();
  });
});

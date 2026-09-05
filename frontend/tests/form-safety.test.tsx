import { useState } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ReviewWorkspace } from '../src/documents';
import { ApiError, patch, post } from '../src/api';
import { ErrorNotice } from '../src/ui';
import type { DocumentRecord, Draft, Field, Review } from '../src/types';

vi.mock('../src/api', async (original) => ({
  ...(await original<object>()),
  api: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}));
const field: Field = {
  code: 'number',
  label: 'Numer wniosku',
  value: 'TEST/1',
  type: 'text',
  unit: '',
  group: 'application',
  index: 0,
  page: 1,
  source: 'Numer TEST/1',
  method: 'text',
  warnings: [],
  manual: false,
  absent: false,
};
const draft: Draft = {
  id: 1,
  version: 1,
  fields: [field],
  updated_at: '2026-09-05T12:00:00Z',
  approved_version: null,
};
const document: DocumentRecord = {
  id: 1,
  client: 1,
  client_name: 'DANE TESTOWE',
  policy: null,
  original_name: 'DANE TESTOWE.pdf',
  mime_type: 'application/pdf',
  size: 100,
  checksum: 'test',
  category: 'Wniosek',
  page_count: 1,
  created_at: '2026-09-05T12:00:00Z',
  author_name: 'DANE TESTOWE',
  duplicate_warnings: [],
  latest_job: null,
  review_status: 'draft',
};
const review: Review = {
  job: null,
  engine_result: {
    id: 1,
    profile: 'motor',
    fields: [field],
    warnings: [],
    pages: [{ number: 1, method: 'text' }],
  },
  draft,
  revisions: [],
};
function showReview() {
  render(
    <RouterProvider
      router={createMemoryRouter([
        {
          path: '*',
          element: (
            <ReviewWorkspace
              document={document}
              review={review}
              refresh={vi.fn()}
              networkError=""
            />
          ),
        },
      ])}
    />,
  );
}
describe('Bezpieczeństwo formularza', () => {
  it('wczytanie po konflikcie nie przesyła formularza', async () => {
    const submit = vi.fn((event: React.FormEvent) => event.preventDefault());
    const reload = vi.fn();
    render(
      <form onSubmit={submit}>
        <ErrorNotice error={new ApiError(409, 'Nowsza wersja')} onReload={reload} />
      </form>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Wczytaj ponownie' }));
    expect(reload).toHaveBeenCalledOnce();
    expect(submit).not.toHaveBeenCalled();
  });
  it('blokuje zmianę odczytu podczas opóźnionego PATCH', async () => {
    let resolve!: (value: Draft) => void;
    vi.mocked(patch).mockImplementationOnce(
      () =>
        new Promise<Draft>((done) => {
          resolve = done;
        }),
    );
    showReview();
    await userEvent.clear(screen.getByLabelText('Numer wniosku'));
    await userEvent.type(screen.getByLabelText('Numer wniosku'), 'TEST/2');
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz wersję roboczą' }));
    try {
      expect(screen.getByLabelText('Numer wniosku')).toBeDisabled();
    } finally {
      await act(async () =>
        resolve({ ...draft, version: 2, fields: [{ ...field, value: 'TEST/2', manual: true }] }),
      );
    }
    expect(screen.getByLabelText('Numer wniosku')).toHaveValue('TEST/2');
    expect(screen.getByLabelText('Numer wniosku')).toBeEnabled();
  });
  it('konflikt PATCH zachowuje wpisaną korektę', async () => {
    vi.mocked(patch).mockRejectedValueOnce(new ApiError(409, 'Wersja została zmieniona.'));
    showReview();
    await userEvent.clear(screen.getByLabelText('Numer wniosku'));
    await userEvent.type(screen.getByLabelText('Numer wniosku'), 'TEST/KOREKTA');
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz wersję roboczą' }));
    await waitFor(() => expect(screen.getByText(/Konflikt wersji/)).toBeVisible());
    expect(screen.getByLabelText('Numer wniosku')).toHaveValue('TEST/KOREKTA');
    expect(screen.getByText('Niezapisane zmiany')).toBeVisible();
  });
});

describe('Odpowiedzi i nawigacja', () => {
  it('polling nie nadpisuje niezapisanej korekty', async () => {
    let changeReview!: (value: Review) => void;
    function Host() {
      const [current, setCurrent] = useState(review);
      changeReview = setCurrent;
      return (
        <ReviewWorkspace document={document} review={current} refresh={vi.fn()} networkError="" />
      );
    }
    render(<RouterProvider router={createMemoryRouter([{ path: '*', element: <Host /> }])} />);
    await userEvent.clear(screen.getByLabelText('Numer wniosku'));
    await userEvent.type(screen.getByLabelText('Numer wniosku'), 'TEST/LOKALNY');
    await act(async () =>
      changeReview({
        ...review,
        draft: { ...draft, version: 2, fields: [{ ...field, value: 'TEST/INNY PRACOWNIK' }] },
      }),
    );
    expect(screen.getByLabelText('Numer wniosku')).toHaveValue('TEST/LOKALNY');
    expect(screen.getByText('Niezapisane zmiany')).toBeVisible();
  });
  it('ostrzeżenia wymagają potwierdzenia i notatki do konkretnej wersji', async () => {
    const warnings = [
      {
        id: 'date-order',
        field: 'coverage:end_date',
        code: 'date_order',
        message: 'Koniec ochrony poprzedza początek ochrony.',
        requires_note: true,
      },
    ];
    const current = { ...review, draft: { ...draft, warnings, warning_digest: 'digest-v1' } };
    render(
      <RouterProvider
        router={createMemoryRouter([
          {
            path: '*',
            element: (
              <ReviewWorkspace
                document={document}
                review={current}
                refresh={vi.fn()}
                networkError=""
              />
            ),
          },
        ])}
      />,
    );
    vi.mocked(post).mockResolvedValueOnce({
      id: 4,
      number: 1,
      created_at: '2026-09-05T12:00:00Z',
      author_name: 'DANE TESTOWE',
    });
    await userEvent.click(screen.getByRole('button', { name: 'Zatwierdź wersję' }));
    const confirm = screen.getByRole('button', { name: 'Potwierdź zatwierdzenie' });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByLabelText(/Zapoznałem się z aktualnymi/));
    expect(confirm).toBeDisabled();
    await userEvent.type(
      screen.getByRole('textbox', { name: /^Notatka do zatwierdzenia/ }),
      'DANE TESTOWE: wierny zapis źródła',
    );
    await userEvent.click(confirm);
    expect(post).toHaveBeenCalledWith('/api/documents/1/approve/', {
      version: 1,
      warning_digest: 'digest-v1',
      confirm_warnings: true,
      note: 'DANE TESTOWE: wierny zapis źródła',
    });
  });
});

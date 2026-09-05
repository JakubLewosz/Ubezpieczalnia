import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, money, date } from '../src/api';

afterEach(() => vi.unstubAllGlobals());
describe('Komunikacja z API', () => {
  it('używa sesji i tokena CSRF przy mutacji', async () => {
    document.cookie = 'csrftoken=test-csrf-token; path=/';
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', request);
    await api('/api/clients/', {
      method: 'POST',
      body: JSON.stringify({ first_name: 'DANE TESTOWE' }),
    });
    expect(request).toHaveBeenCalledOnce();
    const options = request.mock.calls[0]?.[1] as RequestInit;
    expect(options.credentials).toBe('same-origin');
    expect(new Headers(options.headers).get('X-CSRFToken')).toBe('test-csrf-token');
  });
  it('pozostawia konflikt wersji jako rozpoznawalny błąd', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Nowsza wersja jest już zapisana.' }), {
          status: 409,
        }),
      ),
    );
    await expect(api('/api/clients/1/', { method: 'PATCH', body: '{}' })).rejects.toMatchObject({
      status: 409,
      message: 'Nowsza wersja jest już zapisana.',
    });
  });
  it('wyjaśnia brak połączenia bez pozornego sukcesu', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network error')));
    await expect(api('/api/clients/')).rejects.toBeInstanceOf(ApiError);
  });
  it('nie zamienia nieznanej składki na zero i formatuje datę kalendarzową po polsku', () => {
    expect(money(null, 'PLN')).toBe('Nie podano');
    expect(money('0.00', 'PLN')).toContain('0,00');
    expect(date('2026-09-05')).toBe('5.09.2026');
  });
});

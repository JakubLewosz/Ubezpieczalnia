export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
const fieldNames: Record<string, string> = {
  first_name: 'Imię',
  last_name: 'Nazwisko',
  organization_name: 'Nazwa organizacji',
  pesel: 'PESEL',
  nip: 'NIP',
  email: 'E-mail',
  phone: 'Telefon',
  end_date: 'Koniec ochrony',
  start_date: 'Początek ochrony',
  premium: 'Składka',
  number: 'Numer polisy',
  insurer: 'Ubezpieczyciel',
  file: 'Plik',
  version: 'Wersja',
  participants: 'Uczestnicy',
  detail: '',
  non_field_errors: '',
};
function describeError(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(describeError).join(' ');
  if (value && typeof value === 'object')
    return Object.entries(value)
      .map(
        ([key, item]) =>
          `${fieldNames[key] ?? key}${(fieldNames[key] ?? key) ? ': ' : ''}${describeError(item)}`,
      )
      .join(' ');
  return 'Nie udało się wykonać operacji.';
}
export function csrfToken(): string {
  return (
    document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='))
      ?.split('=')
      .slice(1)
      .join('=') ?? ''
  );
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method))
    headers.set('X-CSRFToken', decodeURIComponent(csrfToken()));
  let response: Response;
  try {
    response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(
      0,
      'Brak połączenia z serwerem. Sprawdź, czy usługi są uruchomione, i spróbuj ponownie.',
    );
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body ? describeError(body) : `Serwer zwrócił błąd ${response.status}. Spróbuj ponownie.`,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: 'POST', body: JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'Nie udało się wykonać operacji.';
export const date = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat('pl-PL').format(
        new Date(value.length === 10 ? `${value}T12:00:00` : value),
      )
    : '—';
export const dateTime = (value: string) =>
  new Intl.DateTimeFormat('pl-PL', { dateStyle: 'short', timeStyle: 'short' }).format(
    new Date(value),
  );
export const money = (value: string | null, currency: string) =>
  value === null || value === ''
    ? 'Nie podano'
    : new Intl.NumberFormat('pl-PL', { style: 'currency', currency }).format(Number(value));
export function params(values: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value));
  });
  return query.toString();
}

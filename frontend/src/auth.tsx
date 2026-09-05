import { createContext, useContext, useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react';
import { api, errorMessage, post } from './api';
import type { User } from './types';
import { Alert, Button, FieldLabel, Loading } from './ui';

const AuthContext = createContext<{ user: User; logout: () => Promise<void> } | null>(null);
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('Brak kontekstu sesji.');
  return context;
}
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api<User>('/api/auth/me/')
      .then((value) => {
        if (active) setUser(value);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function logout() {
    await post('/api/auth/logout/');
    setUser(null);
  }
  if (loading) return <Loading label="Sprawdzanie sesji…" />;
  if (!user) return <Login onLogin={setUser} error={error} onError={setError} />;
  return <AuthContext value={{ user, logout }}>{children}</AuthContext>;
}
function Login({
  onLogin,
  error,
  onError,
}: {
  onLogin: (user: User) => void;
  error: string;
  onError: (error: string) => void;
}) {
  const [username, setUsername] = useState(''),
    [password, setPassword] = useState(''),
    [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    onError('');
    try {
      await api('/api/auth/csrf/');
      await post('/api/auth/login/', { username, password });
      onLogin(await api<User>('/api/auth/me/'));
    } catch (failure) {
      onError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-intro">
        <div className="brand">
          <span className="brand-symbol">
            <ShieldCheck size={23} />
          </span>
          <span>
            broker<span className="brand-light">office</span>
          </span>
        </div>
        <div>
          <span className="eyebrow">PRZESTRZEŃ TWOJEJ KANCELARII</span>
          <h1>
            Klienci, dokumenty
            <br />i polisy.
          </h1>
          <p>
            Lokalne środowisko demonstracyjne kancelarii.
            <br />
            Sprawdź odczyt i zatwierdź wersję dokumentu.
          </p>
        </div>
        <div className="demo-note">
          <span className="status-dot" />
          Środowisko demonstracyjne · DANE TESTOWE
        </div>
      </div>
      <main className="login-main">
        <form onSubmit={submit} className="login-card">
          <div className="login-icon">
            <LockKeyhole size={23} />
          </div>
          <h2>Zaloguj się</h2>
          <p>Użyj indywidualnego konta pracownika kancelarii.</p>
          {error && <Alert>{error}</Alert>}
          <FieldLabel label="Nazwa użytkownika" required>
            <input
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </FieldLabel>
          <FieldLabel label="Hasło" required>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </FieldLabel>
          <Button disabled={busy} type="submit">
            {busy ? 'Logowanie…' : 'Zaloguj się'}
            <ArrowRight size={17} />
          </Button>
          <p className="login-help">
            Konto oraz reset hasła przygotowuje administrator. W tym środowisku używaj wyłącznie
            danych testowych.
          </p>
        </form>
        <span className="login-footer">BROKER OFFICE · LOKALNE MVP</span>
      </main>
    </div>
  );
}

import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useRouteError } from 'react-router-dom';
import {
  ArrowUpRight,
  CalendarClock,
  ChevronRight,
  FileCheck2,
  Files,
  LayoutGrid,
  Inbox,
  LogOut,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react';
import { useAuth } from './auth';
import { errorMessage } from './api';
import { useApi } from './hooks';
import type { Dashboard } from './types';
import {
  Alert,
  Button,
  DocumentTable,
  ErrorNotice,
  Loading,
  PageHeading,
  PolicyTable,
  hasUnsavedChanges,
} from './ui';

export function AppLayout() {
  const { user, logout } = useAuth();
  const [menu, setMenu] = useState(false),
    [error, setError] = useState('');
  const location = useLocation();
  const area = location.pathname.startsWith('/clients')
    ? 'Klienci'
    : location.pathname.startsWith('/documents')
      ? 'Dokumenty'
      : location.pathname.startsWith('/policies')
        ? 'Polisy'
        : location.pathname.startsWith('/mailbox')
          ? 'Skrzynka'
          : 'Start';
  const displayName = `${user.first_name} ${user.last_name}`.trim() || user.username;
  const links = [
    { to: '/', label: 'Start', icon: LayoutGrid },
    { to: '/mailbox', label: 'Skrzynka', icon: Inbox },
    { to: '/clients', label: 'Klienci', icon: Users },
    { to: '/documents', label: 'Dokumenty', icon: Files },
    { to: '/policies', label: 'Polisy', icon: ShieldCheck },
  ];
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Przejdź do treści
      </a>
      <aside className={`sidebar ${menu ? 'is-open' : ''}`}>
        <Link to="/" className="brand" onClick={() => setMenu(false)}>
          <span className="brand-symbol">
            <ShieldCheck size={23} />
          </span>
          <span>
            broker<span className="brand-light">office</span>
          </span>
        </Link>
        <div className="workspace-label">KANCELARIA UBEZPIECZENIOWA</div>
        <nav aria-label="Główne menu">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMenu(false)}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={19} />
              {label}
              {area === label && <span className="nav-active-dot" />}
            </NavLink>
          ))}
          {user.role === 'ADMIN' && (
            <a className="nav-item admin-link" href="/admin/">
              <Settings size={19} />
              Administracja
              <ArrowUpRight size={14} />
            </a>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="environment-card">
            <span className="environment-icon">
              <ShieldCheck size={17} />
            </span>
            <strong>Wersja demonstracyjna</strong>
            <span>Wyłącznie DANE TESTOWE</span>
            <small>
              Dane zapisują się lokalnie.
              <br />
              Odczyt bez zewnętrznych usług.
            </small>
          </div>
          <div className="user-card">
            <span className="user-avatar">{displayName.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{displayName}</strong>
              <span>{user.role === 'ADMIN' ? 'Administrator' : 'Pracownik kancelarii'}</span>
            </div>
            <Button
              variant="ghost"
              onClick={() => {
                if (
                  hasUnsavedChanges() &&
                  !window.confirm(
                    'Masz niezapisane zmiany. Wylogowanie spowoduje ich utratę. Kontynuować?',
                  )
                )
                  return;
                void logout().catch((failure) => setError(errorMessage(failure)));
              }}
              aria-label="Wyloguj się"
            >
              <LogOut size={17} />
            </Button>
          </div>
        </div>
      </aside>
      {menu && (
        <button
          className="sidebar-backdrop"
          aria-label="Zamknij menu"
          onClick={() => setMenu(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <Button
            variant="ghost"
            className="mobile-menu"
            onClick={() => setMenu(!menu)}
            aria-label={menu ? 'Zamknij menu' : 'Otwórz menu'}
          >
            {menu ? <X size={22} /> : <Menu size={22} />}
          </Button>
          <div className="breadcrumb">
            Kancelaria <ChevronRight size={14} />
            <span>{area}</span>
          </div>
          <div className="topbar-right">
            <span className="environment-pill">
              <span className="status-dot" />
              DANE TESTOWE
            </span>
            <Link to="/clients" className="icon-link" aria-label="Przejdź do wyszukiwania klientów">
              <Search size={18} />
            </Link>
          </div>
        </header>
        <main
          id="main-content"
          className={`main-content ${location.pathname.match(/^\/documents\/\d+/) ? 'wide-content' : ''}`}
        >
          {error && <Alert>{error}</Alert>}
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>Broker Office · MVP demonstracyjne</span>
          <span>Wszystkie dane w środowisku są testowe</span>
        </footer>
      </div>
    </div>
  );
}
export function DashboardPage() {
  const resource = useApi<Dashboard>('/api/dashboard/', 8000);
  const now = new Intl.DateTimeFormat('pl-PL', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'Europe/Warsaw',
  }).format(new Date());
  if (resource.error && !resource.data)
    return <ErrorNotice error={resource.error} onReload={resource.reload} />;
  return (
    <>
      <PageHeading
        eyebrow={now.toUpperCase()}
        title="Dzień dobry. Co dziś na biurku?"
        description="Przegląd dokumentów do sprawdzenia i najbliższych terminów."
        actions={
          <Link className="button primary" to="/documents/new">
            <Files size={17} />
            Dodaj dokument
          </Link>
        }
      />
      {!resource.data ? (
        <Loading />
      ) : (
        <>
          <div className="stats-grid mail-dashboard-grid">
            <Link className="stat-card" to="/mailbox?queue=action">
              <span className="stat-label">
                Do obsłużenia
                <Inbox size={20} />
              </span>
              <div className="stat-number">
                {resource.data.mail_action_count ?? '—'}
                <span>wiadomości</span>
              </div>
              <span className="stat-footer amber-text">
                Przeczytanie nie zamyka obsługi
                <ArrowUpRight size={15} />
              </span>
            </Link>
            <Link className="stat-card" to="/documents">
              <span className="stat-label">
                Do sprawdzenia
                <FileCheck2 size={20} />
              </span>
              <div className="stat-number">
                {resource.data.review_count}
                <span>dokumentów</span>
              </div>
              <span className="stat-footer amber-text">
                Czekają na weryfikację
                <ArrowUpRight size={15} />
              </span>
            </Link>
            <Link className="stat-card" to="/policies?expires_in=30">
              <span className="stat-label">
                Kończąca się ochrona
                <CalendarClock size={20} />
              </span>
              <div className="stat-number">
                {resource.data.expiring_count}
                <span>polis</span>
              </div>
              <span className="stat-footer">
                W najbliższych 30 dniach
                <ArrowUpRight size={15} />
              </span>
            </Link>
            <Link className="stat-card" to="/clients">
              <span className="stat-label">
                Aktywne kartoteki
                <Users size={20} />
              </span>
              <div className="stat-number">
                {resource.data.clients_count}
                <span>klientów</span>
              </div>
              <span className="stat-footer">
                Wspólna baza kancelarii
                <ArrowUpRight size={15} />
              </span>
            </Link>
          </div>
          <div className="mail-dashboard-links">
            <Link to="/mailbox?queue=unassigned">
              Nieprzydzielone wiadomości: {resource.data.mail_unassigned_count ?? '—'}
            </Link>
            <Link to="/mailbox?queue=mine">
              Moje wiadomości: {resource.data.mail_mine_count ?? '—'}
            </Link>
          </div>
          {resource.data.failed_count > 0 && (
            <Alert kind="warning">
              {resource.data.failed_count} dokumentów wymaga ponowienia odczytu. Otwórz plik
              poniżej, aby sprawdzić przyczynę błędu.
            </Alert>
          )}
          <section className="panel dashboard-documents">
            <div className="card-heading padded">
              <div>
                <h2>
                  Dokumenty do sprawdzenia{' '}
                  <span className="count">{resource.data.review_count}</span>
                </h2>
                <p>Sprawdź odczyt, uzupełnij braki i zatwierdź wersję.</p>
              </div>
              <Link className="text-link" to="/documents">
                Wszystkie dokumenty
                <ArrowUpRight size={14} />
              </Link>
            </div>
            <DocumentTable documents={resource.data.review_documents} />
          </section>
          {resource.data.failed_documents.length > 0 && (
            <section className="panel">
              <div className="card-heading padded">
                <h2>
                  Błędy odczytu <span className="count">{resource.data.failed_count}</span>
                </h2>
              </div>
              <DocumentTable documents={resource.data.failed_documents} />
            </section>
          )}
          <section className="panel">
            <div className="card-heading padded">
              <div>
                <h2>Najbliższe końce ochrony</h2>
                <p>Najbliższe 30 dni · zakres demonstracyjny, obie daty włącznie.</p>
              </div>
              <Link className="text-link" to="/policies?expires_in=30">
                Przejdź do polis
                <ArrowUpRight size={14} />
              </Link>
            </div>
            <PolicyTable policies={resource.data.expiring_policies} />
          </section>
          <div className="dashboard-note">
            <ShieldCheck size={17} />
            <p>
              Zatwierdzenie wniosku zapisuje wersję odczytu. Kartoteki klientów i polisy uzupełniasz
              samodzielnie.
            </p>
          </div>
        </>
      )}
    </>
  );
}
export function NotFoundPage() {
  return (
    <>
      <PageHeading
        title="Nie znaleziono strony"
        description="Sprawdź adres lub wróć do głównego widoku kancelarii."
      />
      <Link className="button primary" to="/">
        Przejdź na Start
      </Link>
    </>
  );
}
export function RouteErrorPage() {
  const error = useRouteError();
  return (
    <main className="standalone-error">
      <h1>Nie udało się wyświetlić strony</h1>
      <ErrorNotice error={errorMessage(error)} />
      <a className="button primary" href="/">
        Wróć na Start
      </a>
    </main>
  );
}

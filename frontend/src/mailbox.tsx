import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  Check,
  Download,
  FilePlus2,
  History,
  Mail,
  Paperclip,
  RefreshCw,
  Search,
  UserRound,
  X,
} from 'lucide-react';
import { api, dateTime, params, post } from './api';
import { useAuth } from './auth';
import { ClientPicker } from './clients';
import { useApi, useDebounce, useMounted } from './hooks';
import { PolicyPicker } from './policies';
import type { Client, DocumentRecord, Page, Policy } from './types';
import type {
  MailAttachment,
  Mailbox,
  MailMessage,
  MailPage,
  MailUser,
  MessageRow,
  WorkStatus,
} from './mail-types';
import {
  Alert,
  Badge,
  Button,
  Empty,
  ErrorNotice,
  FieldLabel,
  Loading,
  Modal,
  PageHeading,
  Pagination,
  UnsavedGuard,
  Warnings,
} from './ui';

export const workLabels: Record<WorkStatus, string> = {
  todo: 'Do obsłużenia',
  in_progress: 'W trakcie',
  waiting: 'Oczekujemy',
  done: 'Obsłużona',
  no_action: 'Nie wymaga działania',
};
export function WorkBadge({ status }: { status: WorkStatus }) {
  return (
    <Badge
      tone={
        status === 'done'
          ? 'green'
          : status === 'todo'
            ? 'amber'
            : status === 'in_progress'
              ? 'blue'
              : 'neutral'
      }
    >
      {workLabels[status]}
    </Badge>
  );
}
const sourceLabels: Record<string, string> = {
  demo: 'Tryb demonstracyjny',
  disabled: 'Integracja wyłączona',
  paused: 'Import wstrzymany',
  connected: 'Połączono',
  idle: 'Połączono',
  syncing: 'Trwa synchronizacja',
  running: 'Trwa synchronizacja',
  error: 'Błąd integracji',
  needs_resync: 'Wymagana ponowna synchronizacja',
  resync_required: 'Wymagana ponowna synchronizacja',
  unconfigured: 'Integracja nieskonfigurowana',
  configuration_changed: 'Konfiguracja źródła zmieniona — wymaga kontroli',
  ready: 'Import aktywny — oczekuje na przebieg',
  rebuilding: 'Odbudowa synchronizacji',
};

export function MailboxSources() {
  const { user } = useAuth();
  const resource = useApi<{ results: Mailbox[]; configuration_error?: string }>(
    '/api/mailboxes/',
    8000,
  );
  const [busy, setBusy] = useState<number | null>(null),
    [error, setError] = useState<unknown>(null),
    [notice, setNotice] = useState('');
  const [confirm, setConfirm] = useState<{ mailbox: Mailbox; action: 'start' | 'recover' } | null>(
    null,
  );
  async function control(mailbox: Mailbox, action: string) {
    if (busy !== null) return;
    setBusy(mailbox.id);
    setConfirm(null);
    setError(null);
    setNotice('');
    try {
      const result = await post<{
        ok?: boolean;
        queued?: boolean;
        state?: string;
        error_message?: string;
      }>(`/api/mailboxes/${mailbox.id}/control/`, { action, version: mailbox.version });
      if (result.ok === false)
        throw new Error(result.error_message || 'Test połączenia nie powiódł się.');
      if (result.queued === false) {
        resource.reload();
        if (result.state === 'error')
          throw new Error(
            'Nie udało się zlecić synchronizacji. Sprawdź błąd źródła i proces roboczy.',
          );
        setNotice(
          'Nie utworzono kolejnego zadania: trwa odbiór, obowiązuje odstęp pomiędzy próbami albo import jest wstrzymany. Aktualny stan widoczny jest poniżej.',
        );
        return;
      }
      setNotice(
        action === 'test'
          ? 'Zakończono test połączenia. Test nie włącza importu ani nie zmienia jego granicy.'
          : 'Przyjęto operację integracji. Aktualny stan jest widoczny poniżej.',
      );
      resource.reload();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(null);
    }
  }
  const sources = resource.data?.results ?? [];
  const historical = sources.filter((mailbox) => mailbox.kind === 'imap' && !mailbox.is_current);
  const renderSource = (mailbox: Mailbox) => (
    <div className="mail-source" key={mailbox.id}>
      <div className="source-state">
        <span className="status-dot" />
        <strong>
          {mailbox.kind === 'demo'
            ? 'Tryb demonstracyjny'
            : (sourceLabels[mailbox.state] ?? 'Stan wymaga kontroli administratora')}
        </strong>
        <span>{mailbox.folder}</span>
        {mailbox.kind === 'imap' && !mailbox.enabled && <Badge>Import wyłączony</Badge>}
        {mailbox.kind === 'imap' && !mailbox.is_current && (
          <Badge>Historyczne źródło — zachowane wiadomości</Badge>
        )}
      </div>
      <p>
        {mailbox.kind === 'demo'
          ? 'Syntetyczne wiadomości są dodawane jawną komendą demonstracyjną. To źródło nie łączy się z Internetem.'
          : 'Importujemy INBOX. Wiadomość przeniesiona lub usunięta u dostawcy przed odczytem może nie zostać pobrana.'}
      </p>
      <div className="mail-source-meta">
        <span>
          Ostatni udany przebieg:{' '}
          {mailbox.last_success ? dateTime(mailbox.last_success) : 'brak potwierdzonego przebiegu'}
        </span>
        <span>
          Oczekujące pobrania: {mailbox.pending_count} · Problemy: {mailbox.error_count}
        </span>
      </div>
      {mailbox.error_message && <Alert>{mailbox.error_message}</Alert>}
      {mailbox.boundary_uid !== null && mailbox.kind === 'imap' && (
        <p className="muted">
          Wcześniejsza historia została wyłączona z automatycznego importu. Granica UID:{' '}
          {mailbox.boundary_uid}; identyfikator folderu: {mailbox.uidvalidity}. Nie oznacza to
          obsłużenia starszych wiadomości.
        </p>
      )}
      {user.role === 'ADMIN' && mailbox.kind === 'imap' && mailbox.is_current && (
        <div className="mail-source-actions">
          <Button
            variant="secondary"
            disabled={busy !== null}
            onClick={() => void control(mailbox, 'test')}
          >
            Test połączenia
          </Button>
          {mailbox.enabled ? (
            <Button
              variant="secondary"
              disabled={busy !== null}
              onClick={() => void control(mailbox, 'pause')}
            >
              Wstrzymaj import
            </Button>
          ) : (
            <Button
              variant="secondary"
              disabled={busy !== null}
              onClick={() => setConfirm({ mailbox, action: 'start' })}
            >
              Rozpocznij import
            </Button>
          )}
          <Button
            variant="secondary"
            disabled={busy !== null || !mailbox.enabled}
            onClick={() => void control(mailbox, 'sync')}
          >
            Zleć synchronizację IMAP
          </Button>
          {(mailbox.state.includes('resync') || mailbox.state.includes('validity')) && (
            <Button
              variant="secondary"
              disabled={busy !== null}
              onClick={() => setConfirm({ mailbox, action: 'recover' })}
            >
              Odbuduj synchronizację
            </Button>
          )}
        </div>
      )}
    </div>
  );
  return (
    <section className="mail-source-panel panel" aria-label="Stan skrzynki">
      <div className="card-heading">
        <h2>Źródło wiadomości</h2>
        <Badge>Odbiór tylko do odczytu</Badge>
      </div>
      {resource.error && <ErrorNotice error={resource.error} onReload={resource.reload} />}
      {!!error && <ErrorNotice error={error} onReload={resource.reload} />}
      {notice && <Alert kind="info">{notice}</Alert>}
      {resource.data?.configuration_error && <Alert>{resource.data.configuration_error}</Alert>}
      {!resource.data && !resource.error && <Loading />}
      {resource.data?.results.length === 0 && (
        <Alert kind="warning">
          Brak skonfigurowanego źródła. Administrator może przygotować demonstrację lub konfigurację
          integracji.
        </Alert>
      )}
      {sources.filter((mailbox) => mailbox.kind === 'demo' || mailbox.is_current).map(renderSource)}
      {historical.length > 0 && (
        <details className="message-headers">
          <summary>Wcześniejsze źródła — zachowane wiadomości ({historical.length})</summary>
          {historical.map(renderSource)}
        </details>
      )}
      {confirm && (
        <Modal
          title={
            confirm.action === 'start' ? 'Rozpocznij import INBOX' : 'Odbuduj stan synchronizacji'
          }
          onClose={() => setConfirm(null)}
        >
          <p>
            {confirm.action === 'start'
              ? 'Przy pierwszym udanym otwarciu folderu aplikacja zapisze granicę nowych wiadomości. Starsza historia nie zostanie zaimportowana. Wznowienie istniejącej integracji zachowuje jej granicę.'
              : 'Historia pracy pozostanie zachowana. Po zmianie identyfikatora folderu niejednoznaczne wiadomości wymagają ponownej kontroli; nie zostaną uznane automatycznie za obsłużone.'}
          </p>
          <div className="form-actions">
            <Button variant="secondary" onClick={() => setConfirm(null)}>
              Anuluj
            </Button>
            <Button onClick={() => void control(confirm.mailbox, confirm.action)}>
              Potwierdź operację
            </Button>
          </div>
        </Modal>
      )}
    </section>
  );
}

export function MessageTable({ messages }: { messages: MessageRow[] }) {
  return messages.length ? (
    <div className="table-wrap">
      <table className="mail-table">
        <thead>
          <tr>
            <th>Wiadomość</th>
            <th>Stan obsługi</th>
            <th>Odpowiedzialny</th>
            <th>Klient</th>
            <th>Odebrano</th>
          </tr>
        </thead>
        <tbody>
          {messages.map((message) => (
            <tr key={message.id} className={!message.is_read ? 'mail-unread' : ''}>
              <td>
                <Link className="row-link" to={`/mailbox/${message.id}`}>
                  <span className="mail-subject">
                    {!message.is_read && (
                      <span className="unread-dot" aria-label="Nie otwierano na Twoim koncie" />
                    )}
                    {message.subject || '(bez tematu)'}
                  </span>
                  <small>
                    {message.sender_name && `${message.sender_name} · `}
                    {message.sender_address || 'Nieprawidłowy lub brakujący nadawca'}
                  </small>
                </Link>
                <div className="mail-row-meta">
                  {message.attachment_count > 0 && (
                    <span>
                      <Paperclip size={13} />
                      {message.attachment_count} załączników
                    </span>
                  )}
                  {message.fetch_state !== 'ready' && (
                    <Badge tone={message.fetch_state === 'error' ? 'red' : 'neutral'}>
                      {message.fetch_state === 'error'
                        ? 'Problem pobrania'
                        : 'Oczekuje na pobranie'}
                    </Badge>
                  )}
                  {message.source_kind === 'demo' && <span>DANE TESTOWE</span>}
                </div>
              </td>
              <td>
                <WorkBadge status={message.status} />
              </td>
              <td>
                {message.owner ? (
                  <>
                    {message.owner.username}
                    {!message.owner.is_active && (
                      <small className="error-text">
                        Konto nieaktywne — wymaga przekazania przez administratora
                      </small>
                    )}
                  </>
                ) : (
                  'Nieprzydzielona'
                )}
              </td>
              <td>
                {message.client ? (
                  <Link to={`/clients/${message.client}`}>{message.client_name}</Link>
                ) : (
                  'Bez przypisanego klienta'
                )}
              </td>
              <td className="nowrap muted">
                {message.received_at ? dateTime(message.received_at) : 'Nieustalona data odbioru'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty
      title="Brak wiadomości spełniających filtry"
      description="Sprawdź filtry oraz stan źródła. Brak wyników nie potwierdza poprawnego działania synchronizacji."
    />
  );
}

export function MailboxPage() {
  const [query, setQuery] = useSearchParams();
  const search = query.get('search') ?? '',
    queue = query.get('queue') ?? 'action',
    status = query.get('status') ?? '',
    client = query.get('client') ?? '',
    ordering = query.get('ordering') ?? 'received_at';
  const page = Math.max(1, Number(query.get('page')) || 1);
  const resource = useApi<MailPage>(
    `/api/messages/?${params({ queue, status, client, ordering, search: useDebounce(search), page })}`,
    6000,
  );
  const [clientPicker, setClientPicker] = useState(false);
  function filter(key: string, value: string) {
    setQuery((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== 'page') next.delete('page');
      return next;
    });
  }
  return (
    <>
      <PageHeading
        eyebrow="WSPÓLNA SKRZYNKA"
        title="Skrzynka"
        description="Przeczytanie wiadomości nie oznacza jej obsłużenia."
        actions={
          <Button variant="secondary" onClick={resource.reload}>
            <RefreshCw size={16} />
            Odśwież listę
          </Button>
        }
      />
      <MailboxSources />
      <Alert kind="info">
        Tutaj odbieramy i organizujemy pracę. Odpowiedzi wysyłasz w dotychczasowej poczcie, a wynik
        odnotowujesz ręcznie. Aplikacja nie wysyła wiadomości.
      </Alert>
      <section className="panel">
        <div className="filter-bar mail-filters">
          <label className="search-field">
            <Search size={18} />
            <input
              aria-label="Szukaj wiadomości"
              placeholder="Temat, nazwa lub adres nadawcy…"
              value={search}
              onChange={(event) => filter('search', event.target.value)}
            />
          </label>
          <select
            aria-label="Kolejka wiadomości"
            value={queue}
            onChange={(event) => filter('queue', event.target.value)}
          >
            <option value="action">Wymagające działania</option>
            <option value="unassigned">Nieprzydzielone</option>
            <option value="mine">Moje</option>
            <option value="all">Wszystkie</option>
          </select>
          <select
            aria-label="Stan obsługi wiadomości"
            value={status}
            onChange={(event) => filter('status', event.target.value)}
          >
            <option value="">Każdy stan</option>
            {Object.entries(workLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="Sortowanie wiadomości"
            value={ordering}
            onChange={(event) => filter('ordering', event.target.value)}
          >
            <option value="received_at">Najstarsze najpierw</option>
            <option value="-received_at">Najnowsze najpierw</option>
          </select>
          <Button variant="secondary" onClick={() => setClientPicker(true)}>
            {client ? `Klient #${client}` : 'Filtr klienta'}
          </Button>
          {client && (
            <Button
              variant="ghost"
              onClick={() => filter('client', '')}
              aria-label="Usuń filtr klienta"
            >
              <X size={16} />
            </Button>
          )}
        </div>
        {resource.data?.counts && (
          <div className="mail-counts" aria-label="Liczniki filtrowanej skrzynki">
            <strong>Cały filtrowany zbiór: {resource.data.counts.total}</strong>
            {Object.entries(workLabels).map(([value, label]) => (
              <span key={value}>
                {label}: {resource.data!.counts[value as WorkStatus]}
              </span>
            ))}
          </div>
        )}
        {resource.error && <ErrorNotice error={resource.error} onReload={resource.reload} />}
        {resource.data ? (
          <>
            <MessageTable messages={resource.data.results} />
            <Pagination
              data={resource.data}
              page={page}
              onPage={(value) => filter('page', String(value))}
            />
          </>
        ) : (
          !resource.error && <Loading />
        )}
      </section>
      {clientPicker && (
        <Modal title="Filtruj wiadomości klienta" onClose={() => setClientPicker(false)}>
          <ClientPicker
            onSelect={(selected) => {
              filter('client', String(selected.id));
              setClientPicker(false);
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function ClientCorrespondence({ clientId }: { clientId: number }) {
  const resource = useApi<MailPage>(
    `/api/messages/?${params({ client: clientId, queue: 'all', ordering: '-received_at' })}`,
    10000,
  );
  return (
    <section className="panel">
      <div className="card-heading padded">
        <h2>
          Korespondencja <span className="count">{resource.data?.count ?? '—'}</span>
        </h2>
        <Link to={`/mailbox?client=${clientId}&queue=all`}>Wszystkie wiadomości</Link>
      </div>
      {resource.error ? (
        <ErrorNotice error={resource.error} onReload={resource.reload} />
      ) : resource.data ? (
        <MessageTable messages={resource.data.results} />
      ) : (
        <Loading />
      )}
    </section>
  );
}

export function MessagePage() {
  const { id } = useParams();
  const resource = useApi<MailMessage>(`/api/messages/${id}/`, 5000);
  if (!resource.data)
    return resource.error ? (
      <ErrorNotice error={resource.error} onReload={resource.reload} />
    ) : (
      <Loading label="Wczytywanie wiadomości…" />
    );
  return (
    <MessageWorkspace
      key={id}
      message={resource.data}
      refresh={resource.reload}
      networkError={resource.error}
    />
  );
}

export function MessageWorkspace({
  message,
  refresh,
  networkError,
}: {
  message: MailMessage;
  refresh: () => void;
  networkError: string;
}) {
  const { user } = useAuth();
  const mounted = useMounted();
  const [record, setRecord] = useState(message),
    [note, setNote] = useState(message.note),
    [status, setStatus] = useState<WorkStatus>(message.status),
    [selectedClient, setSelectedClient] = useState<{ id: number; display_name: string } | null>(
      message.client
        ? { id: message.client, display_name: message.client_name ?? `Klient #${message.client}` }
        : null,
    ),
    [policy, setPolicy] = useState<Policy | null>(null),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(''),
    [error, setError] = useState<unknown>(null),
    [notice, setNotice] = useState(''),
    [clientPicker, setClientPicker] = useState(false),
    [clientSearch, setClientSearch] = useState(''),
    [assignPicker, setAssignPicker] = useState(false),
    [promoted, setPromoted] = useState<DocumentRecord | null>(null),
    [confirmReload, setConfirmReload] = useState(false);
  const existingPolicy = useApi<Policy>(record.policy ? `/api/policies/${record.policy}/` : null);
  const canEdit = user.role === 'ADMIN' || message.owner?.id === user.id;
  const policyUnresolved = !!record.policy && !existingPolicy.data && !dirty;
  const terminal = record.status === 'done' || record.status === 'no_action';
  const statusNeedsNote = status === 'waiting' || status === 'no_action';
  useEffect(() => {
    if (!dirty && !busy && message.version >= record.version) {
      setRecord(message);
      setNote(message.note);
      setStatus(message.status);
      setSelectedClient(
        message.client
          ? { id: message.client, display_name: message.client_name ?? `Klient #${message.client}` }
          : null,
      );
    }
  }, [message, record.version, dirty, busy]);
  useEffect(() => {
    if (!dirty && !busy) setPolicy(existingPolicy.data);
  }, [existingPolicy.data, dirty, busy]);
  useEffect(() => {
    let active = true;
    void post(`/api/messages/${message.id}/read/`).catch((failure) => {
      if (active) setError(failure);
    });
    return () => {
      active = false;
    };
  }, [message.id]);
  function change(change: () => void) {
    if (busy || !canEdit) return;
    change();
    setDirty(true);
    setNotice('');
  }
  function adopt(result: MailMessage) {
    setRecord(result);
    setNote(result.note);
    setStatus(result.status);
    setSelectedClient(
      result.client
        ? { id: result.client, display_name: result.client_name ?? `Klient #${result.client}` }
        : null,
    );
    setDirty(false);
    refresh();
  }
  async function work(
    action: 'claim' | 'update' | 'release' | 'reopen' | 'assign',
    owner?: number,
  ) {
    if (busy) return;
    setBusy(action);
    setError(null);
    setNotice('');
    try {
      const result = await post<MailMessage>(
        `/api/messages/${record.id}/${action === 'claim' ? 'claim' : 'work'}/`,
        action === 'claim'
          ? { version: record.version }
          : {
              version: record.version,
              action,
              ...(action === 'update'
                ? { status, note, client: selectedClient?.id ?? null, policy: policy?.id ?? null }
                : {}),
              ...(owner ? { owner } : {}),
            },
      );
      if (!mounted.current) return;
      adopt(result);
      setAssignPicker(false);
      setNotice(
        action === 'claim'
          ? 'Przejęto obsługę wiadomości.'
          : action === 'release'
            ? 'Wiadomość wróciła do nieprzydzielonych.'
            : 'Zapisano stan obsługi i historię zmiany.',
      );
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy('');
    }
  }
  async function promote(attachment: MailAttachment) {
    if (!selectedClient || busy || dirty) return;
    setBusy(`attachment-${attachment.id}`);
    setError(null);
    try {
      const result = await post<{ document: DocumentRecord; message_version: number }>(
        `/api/mail-attachments/${attachment.id}/promote/`,
        { version: record.version, client: selectedClient.id, policy: policy?.id ?? null },
      );
      if (!mounted.current) return;
      setPromoted(result.document);
      setRecord((current) => ({ ...current, version: result.message_version }));
      setNotice(
        'Załącznik zapisano w prywatnych dokumentach klienta. Stan obsługi wiadomości pozostaje bez zmian.',
      );
      refresh();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy('');
    }
  }
  async function reload() {
    setConfirmReload(false);
    setBusy('reload');
    try {
      const latest = await api<MailMessage>(`/api/messages/${record.id}/`);
      if (mounted.current) {
        adopt(latest);
        setError(null);
      }
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy('');
    }
  }
  const newer = message.version > record.version;
  return (
    <>
      <UnsavedGuard dirty={dirty || !!busy} />
      <PageHeading
        eyebrow="WIADOMOŚĆ DO OBSŁUGI"
        title={record.subject || '(bez tematu)'}
        back={{ to: '/mailbox', label: 'Wspólna skrzynka' }}
        description={`${record.sender_name ? record.sender_name + ' · ' : ''}${record.sender_address || 'Brak prawidłowego adresu nadawcy'}`}
        actions={
          <Button variant="secondary" disabled={!!busy} onClick={refresh}>
            <RefreshCw size={16} />
            Odśwież szczegóły
          </Button>
        }
      />
      <div className="message-status-bar">
        <WorkBadge status={message.status} />
        <span>
          {message.owner ? `Odpowiedzialny: ${message.owner.username}` : 'Nieprzydzielona'}
        </span>
        <Badge>{record.source_kind === 'demo' ? 'DANE TESTOWE' : 'INBOX'}</Badge>
        <span>Otwarcie nie zamyka obsługi</span>
      </div>
      {networkError && <ErrorNotice error={networkError} onReload={refresh} />}
      {!!error && <ErrorNotice error={error} onReload={() => setConfirmReload(true)} />}
      {notice && (
        <Alert kind="success">
          {notice}
          {promoted && (
            <>
              {' '}
              <Link to={`/documents/${promoted.id}`}>Otwórz dokument i odczyt</Link>
            </>
          )}
        </Alert>
      )}
      {newer && dirty && (
        <Alert kind="warning">
          Inny pracownik zapisał nowszą wersję wiadomości. Twoje wpisy pozostają w formularzu. Przed
          wczytaniem bieżącej wersji zachowaj swoją notatkę.
        </Alert>
      )}
      {message.owner && !message.owner.is_active && (
        <Alert kind="warning">
          Właściciel obsługi ma nieaktywne konto. Administrator powinien przekazać tę wiadomość
          aktywnemu pracownikowi.
        </Alert>
      )}
      {record.fetch_state !== 'ready' && (
        <Alert kind={record.fetch_state === 'error' ? 'error' : 'info'}>
          {record.fetch_state === 'error'
            ? 'Treść wymaga uwagi: '
            : 'Wiadomość oczekuje na pobranie. '}
          {record.fetch_error} Ten stan techniczny nie oznacza obsłużenia wiadomości.
        </Alert>
      )}
      <Warnings items={record.warnings} />
      {record.recovery_status === 'review' && (
        <Alert kind="warning">
          Po odbudowie synchronizacji ta wiadomość wymaga sprawdzenia możliwych wcześniejszych
          odpowiedników. Nie została automatycznie uznana za obsłużoną.
          {!!record.recovery_candidates?.length && (
            <ul>
              {record.recovery_candidates.map((candidate) => (
                <li key={candidate}>
                  <Link to={`/mailbox/${candidate}`}>
                    Porównaj z wcześniejszą wiadomością #{candidate}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Alert>
      )}
      <div className="message-layout">
        <div className="message-content">
          <section className="panel info-card">
            <h2>
              <Mail size={18} />
              Treść wiadomości
            </h2>
            <dl className="detail-list two-columns">
              <div>
                <dt>Odebrano u dostawcy</dt>
                <dd>
                  {record.received_at ? dateTime(record.received_at) : 'Nieustalona data odbioru'}
                </dd>
              </div>
              <div>
                <dt>Data podana przez nadawcę</dt>
                <dd>
                  {record.declared_at ? dateTime(record.declared_at) : 'Brak prawidłowej daty'}
                </dd>
              </div>
              <div>
                <dt>Zaimportowano</dt>
                <dd>{dateTime(record.imported_at)}</dd>
              </div>
            </dl>
            <p className="muted">
              Bezpieczny widok tekstowy. Zdalne obrazy, skrypty i piksele śledzące nie są
              wczytywane.
            </p>
            <div className="message-body" aria-label="Pełna treść wiadomości">
              {record.body_text || 'Brak dostępnej treści tekstowej.'}
            </div>
            {record.headers?.length > 0 && (
              <details className="message-headers">
                <summary>Nagłówki i oryginał wiadomości</summary>
                <dl>
                  {record.headers.map(([name, value], index) => (
                    <div key={index}>
                      <dt>{name}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
                <a className="button secondary" href={`/api/messages/${record.id}/raw/`}>
                  <Download size={16} />
                  Pobierz oryginalną wiadomość
                </a>
              </details>
            )}
          </section>
          <section className="panel info-card">
            <h2>
              <Paperclip size={18} />
              Załączniki ({record.attachments.length})
            </h2>
            <p className="muted">
              Sprawdzenie typu pliku nie zastępuje skanowania antywirusowego. OCR uruchamiasz osobno
              w dokumencie.
            </p>
            {record.attachments.length === 0 ? (
              <p>Ta wiadomość nie ma załączników.</p>
            ) : (
              <div className="mail-attachments">
                {record.attachments.map((attachment) => (
                  <div className="mail-attachment" key={attachment.id}>
                    <div>
                      <strong>{attachment.original_name || 'Załącznik bez nazwy'}</strong>
                      <small>
                        {attachment.mime_type} · {Math.ceil(attachment.size / 1024)} KB
                      </small>
                    </div>
                    {attachment.blocked_reason ? (
                      <Alert kind="warning">
                        Zablokowany załącznik: {attachment.blocked_reason}
                      </Alert>
                    ) : (
                      <div className="stack-actions">
                        <a
                          className="button secondary"
                          href={`/api/mail-attachments/${attachment.id}/download/`}
                        >
                          <Download size={15} />
                          Pobierz załącznik
                        </a>
                        {attachment.document ? (
                          <Link className="button primary" to={`/documents/${attachment.document}`}>
                            Otwórz dokument #{attachment.document}
                          </Link>
                        ) : (
                          <Button
                            variant="secondary"
                            disabled={!canEdit || !selectedClient || dirty || !!busy}
                            onClick={() => void promote(attachment)}
                          >
                            <FilePlus2 size={15} />
                            Dodaj do dokumentów klienta
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {!selectedClient &&
              record.attachments.some((item) => !item.blocked_reason && !item.document) && (
                <p className="muted">
                  Najpierw przejmij wiadomość oraz przypisz i zapisz klienta, aby utworzyć dokument
                  z załącznika.
                </p>
              )}
          </section>
          {record.related_messages.length > 0 && (
            <section className="panel info-card">
              <h2>Powiązane wiadomości</h2>
              <p>
                Powiązanie na podstawie nagłówków nie łączy stanów obsługi. Każda nowa wiadomość
                jest osobną pozycją do obsłużenia.
              </p>
              <ul className="link-list">
                {record.related_messages.map((related) => (
                  <li key={related.id}>
                    <Link to={`/mailbox/${related.id}`}>{related.subject || '(bez tematu)'}</Link>
                    <WorkBadge status={related.status} />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
        <aside className="message-work">
          <section className="panel info-card">
            <h2>
              <UserRound size={18} />
              Obsługa wiadomości
            </h2>
            <p className="muted">
              Praca na wersji {record.version}. Odpowiedź wyślij w dotychczasowej poczcie i odnotuj
              wynik tutaj.
            </p>
            <div className="message-actions">
              {!message.owner && message.status === 'todo' && (
                <Button disabled={!!busy || dirty} onClick={() => void work('claim')}>
                  Zajmij się
                </Button>
              )}
              {canEdit && message.owner && !terminal && (
                <Button
                  variant="secondary"
                  disabled={!!busy || dirty}
                  onClick={() => void work('release')}
                >
                  Zwolnij do obsługi
                </Button>
              )}
              {canEdit && terminal && (
                <Button
                  variant="secondary"
                  disabled={!!busy || dirty}
                  onClick={() => void work('reopen')}
                >
                  Otwórz ponownie
                </Button>
              )}
              {user.role === 'ADMIN' && !terminal && (
                <Button
                  variant="secondary"
                  disabled={!!busy || dirty}
                  onClick={() => setAssignPicker(true)}
                >
                  Przypisz / przekaż
                </Button>
              )}
            </div>
            {!canEdit && (
              <Alert kind="info">
                {message.owner
                  ? `Stan, notatkę i powiązania zmienia ${message.owner.username} lub administrator.`
                  : 'Przejmij wiadomość, aby zmienić stan, notatkę i powiązania.'}
              </Alert>
            )}
            {dirty && !canEdit && (
              <FieldLabel
                label="Kopia Twojej niezapisanej notatki"
                hint="Uprawnienie do edycji zmieniło się. Zachowaliśmy tekst; możesz go skopiować przed wczytaniem nowej wersji."
              >
                <textarea readOnly rows={5} value={note} />
              </FieldLabel>
            )}
            {policyUnresolved && <Loading label="Wczytywanie zapisanego powiązania polisy…" />}
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (!busy && dirty) void work('update');
              }}
            >
              <fieldset className="form-lock" disabled={!canEdit || !!busy || policyUnresolved}>
                <FieldLabel label="Stan obsługi">
                  <select
                    value={status}
                    disabled={terminal || record.status === 'todo'}
                    onChange={(event) => change(() => setStatus(event.target.value as WorkStatus))}
                  >
                    {terminal || record.status === 'todo' ? (
                      <option value={record.status}>{workLabels[record.status]}</option>
                    ) : (
                      <>
                        {(['in_progress', 'waiting', 'done', 'no_action'] as WorkStatus[]).map(
                          (value) => (
                            <option value={value} key={value}>
                              {workLabels[value]}
                            </option>
                          ),
                        )}
                      </>
                    )}
                  </select>
                </FieldLabel>
                <FieldLabel
                  label="Notatka obsługi"
                  required={statusNeedsNote}
                  hint={
                    status === 'waiting'
                      ? 'Napisz, na co czekamy.'
                      : status === 'no_action'
                        ? 'Podaj krótki powód niewymagania działania.'
                        : 'Notatka o wykonanej pracy; status Obsłużona nie potwierdza wysłania odpowiedzi.'
                  }
                >
                  <textarea
                    rows={7}
                    value={note}
                    maxLength={10000}
                    onChange={(event) => change(() => setNote(event.target.value))}
                  />
                </FieldLabel>
                <div className="form-divider" />
                <h3>Powiązania</h3>
                {selectedClient ? (
                  <div className="selected-relation">
                    <Link to={`/clients/${selectedClient.id}`}>{selectedClient.display_name}</Link>
                    <Button
                      variant="ghost"
                      aria-label="Odłącz klienta od wiadomości"
                      onClick={() =>
                        change(() => {
                          setSelectedClient(null);
                          setPolicy(null);
                        })
                      }
                    >
                      <X size={16} />
                    </Button>
                  </div>
                ) : (
                  <p>Bez przypisanego klienta</p>
                )}
                <Button
                  variant="secondary"
                  onClick={() => {
                    setClientSearch('');
                    setClientPicker(true);
                  }}
                >
                  Wybierz klienta
                </Button>
                {selectedClient && (
                  <PolicyPicker
                    key={selectedClient.id}
                    clientId={selectedClient.id}
                    selected={policy}
                    onSelect={(value) => change(() => setPolicy(value))}
                  />
                )}
                {existingPolicy.error && (
                  <ErrorNotice error={existingPolicy.error} onReload={existingPolicy.reload} />
                )}
                <div className="form-actions">
                  <span className={dirty ? 'amber-text' : 'muted'}>
                    {dirty ? 'Niezapisane zmiany' : 'Wersja zapisana'}
                  </span>
                  <Button
                    type="submit"
                    disabled={!dirty || !!busy || (statusNeedsNote && note.trim().length < 3)}
                  >
                    <Check size={16} />
                    {busy === 'update' ? 'Zapisywanie…' : 'Zapisz obsługę'}
                  </Button>
                </div>
              </fieldset>
            </form>
            {record.claimed_at && <p className="muted">Przejęto: {dateTime(record.claimed_at)}</p>}
            {record.completed_at && (
              <p className="muted">
                Zakończono: {record.completed_by?.username ?? 'Pracownik'} ·{' '}
                {dateTime(record.completed_at)}
              </p>
            )}
          </section>
          {record.client_candidates.length > 0 && !record.client && (
            <section className="panel info-card">
              <h2>
                Możliwe kartoteki (
                {record.client_candidate_count ?? record.client_candidates.length})
              </h2>
              <p>
                Podobny adres nadawcy nie potwierdza tożsamości. Powiązanie wymaga Twojego wyboru i
                zapisu.
              </p>
              {(record.client_candidate_count ?? 0) > record.client_candidates.length && (
                <p>
                  Poniżej pokazano pierwsze {record.client_candidates.length} dopasowań. Pozostałe
                  są dostępne w wyszukiwaniu.
                </p>
              )}
              <Button
                variant="secondary"
                disabled={!canEdit || !!busy}
                onClick={() => {
                  setClientSearch(record.sender_address);
                  setClientPicker(true);
                }}
              >
                Przeszukaj wszystkie kartoteki
              </Button>
              {record.client_candidates.map((candidate) => (
                <div className="candidate-row" key={candidate.id}>
                  <Link to={`/clients/${candidate.id}`}>{candidate.display_name}</Link>
                  {candidate.archived ? (
                    <Badge>Archiwum</Badge>
                  ) : (
                    <Button
                      variant="secondary"
                      disabled={!canEdit || !!busy}
                      onClick={() =>
                        change(() => {
                          setSelectedClient(candidate);
                          setPolicy(null);
                        })
                      }
                    >
                      Wybierz tę kartotekę
                    </Button>
                  )}
                </div>
              ))}
            </section>
          )}
          <MessageHistory key={`${record.id}-${record.version}`} messageId={record.id} />
        </aside>
      </div>
      {clientPicker && (
        <Modal title="Powiąż istniejącą kartotekę" onClose={() => setClientPicker(false)}>
          <ClientPicker
            initialSearch={clientSearch}
            onSelect={(selected: Client) => {
              change(() => {
                setSelectedClient(selected);
                setPolicy(null);
              });
              setClientPicker(false);
            }}
          />
        </Modal>
      )}
      {assignPicker && (
        <Modal title="Przypisz wiadomość pracownikowi" onClose={() => setAssignPicker(false)}>
          <MailUserPicker onSelect={(owner) => void work('assign', owner.id)} disabled={!!busy} />
        </Modal>
      )}
      {confirmReload && (
        <Modal title="Wczytaj aktualną wiadomość" onClose={() => setConfirmReload(false)}>
          <p>
            Niezapisana notatka i wybór powiązań zostaną odrzucone. Skopiuj swoje zmiany przed
            wczytaniem nowszej wersji.
          </p>
          <div className="form-actions">
            <Button variant="secondary" onClick={() => setConfirmReload(false)}>
              Zachowaj moje wpisy
            </Button>
            <Button onClick={() => void reload()}>Wczytaj aktualne dane</Button>
          </div>
        </Modal>
      )}
    </>
  );
}
const mailActionLabels: Record<string, string> = {
  'mail.imported': 'Zaimportowano wiadomość',
  'mail.claimed': 'Przejęto obsługę',
  'mail.updated': 'Zapisano stan, notatkę lub powiązania',
  'mail.released': 'Zwolniono wiadomość do obsługi',
  'mail.assigned': 'Przypisano lub przekazano wiadomość',
  'mail.reopened': 'Ponownie otwarto obsługę',
  'mail.document_created': 'Utworzono dokument z załącznika',
  'mail.display_normalized': 'Poprawiono wyświetlanie zakończeń wierszy',
};
type MailHistoryEvent = MailMessage['history'][number];
function eventChanges(event: MailHistoryEvent) {
  const before = event.metadata.before as Record<string, unknown> | undefined;
  const after = event.metadata.after as Record<string, unknown> | undefined;
  if (!before || !after) return null;
  const oldStatus = before.status as WorkStatus,
    newStatus = after.status as WorkStatus;
  return (
    <>
      {oldStatus !== newStatus && workLabels[oldStatus] && workLabels[newStatus] && (
        <span>
          {workLabels[oldStatus]} → {workLabels[newStatus]}
        </span>
      )}
      {before.owner_id !== after.owner_id && (
        <span>
          Odpowiedzialny:{' '}
          {typeof before.owner_name === 'string'
            ? before.owner_name
            : before.owner_id
              ? `pracownik #${Number(before.owner_id)}`
              : 'nieprzydzielona'}{' '}
          →{' '}
          {typeof after.owner_name === 'string'
            ? after.owner_name
            : after.owner_id
              ? `pracownik #${Number(after.owner_id)}`
              : 'nieprzydzielona'}
        </span>
      )}
      {before.client_id !== after.client_id && (
        <span>
          {after.client_id ? (
            <Link to={`/clients/${Number(after.client_id)}`}>
              Powiązano kartotekę #{Number(after.client_id)}
            </Link>
          ) : (
            'Odłączono klienta od wiadomości'
          )}
        </span>
      )}
    </>
  );
}
function MessageHistory({ messageId }: { messageId: number }) {
  const [page, setPage] = useState(1);
  const resource = useApi<Page<MailHistoryEvent>>(
    `/api/messages/${messageId}/history/?page=${page}`,
  );
  return (
    <section className="panel info-card">
      <h2>
        <History size={18} />
        Historia obsługi
      </h2>
      {resource.error && <ErrorNotice error={resource.error} onReload={resource.reload} />}
      {resource.data ? (
        <>
          <ol className="timeline">
            {resource.data.results.map((event) => (
              <li key={event.id}>
                <span className="timeline-dot" />
                <strong>{mailActionLabels[event.action] ?? 'Zmiana obsługi wiadomości'}</strong>
                <span>{event.actor_name || 'System'}</span>
                <time>{dateTime(event.created_at)}</time>
                {eventChanges(event)}
              </li>
            ))}
          </ol>
          <Pagination data={resource.data} page={page} onPage={setPage} />
        </>
      ) : (
        !resource.error && <Loading />
      )}
    </section>
  );
}
function MailUserPicker({
  onSelect,
  disabled,
}: {
  onSelect: (user: MailUser) => void;
  disabled: boolean;
}) {
  const [search, setSearch] = useState(''),
    [page, setPage] = useState(1);
  const resource = useApi<Page<MailUser>>(
    `/api/mail-users/?${params({ search: useDebounce(search), page })}`,
  );
  return (
    <>
      <FieldLabel label="Szukaj aktywnego pracownika">
        <input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
      </FieldLabel>
      {resource.error && <ErrorNotice error={resource.error} onReload={resource.reload} />}
      <div className="picker-results">
        {resource.data?.results.map((item) => (
          <Button
            key={item.id}
            variant="secondary"
            disabled={disabled || !item.is_active}
            onClick={() => onSelect(item)}
          >
            {item.username}
          </Button>
        ))}
      </div>
      {resource.data ? (
        <Pagination data={resource.data} page={page} onPage={setPage} />
      ) : (
        <Loading />
      )}
    </>
  );
}

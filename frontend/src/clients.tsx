import { useState } from 'react';
import { flushSync } from 'react-dom';
import type { FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Archive,
  ArrowUpRight,
  Building2,
  ChevronRight,
  FilePlus2,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Plus,
  Search,
  UserRound,
} from 'lucide-react';
import { api, date, dateTime, params, patch, post } from './api';
import { useApi, useDebounce, useMounted } from './hooks';
import type { AuditEvent, Client, DocumentRecord, Page, Policy } from './types';
import {
  Alert,
  Badge,
  Button,
  DocumentTable,
  Empty,
  ErrorNotice,
  FieldLabel,
  Loading,
  Modal,
  PageHeading,
  Pagination,
  PolicyTable,
  UnsavedGuard,
  Warnings,
} from './ui';

export function ClientsPage() {
  const [search, setSearch] = useState(''),
    [archived, setArchived] = useState('false'),
    [ordering, setOrdering] = useState('display_name'),
    [page, setPage] = useState(1);
  const query = useDebounce(search);
  const resource = useApi<Page<Client>>(
    `/api/clients/?${params({ search: query, archived, ordering, page })}`,
  );
  return (
    <>
      <PageHeading
        eyebrow="KARTOTEKA KANCELARII"
        title="Klienci"
        description="Dane kontaktowe, dokumenty i polisy w jednej kartotece."
        actions={
          <Link className="button primary" to="/clients/new">
            <Plus size={17} />
            Dodaj klienta
          </Link>
        }
      />
      <section className="panel">
        <div className="filter-bar">
          <label className="search-field">
            <Search size={18} />
            <input
              aria-label="Szukaj klientów"
              placeholder="Nazwa, identyfikator, kontakt lub numer polisy…"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <select
            aria-label="Status klientów"
            value={archived}
            onChange={(event) => {
              setArchived(event.target.value);
              setPage(1);
            }}
          >
            <option value="false">Aktywni klienci</option>
            <option value="true">Archiwum</option>
            <option value="all">Wszyscy klienci</option>
          </select>
          <select
            aria-label="Sortowanie klientów"
            value={ordering}
            onChange={(event) => {
              setOrdering(event.target.value);
              setPage(1);
            }}
          >
            <option value="display_name">Nazwa A–Z</option>
            <option value="-created_at">Najnowsi</option>
          </select>
        </div>
        {resource.error ? (
          <ErrorNotice error={resource.error} onReload={resource.reload} />
        ) : resource.loading && !resource.data ? (
          <Loading />
        ) : (
          resource.data && (
            <>
              {resource.data.results.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Klient</th>
                        <th>Kontakt</th>
                        <th>Identyfikator</th>
                        <th>Dodano</th>
                        <th>
                          <span className="sr-only">Otwórz</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {resource.data.results.map((client) => (
                        <tr key={client.id}>
                          <td>
                            <Link className="client-cell" to={`/clients/${client.id}`}>
                              <span
                                className={`avatar ${client.kind === 'organization' ? 'organization' : ''}`}
                              >
                                {client.kind === 'organization' ? (
                                  <Building2 size={19} />
                                ) : (
                                  <UserRound size={19} />
                                )}
                              </span>
                              <span className="row-link">
                                {client.display_name}
                                <small>
                                  {client.kind === 'person' ? 'Osoba fizyczna' : 'Organizacja'}
                                  {client.archived ? ' · Archiwum' : ''}
                                </small>
                              </span>
                            </Link>
                          </td>
                          <td>
                            <span>{client.email || '—'}</span>
                            <small>{client.phone}</small>
                          </td>
                          <td className="muted">{client.pesel || client.nip || 'Nie podano'}</td>
                          <td className="muted nowrap">{date(client.created_at)}</td>
                          <td>
                            <Link
                              className="icon-link"
                              to={`/clients/${client.id}`}
                              aria-label={`Otwórz ${client.display_name}`}
                            >
                              <ChevronRight size={17} />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty
                  title="Nie znaleziono klientów"
                  description="Zmień wyszukiwanie lub dodaj nową kartotekę."
                />
              )}
              <Pagination data={resource.data} page={page} onPage={setPage} />
            </>
          )
        )}
      </section>
    </>
  );
}

type ClientInput = Pick<
  Client,
  | 'kind'
  | 'first_name'
  | 'last_name'
  | 'organization_name'
  | 'pesel'
  | 'nip'
  | 'email'
  | 'phone'
  | 'address'
  | 'note'
>;
const emptyClient: ClientInput = {
  kind: 'person',
  first_name: '',
  last_name: '',
  organization_name: '',
  pesel: '',
  nip: '',
  email: '',
  phone: '',
  address: '',
  note: '',
};
export function ClientFormPage() {
  const { id } = useParams();
  const resource = useApi<Client>(id ? `/api/clients/${id}/` : null);
  if (id && resource.error)
    return <ErrorNotice error={resource.error} onReload={resource.reload} />;
  if (id && (!resource.data || resource.loading)) return <Loading />;
  return (
    <ClientForm
      key={id ? `${id}-${resource.data?.version}` : 'new'}
      initial={resource.data}
      reload={resource.reload}
    />
  );
}
export function ClientForm({ initial, reload }: { initial: Client | null; reload: () => void }) {
  const navigate = useNavigate();
  const mounted = useMounted();
  const [values, setValues] = useState<ClientInput>(initial ?? emptyClient),
    [dirty, setDirty] = useState(false),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState<Client | null>(null),
    [confirmReload, setConfirmReload] = useState(false);
  const nameSearch =
    values.kind === 'organization'
      ? values.organization_name
      : `${values.first_name} ${values.last_name}`.trim();
  const duplicateQuery = useDebounce(values.pesel || values.nip || nameSearch);
  const similar = useApi<Page<Client>>(
    duplicateQuery.length > 2
      ? `/api/clients/?${params({ search: duplicateQuery, archived: 'all' })}`
      : null,
  );
  function update(key: keyof ClientInput, value: string) {
    setValues((previous) => ({ ...previous, [key]: value }));
    setDirty(true);
    setSaved(null);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const payload = {
        ...values,
        pesel: values.kind === 'person' ? values.pesel : '',
        nip: values.kind === 'organization' ? values.nip : '',
        ...(initial ? { version: initial.version } : {}),
      };
      const client = initial
        ? await patch<Client>(`/api/clients/${initial.id}/`, payload)
        : await post<Client>('/api/clients/', payload);
      if (!mounted.current) return;
      flushSync(() => {
        setBusy(false);
        setDirty(false);
        setSaved(client);
      });
      void navigate(`/clients/${client.id}`);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  const possible = similar.data?.results.filter((client) => client.id !== initial?.id) ?? [];
  return (
    <>
      <UnsavedGuard dirty={dirty || !!busy} />
      <PageHeading
        title={initial ? 'Edytuj klienta' : 'Nowy klient'}
        description="Nieznane dane możesz uzupełnić później. Pola z gwiazdką są wymagane."
        back={{
          to: initial ? `/clients/${initial.id}` : '/clients',
          label: initial ? 'Kartoteka klienta' : 'Klienci',
        }}
      />
      <form className="panel form-panel" onSubmit={submit}>
        <fieldset disabled={busy} className="form-lock">
          {!!error && (
            <ErrorNotice
              error={error}
              onReload={initial ? () => setConfirmReload(true) : undefined}
            />
          )}
          <Warnings items={saved?.duplicate_warnings} />
          {saved && (
            <Alert kind="success">
              Kartoteka została zapisana.{' '}
              <Link to={`/clients/${saved.id}`}>
                Przejdź do klienta <ArrowUpRight size={14} />
              </Link>
            </Alert>
          )}
          {possible.length > 0 && !saved && (
            <Alert kind="warning">
              Sprawdź możliwe duplikaty:{' '}
              {possible.slice(0, 3).map((client, index) => (
                <span key={client.id}>
                  {index ? ', ' : ''}
                  <Link to={`/clients/${client.id}`}>{client.display_name}</Link>
                </span>
              ))}
              . Wspólny kontakt ani podobna nazwa nie potwierdzają tożsamości. Kartoteki nie zostaną
              automatycznie połączone.
            </Alert>
          )}
          <h2>Dane podstawowe</h2>
          <fieldset className="segmented">
            <legend className="sr-only">Typ klienta</legend>
            <label className={values.kind === 'person' ? 'selected' : ''}>
              <input
                type="radio"
                name="kind"
                value="person"
                checked={values.kind === 'person'}
                onChange={() => update('kind', 'person')}
              />
              <UserRound size={17} />
              Osoba fizyczna
            </label>
            <label className={values.kind === 'organization' ? 'selected' : ''}>
              <input
                type="radio"
                name="kind"
                value="organization"
                checked={values.kind === 'organization'}
                onChange={() => update('kind', 'organization')}
              />
              <Building2 size={17} />
              Organizacja
            </label>
          </fieldset>
          <div className="form-grid">
            {values.kind === 'person' ? (
              <>
                <FieldLabel label="Imię" required>
                  <input
                    required
                    autoComplete="given-name"
                    value={values.first_name}
                    onChange={(event) => update('first_name', event.target.value)}
                  />
                </FieldLabel>
                <FieldLabel label="Nazwisko" required>
                  <input
                    required
                    autoComplete="family-name"
                    value={values.last_name}
                    onChange={(event) => update('last_name', event.target.value)}
                  />
                </FieldLabel>
                <FieldLabel
                  label="PESEL"
                  hint="Opcjonalny identyfikator; przechowywany jako tekst."
                >
                  <input
                    inputMode="numeric"
                    value={values.pesel}
                    onChange={(event) => update('pesel', event.target.value)}
                  />
                </FieldLabel>
              </>
            ) : (
              <>
                <FieldLabel label="Nazwa organizacji" required className="span-2">
                  <input
                    required
                    value={values.organization_name}
                    onChange={(event) => update('organization_name', event.target.value)}
                  />
                </FieldLabel>
                <FieldLabel label="NIP" hint="Opcjonalny identyfikator; przechowywany jako tekst.">
                  <input
                    inputMode="numeric"
                    value={values.nip}
                    onChange={(event) => update('nip', event.target.value)}
                  />
                </FieldLabel>
              </>
            )}
          </div>
          <div className="form-divider" />
          <h2>Kontakt i adres</h2>
          <div className="form-grid">
            <FieldLabel label="E-mail" hint="W demonstracji używaj domeny .invalid.">
              <input
                type="email"
                autoComplete="email"
                value={values.email}
                onChange={(event) => update('email', event.target.value)}
              />
            </FieldLabel>
            <FieldLabel label="Telefon">
              <input
                type="tel"
                autoComplete="tel"
                value={values.phone}
                onChange={(event) => update('phone', event.target.value)}
              />
            </FieldLabel>
            <FieldLabel label="Adres" className="span-2">
              <textarea
                rows={2}
                value={values.address}
                onChange={(event) => update('address', event.target.value)}
              />
            </FieldLabel>
            <FieldLabel label="Notatka" className="span-2">
              <textarea
                rows={3}
                value={values.note}
                onChange={(event) => update('note', event.target.value)}
              />
            </FieldLabel>
          </div>
          <div className="form-actions">
            <Link className="button secondary" to={initial ? `/clients/${initial.id}` : '/clients'}>
              Anuluj
            </Link>
            <Button type="submit" disabled={busy || !!saved}>
              {busy ? 'Zapisywanie…' : 'Zapisz klienta'}
            </Button>
          </div>
        </fieldset>
      </form>
      {confirmReload && (
        <Modal title="Wczytać nowszą kartotekę?" onClose={() => setConfirmReload(false)}>
          <p>
            Twoje niezapisane zmiany zostaną odrzucone. W razie potrzeby skopiuj je przed
            kontynuowaniem.
          </p>
          <div className="form-actions">
            <Button variant="secondary" onClick={() => setConfirmReload(false)}>
              Anuluj
            </Button>
            <Button
              onClick={() => {
                setDirty(false);
                setConfirmReload(false);
                reload();
              }}
            >
              Wczytaj aktualne dane
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
export function ClientDetailPage() {
  const { id } = useParams();
  const resource = useApi<Client>(`/api/clients/${id}/`),
    documents = useApi<Page<DocumentRecord>>(`/api/documents/?client=${id}`),
    policies = useApi<Page<Policy>>(`/api/policies/?client=${id}&archived=all`),
    history = useApi<AuditEvent[]>(`/api/clients/${id}/history/`);
  const [archive, setArchive] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  if (resource.error) return <ErrorNotice error={resource.error} onReload={resource.reload} />;
  if (!resource.data) return <Loading />;
  const client = resource.data;
  async function archiveClient() {
    setBusy(true);
    try {
      await patch(`/api/clients/${id}/`, { version: client.version, archived: !client.archived });
      setArchive(false);
      resource.reload();
      history.reload();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  const actionNames: Record<string, string> = {
    extraction_requested: 'Zlecono odczyt dokumentu',
    review_saved: 'Zapisano wersję roboczą odczytu',
    review_reset: 'Wczytano wynik silnika do wersji roboczej',
    review_approved: 'Zatwierdzono rewizję odczytu',
    revision_exported: 'Pobrano eksport kontrolny',
    'document.downloaded': 'Pobrano oryginał dokumentu',
    'client.created': 'Utworzono kartotekę',
    'client.updated': 'Zmieniono kartotekę',
    'client.archived': 'Zarchiwizowano kartotekę',
    'document.uploaded': 'Dodano dokument',
    'extraction.queued': 'Zlecono odczyt dokumentu',
    'review.saved': 'Zapisano odczyt',
    'review.approved': 'Zatwierdzono odczyt',
    'revision.exported': 'Pobrano eksport kontrolny',
    'policy.created': 'Dodano polisę',
    'policy.updated': 'Zmieniono polisę',
    'policy.archived': 'Zarchiwizowano polisę',
  };
  return (
    <>
      <PageHeading
        title={client.display_name}
        eyebrow={client.kind === 'person' ? 'OSOBA FIZYCZNA' : 'ORGANIZACJA'}
        back={{ to: '/clients', label: 'Klienci' }}
        actions={
          <>
            <Link className="button secondary" to={`/clients/${id}/edit`}>
              <Pencil size={16} />
              Edytuj
            </Link>
            <Link className="button primary" to={`/clients/${id}/upload`}>
              <FilePlus2 size={17} />
              Dodaj dokument
            </Link>
          </>
        }
      />
      {client.archived && <Alert kind="warning">Ta kartoteka jest zarchiwizowana.</Alert>}
      <Warnings items={client.duplicate_warnings} />
      {!!error && <ErrorNotice error={error} onReload={resource.reload} />}
      <div className="client-layout">
        <aside className="detail-aside">
          <section className="panel info-card">
            <div className="card-heading">
              <h2>Dane klienta</h2>
              <Badge>{client.kind === 'person' ? 'Osoba' : 'Organizacja'}</Badge>
            </div>
            <dl className="detail-list">
              <div>
                <dt>
                  <Mail size={15} />
                  E-mail
                </dt>
                <dd>{client.email || 'Nie podano'}</dd>
              </div>
              <div>
                <dt>
                  <Phone size={15} />
                  Telefon
                </dt>
                <dd>{client.phone || 'Nie podano'}</dd>
              </div>
              <div>
                <dt>
                  <MapPin size={15} />
                  Adres
                </dt>
                <dd className="preserve-lines">{client.address || 'Nie podano'}</dd>
              </div>
              <div>
                <dt>{client.kind === 'person' ? 'PESEL' : 'NIP'}</dt>
                <dd>{(client.kind === 'person' ? client.pesel : client.nip) || 'Nie podano'}</dd>
              </div>
            </dl>
            {client.note && (
              <div className="note-block">
                <h3>Notatka</h3>
                <p className="preserve-lines">{client.note}</p>
              </div>
            )}
            <Button variant="ghost" onClick={() => setArchive(true)}>
              <Archive size={15} />
              {client.archived ? 'Przywróć kartotekę' : 'Archiwizuj kartotekę'}
            </Button>
          </section>
          <section className="panel info-card">
            <h2>Historia operacji</h2>
            {history.error ? (
              <ErrorNotice error={history.error} />
            ) : history.loading ? (
              <Loading />
            ) : (
              <ol className="timeline">
                {history.data?.map((item) => (
                  <li key={item.id}>
                    <span className="timeline-dot" />
                    <strong>{actionNames[item.action] ?? item.action}</strong>
                    <span>{item.actor_name || 'System'}</span>
                    <time>{dateTime(item.created_at)}</time>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
        <div className="detail-content">
          <section className="panel">
            <div className="card-heading padded">
              <h2>
                Dokumenty <span className="count">{documents.data?.count ?? 0}</span>
              </h2>
              <Link to={`/documents?client=${id}`} className="text-link">
                Wszystkie <ArrowUpRight size={14} />
              </Link>
            </div>
            {documents.error ? (
              <ErrorNotice error={documents.error} />
            ) : documents.data ? (
              <DocumentTable documents={documents.data.results} compact />
            ) : (
              <Loading />
            )}
          </section>
          <section className="panel">
            <div className="card-heading padded">
              <h2>
                Polisy <span className="count">{policies.data?.count ?? 0}</span>
              </h2>
              <Link className="text-link" to={`/policies/new?client=${id}`}>
                <Plus size={15} />
                Dodaj polisę
              </Link>
            </div>
            {policies.error ? (
              <ErrorNotice error={policies.error} />
            ) : policies.data ? (
              <PolicyTable policies={policies.data.results} />
            ) : (
              <Loading />
            )}
            {!!policies.data?.next && (
              <div className="padded">
                <Link to={`/policies?client=${id}`}>Wszystkie polisy klienta</Link>
              </div>
            )}
          </section>
        </div>
      </div>
      {archive && (
        <Modal
          title={client.archived ? 'Przywróć kartotekę' : 'Archiwizuj kartotekę'}
          onClose={() => setArchive(false)}
        >
          <p>
            {client.archived
              ? 'Klient ponownie pojawi się na liście aktywnych kartotek.'
              : 'Kartoteka zostanie przeniesiona do archiwum. Powiązane dokumenty, polisy i historia pozostaną dostępne.'}
          </p>
          <div className="form-actions">
            <Button variant="secondary" onClick={() => setArchive(false)}>
              Anuluj
            </Button>
            <Button disabled={busy} onClick={() => void archiveClient()}>
              {busy ? 'Zapisywanie…' : client.archived ? 'Przywróć' : 'Archiwizuj'}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

export function ClientPicker({
  onSelect,
  exclude = [],
  label = 'Znajdź klienta',
}: {
  onSelect: (client: Client) => void;
  exclude?: number[];
  label?: string;
}) {
  const [search, setSearch] = useState('');
  const query = useDebounce(search);
  const exclusions = [...new Set(exclude)].sort((a, b) => a - b).join(',');
  const filterKey = `${query}:${exclusions}`;
  const [pagination, setPagination] = useState({ key: filterKey, page: 1 });
  const page = pagination.key === filterKey ? pagination.page : 1;
  const resource = useApi<Page<Client>>(
    `/api/clients/?${params({ search: query, archived: 'false', exclude: exclusions, page })}`,
  );
  return (
    <div className="client-picker">
      <label className="search-field">
        <Search size={17} />
        <input
          aria-label={label}
          placeholder="Szukaj w istniejących kartotekach…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      {resource.error && <ErrorNotice error={resource.error} onReload={resource.reload} />}
      <div className="picker-results">
        {resource.data?.results.map((client) => (
          <button
            type="button"
            className="picker-option"
            key={client.id}
            onClick={() => onSelect(client)}
          >
            <span>
              {client.display_name}
              <small>{client.email || client.phone || 'Brak danych kontaktowych'}</small>
            </span>
            <Plus size={16} />
          </button>
        ))}
        {resource.loading && !resource.data && <Loading />}
        {resource.data && !resource.data.results.length && <p>Nie znaleziono kartotek.</p>}
      </div>
      {resource.data && (
        <Pagination
          data={resource.data}
          page={page}
          onPage={(value) => setPagination({ key: filterKey, page: value })}
        />
      )}
      <small>
        Wybierz istniejącą kartotekę. Wyszukiwanie i kolejne strony obejmują wszystkich dostępnych
        klientów.
      </small>
    </div>
  );
}

export async function getClient(id: string): Promise<Client> {
  return api<Client>(`/api/clients/${id}/`);
}

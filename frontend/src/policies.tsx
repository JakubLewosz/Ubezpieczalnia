import { useState } from 'react';
import type { FormEvent } from 'react';
import { flushSync } from 'react-dom';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Archive, FileText, Pencil, Plus, Search, ShieldCheck, X } from 'lucide-react';
import { date, money, params, patch, post } from './api';
import { ClientPicker } from './clients';
import { useApi, useDebounce } from './hooks';
import type { Client, DocumentRecord, Page, Participant, Policy } from './types';
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
  PolicyTable,
  UnsavedGuard,
  Warnings,
} from './ui';

export function PoliciesPage() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(''),
    [expires, setExpires] = useState(searchParams.get('expires_in') ?? ''),
    [archived, setArchived] = useState('false'),
    [page, setPage] = useState(1);
  const query = useDebounce(search);
  const resource = useApi<Page<Policy>>(
    `/api/policies/?${params({ search: query, expires_in: expires, archived, page, client: searchParams.get('client') ?? '' })}`,
  );
  return (
    <>
      <PageHeading
        eyebrow="EWIDENCJA RĘCZNA"
        title="Polisy"
        description="Umowy ubezpieczenia, uczestnicy i kalendarz ochrony."
        actions={
          <Link className="button primary" to="/policies/new">
            <Plus size={17} />
            Dodaj polisę
          </Link>
        }
      />
      <section className="panel">
        <div className="filter-bar">
          <label className="search-field">
            <Search size={18} />
            <input
              aria-label="Szukaj polis"
              placeholder="Numer polisy lub ubezpieczyciel…"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <select
            aria-label="Termin końca polisy"
            value={expires}
            onChange={(event) => {
              setExpires(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Wszystkie terminy</option>
            <option value="7">Koniec w ciągu 7 dni</option>
            <option value="30">Koniec w ciągu 30 dni</option>
            <option value="60">Koniec w ciągu 60 dni</option>
          </select>
          <select
            aria-label="Status archiwizacji polis"
            value={archived}
            onChange={(event) => {
              setArchived(event.target.value);
              setPage(1);
            }}
          >
            <option value="false">Bieżąca ewidencja</option>
            <option value="true">Archiwum</option>
            <option value="all">Wszystkie polisy</option>
          </select>
        </div>
        {expires && (
          <div className="filter-note">
            Zakres demonstracyjny: od dziś do dziś + {expires} dni, obie daty włącznie. Strefa
            Europe/Warsaw.
          </div>
        )}
        {resource.error ? (
          <ErrorNotice error={resource.error} onReload={resource.reload} />
        ) : resource.data ? (
          <>
            <PolicyTable policies={resource.data.results} />
            <Pagination data={resource.data} page={page} onPage={setPage} />
          </>
        ) : (
          <Loading />
        )}
      </section>
    </>
  );
}

type PolicyInput = Pick<
  Policy,
  | 'insurer'
  | 'number'
  | 'insurance_type'
  | 'start_date'
  | 'end_date'
  | 'premium'
  | 'currency'
  | 'subject'
  | 'participants'
  | 'document_ids'
>;
const emptyPolicy: PolicyInput = {
  insurer: '',
  number: '',
  insurance_type: '',
  start_date: '',
  end_date: '',
  premium: null,
  currency: 'PLN',
  subject: '',
  participants: [],
  document_ids: [],
};
export function PolicyFormPage() {
  const { id } = useParams();
  const [query] = useSearchParams();
  const resource = useApi<Policy>(id ? `/api/policies/${id}/` : null);
  const client = useApi<Client>(
    query.get('client') ? `/api/clients/${query.get('client')}/` : null,
  );
  if (resource.error || client.error) return <ErrorNotice error={resource.error || client.error} />;
  if ((id && !resource.data) || (query.get('client') && !client.data)) return <Loading />;
  return (
    <PolicyForm
      key={resource.data?.version ?? 'new'}
      initial={resource.data}
      initialClient={client.data}
      reload={resource.reload}
    />
  );
}
function PolicyForm({
  initial,
  initialClient,
  reload,
}: {
  initial: Policy | null;
  initialClient: Client | null;
  reload: () => void;
}) {
  const navigate = useNavigate();
  const [values, setValues] = useState<PolicyInput>(
    initial ?? {
      ...emptyPolicy,
      participants: initialClient
        ? [
            {
              client: initialClient.id,
              client_name: initialClient.display_name,
              role: 'policyholder',
            },
          ]
        : [],
    },
  );
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null),
    [participantPicker, setParticipantPicker] = useState(false),
    [newRole, setNewRole] = useState<Participant['role']>('insured'),
    [saved, setSaved] = useState<Policy | null>(null),
    [confirmReload, setConfirmReload] = useState(false),
    [documentSearch, setDocumentSearch] = useState('');
  const documents = useApi<Page<DocumentRecord>>(
    `/api/documents/?${params({ search: useDebounce(documentSearch) })}`,
  );
  function update<K extends keyof PolicyInput>(key: K, value: PolicyInput[K]) {
    setValues((previous) => ({ ...previous, [key]: value }));
    setDirty(true);
    setSaved(null);
  }
  function addParticipant(client: Client) {
    if (values.participants.some((item) => item.client === client.id && item.role === newRole))
      return;
    update('participants', [
      ...values.participants,
      { client: client.id, client_name: client.display_name, role: newRole },
    ]);
    setParticipantPicker(false);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!values.participants.length) {
      setError(new Error('Dodaj co najmniej jednego uczestnika polisy.'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        ...values,
        participants: values.participants.map(({ client, role }) => ({ client, role })),
        ...(initial ? { version: initial.version } : {}),
      };
      const policy = initial
        ? await patch<Policy>(`/api/policies/${initial.id}/`, payload)
        : await post<Policy>('/api/policies/', payload);
      flushSync(() => {
        setDirty(false);
        setSaved(policy);
      });
      void navigate(`/policies/${policy.id}`);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <UnsavedGuard dirty={dirty} />
      <PageHeading
        title={initial ? 'Edytuj polisę' : 'Nowa polisa'}
        description="Wprowadź dane zawartej umowy. Pola z gwiazdką są wymagane."
        back={{
          to: initial ? `/policies/${initial.id}` : '/policies',
          label: initial ? 'Szczegóły polisy' : 'Polisy',
        }}
      />
      <form className="panel form-panel" onSubmit={submit}>
        {!!error && (
          <ErrorNotice
            error={error}
            onReload={initial ? () => setConfirmReload(true) : undefined}
          />
        )}
        <Warnings items={saved?.duplicate_warnings} />
        {saved && (
          <Alert kind="success">
            Polisa została zapisana.{' '}
            <Link to={`/policies/${saved.id}`}>Otwórz szczegóły polisy</Link>
          </Alert>
        )}
        <h2>Dane umowy</h2>
        <div className="form-grid">
          <FieldLabel label="Ubezpieczyciel" required>
            <input
              value={values.insurer}
              required
              onChange={(event) => update('insurer', event.target.value)}
            />
          </FieldLabel>
          <FieldLabel label="Numer polisy" required>
            <input
              value={values.number}
              required
              onChange={(event) => update('number', event.target.value)}
            />
          </FieldLabel>
          <FieldLabel label="Rodzaj ubezpieczenia" required className="span-2">
            <input
              placeholder="Np. komunikacyjne OC / AC"
              value={values.insurance_type}
              required
              onChange={(event) => update('insurance_type', event.target.value)}
            />
          </FieldLabel>
          <FieldLabel label="Początek ochrony" required>
            <input
              type="date"
              value={values.start_date}
              required
              onChange={(event) => update('start_date', event.target.value)}
            />
          </FieldLabel>
          <FieldLabel label="Koniec ochrony" required>
            <input
              type="date"
              min={values.start_date || undefined}
              value={values.end_date}
              required
              onChange={(event) => update('end_date', event.target.value)}
            />
          </FieldLabel>
          <FieldLabel label="Składka" hint="Pozostaw puste, jeśli składka jest nieznana.">
            <input
              inputMode="decimal"
              pattern="[0-9]+([.,][0-9]{1,2})?"
              value={values.premium ?? ''}
              onChange={(event) =>
                update(
                  'premium',
                  event.target.value === '' ? null : event.target.value.replace(',', '.'),
                )
              }
            />
          </FieldLabel>
          <FieldLabel label="Waluta">
            <select
              value={values.currency}
              onChange={(event) => update('currency', event.target.value)}
            >
              <option>PLN</option>
              <option>EUR</option>
              <option>USD</option>
              <option>GBP</option>
              <option>CHF</option>
            </select>
          </FieldLabel>
          <FieldLabel label="Opis przedmiotu ubezpieczenia" className="span-2">
            <textarea
              rows={3}
              value={values.subject}
              onChange={(event) => update('subject', event.target.value)}
            />
          </FieldLabel>
        </div>
        <div className="form-divider" />
        <div className="card-heading">
          <div>
            <h2>Uczestnicy polisy</h2>
            <p className="muted">
              Dodaj ubezpieczającego i co najmniej jednego ubezpieczonego. Jedna kartoteka może
              pełnić obie role.
            </p>
          </div>
          <Button type="button" variant="secondary" onClick={() => setParticipantPicker(true)}>
            <Plus size={16} />
            Dodaj uczestnika
          </Button>
        </div>
        {values.participants.length ? (
          <div className="participant-list">
            {values.participants.map((participant, index) => (
              <div className="participant-row" key={`${participant.client}-${participant.role}`}>
                <span>
                  <strong>{participant.client_name}</strong>
                  <small>
                    {participant.role === 'insured' ? 'Ubezpieczony' : 'Ubezpieczający'}
                  </small>
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    update(
                      'participants',
                      values.participants.filter((_, i) => i !== index),
                    )
                  }
                  aria-label={`Usuń uczestnika ${participant.client_name}, ${participant.role === 'insured' ? 'ubezpieczony' : 'ubezpieczający'}`}
                >
                  <X size={17} />
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            title="Dodaj uczestnika"
            description="Wybierz osobę lub organizację z istniejących kartotek."
          />
        )}
        <div className="form-divider" />
        <h2>Powiązane dokumenty</h2>
        <p className="muted">Możesz powiązać pliki wcześniej dodane do kancelarii.</p>
        <label className="search-field">
          <Search size={17} />
          <input
            aria-label="Szukaj dokumentów do polisy"
            placeholder="Szukaj dokumentów…"
            value={documentSearch}
            onChange={(event) => setDocumentSearch(event.target.value)}
          />
        </label>
        <div className="document-checks">
          {values.document_ids
            .filter((id) => !documents.data?.results.some((document) => document.id === id))
            .map((id) => (
              <label key={id}>
                <input
                  type="checkbox"
                  checked
                  onChange={() =>
                    update(
                      'document_ids',
                      values.document_ids.filter((value) => value !== id),
                    )
                  }
                />
                Dokument #{id} — powiązany
              </label>
            ))}
          {documents.data?.results.map((document) => (
            <label key={document.id}>
              <input
                type="checkbox"
                checked={values.document_ids.includes(document.id)}
                onChange={(event) =>
                  update(
                    'document_ids',
                    event.target.checked
                      ? [...values.document_ids, document.id]
                      : values.document_ids.filter((value) => value !== document.id),
                  )
                }
              />
              <FileText size={16} />
              <span>
                {document.original_name}
                <small>{document.client_name}</small>
              </span>
            </label>
          ))}
        </div>
        {documents.error && <ErrorNotice error={documents.error} />}
        <div className="form-actions">
          <Link className="button secondary" to={initial ? `/policies/${initial.id}` : '/policies'}>
            Anuluj
          </Link>
          <Button type="submit" disabled={busy || !!saved}>
            {busy ? 'Zapisywanie…' : 'Zapisz polisę'}
          </Button>
        </div>
      </form>
      {participantPicker && (
        <Modal title="Dodaj uczestnika polisy" onClose={() => setParticipantPicker(false)}>
          <FieldLabel label="Rola w polisie">
            <select
              value={newRole}
              onChange={(event) => setNewRole(event.target.value as Participant['role'])}
            >
              <option value="insured">Ubezpieczony</option>
              <option value="policyholder">Ubezpieczający</option>
            </select>
          </FieldLabel>
          <ClientPicker
            label="Szukaj uczestnika polisy"
            onSelect={addParticipant}
            exclude={values.participants
              .filter((item) => item.role === newRole)
              .map((item) => item.client)}
          />
        </Modal>
      )}
      {confirmReload && (
        <Modal title="Wczytać nowszą polisę?" onClose={() => setConfirmReload(false)}>
          <p>Twoje niezapisane zmiany zostaną odrzucone.</p>
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

export function PolicyDetailPage() {
  const { id } = useParams();
  const resource = useApi<Policy>(`/api/policies/${id}/`);
  const [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  if (resource.error) return <ErrorNotice error={resource.error} onReload={resource.reload} />;
  if (!resource.data) return <Loading />;
  const policy = resource.data;
  async function toggleArchive() {
    setBusy(true);
    try {
      await patch(`/api/policies/${id}/`, { version: policy.version, archived: !policy.archived });
      setConfirm(false);
      resource.reload();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="POLISA"
        title={policy.number}
        description={policy.insurer}
        back={{ to: '/policies', label: 'Polisy' }}
        actions={
          <Link className="button primary" to={`/policies/${id}/edit`}>
            <Pencil size={16} />
            Edytuj polisę
          </Link>
        }
      />
      {!!error && <ErrorNotice error={error} onReload={resource.reload} />}
      <Warnings items={policy.duplicate_warnings} />
      {policy.archived && <Alert kind="warning">Ta polisa jest zarchiwizowana.</Alert>}
      <div className="policy-layout">
        <section className="panel info-card">
          <div className="card-heading">
            <h2>
              <ShieldCheck size={19} />
              Dane ochrony
            </h2>
            <Badge tone={policy.coverage_status === 'active' ? 'green' : 'neutral'}>
              {
                { active: 'Aktywna', upcoming: 'Planowana', expired: 'Zakończona' }[
                  policy.coverage_status
                ]
              }
            </Badge>
          </div>
          <dl className="detail-list two-columns">
            <div>
              <dt>Rodzaj ubezpieczenia</dt>
              <dd>{policy.insurance_type}</dd>
            </div>
            <div>
              <dt>Składka</dt>
              <dd>{money(policy.premium, policy.currency)}</dd>
            </div>
            <div>
              <dt>Początek ochrony</dt>
              <dd>{date(policy.start_date)}</dd>
            </div>
            <div>
              <dt>Koniec ochrony</dt>
              <dd>{date(policy.end_date)}</dd>
            </div>
            <div className="span-2">
              <dt>Przedmiot ubezpieczenia</dt>
              <dd className="preserve-lines">{policy.subject || 'Nie podano'}</dd>
            </div>
          </dl>
          <Button variant="ghost" onClick={() => setConfirm(true)}>
            <Archive size={16} />
            {policy.archived ? 'Przywróć polisę' : 'Archiwizuj polisę'}
          </Button>
        </section>
        <section className="panel info-card">
          <h2>Uczestnicy</h2>
          <div className="participant-list">
            {policy.participants.map((item) => (
              <div className="participant-row" key={`${item.client}-${item.role}`}>
                <Link to={`/clients/${item.client}`}>
                  <strong>{item.client_name}</strong>
                  <small>{item.role === 'insured' ? 'Ubezpieczony' : 'Ubezpieczający'}</small>
                </Link>
              </div>
            ))}
          </div>
          <div className="form-divider" />
          <h2>Dokumenty</h2>
          {policy.document_ids.length ? (
            <ul className="link-list">
              {policy.document_ids.map((document) => (
                <li key={document}>
                  <Link to={`/documents/${document}`}>
                    <FileText size={16} />
                    Otwórz dokument #{document}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nie powiązano dokumentów.</p>
          )}
        </section>
      </div>
      {confirm && (
        <Modal
          title={policy.archived ? 'Przywróć polisę' : 'Archiwizuj polisę'}
          onClose={() => setConfirm(false)}
        >
          <p>
            {policy.archived
              ? 'Polisa powróci do bieżącej ewidencji.'
              : 'Polisa pozostanie w historii i archiwum. Nie będzie widoczna na liście bieżącej ewidencji.'}
          </p>
          <div className="form-actions">
            <Button variant="secondary" onClick={() => setConfirm(false)}>
              Anuluj
            </Button>
            <Button disabled={busy} onClick={() => void toggleArchive()}>
              {busy ? 'Zapisywanie…' : policy.archived ? 'Przywróć' : 'Archiwizuj'}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

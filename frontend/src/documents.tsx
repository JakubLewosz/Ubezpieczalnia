import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { flushSync } from 'react-dom';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FilePlus2,
  FileText,
  History,
  Info,
  Minus,
  Plus,
  RotateCcw,
  Save,
  Search,
  UploadCloud,
  X,
} from 'lucide-react';
import { api, dateTime, params, patch, post } from './api';
import { ClientPicker } from './clients';
import { PolicyPicker } from './policies';
import { useApi, useDebounce, useMounted } from './hooks';
import type {
  Client,
  DocumentRecord,
  Draft,
  Field,
  Job,
  Page,
  Policy,
  Review,
  Revision,
} from './types';
import {
  Alert,
  Badge,
  Button,
  DocumentStatus,
  DocumentTable,
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

export function DocumentsPage() {
  const [queryParams] = useSearchParams();
  const [search, setSearch] = useState(''),
    [page, setPage] = useState(1);
  const resource = useApi<Page<DocumentRecord>>(
    `/api/documents/?${params({ search: useDebounce(search), client: queryParams.get('client') ?? '', page })}`,
    5000,
  );
  return (
    <>
      <PageHeading
        eyebrow="DOKUMENTY KANCELARII"
        title="Dokumenty"
        description="Oryginały, lokalny odczyt i zatwierdzone wersje danych."
        actions={
          <Link className="button primary" to="/documents/new">
            <FilePlus2 size={17} />
            Dodaj dokument
          </Link>
        }
      />
      <section className="panel">
        <div className="filter-bar">
          <label className="search-field">
            <Search size={18} />
            <input
              aria-label="Szukaj dokumentów"
              placeholder="Nazwa dokumentu…"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </label>
          {queryParams.get('client') && (
            <Link className="button secondary" to="/documents">
              Wszyscy klienci
              <X size={15} />
            </Link>
          )}
          <span className="filter-caption">PDF, JPG, PNG · DOCX i XLSX jako załączniki</span>
        </div>
        {resource.error ? (
          <ErrorNotice error={resource.error} onReload={resource.reload} />
        ) : resource.data ? (
          <>
            <DocumentTable documents={resource.data.results} />
            <Pagination data={resource.data} page={page} onPage={setPage} />
          </>
        ) : (
          <Loading />
        )}
      </section>
    </>
  );
}
export function UploadPage() {
  const { id } = useParams();
  const clientResource = useApi<Client>(id ? `/api/clients/${id}/` : null);
  if (id && !clientResource.data)
    return clientResource.error ? <ErrorNotice error={clientResource.error} /> : <Loading />;
  return <UploadForm key={id ?? 'new'} initialClient={clientResource.data} />;
}
function UploadForm({ initialClient }: { initialClient: Client | null }) {
  const navigate = useNavigate();
  const mounted = useMounted();
  const [client, setClient] = useState(initialClient),
    [file, setFile] = useState<File | null>(null),
    [category, setCategory] = useState('Wniosek brokerski'),
    [policy, setPolicy] = useState<Policy | null>(null),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false),
    [dirty, setDirty] = useState(false);
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!client || !file) {
      setError(new Error('Wybierz klienta i plik dokumentu.'));
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError(new Error('Plik przekracza domyślny limit demonstracyjny 20 MB.'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set('client', String(client.id));
      form.set('category', category);
      if (policy) form.set('policy', String(policy.id));
      form.set('file', file);
      const document = await api<DocumentRecord>('/api/documents/', { method: 'POST', body: form });
      if (!mounted.current) return;
      flushSync(() => {
        setBusy(false);
        setDirty(false);
      });
      void navigate(`/documents/${document.id}`);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <UnsavedGuard dirty={dirty || !!busy} />
      <PageHeading
        title="Dodaj dokument"
        description="Oryginał zostanie zapisany w prywatnym magazynie kancelarii."
        back={{
          to: initialClient ? `/clients/${initialClient.id}` : '/documents',
          label: initialClient ? 'Kartoteka klienta' : 'Dokumenty',
        }}
      />
      <form onSubmit={upload} className="panel form-panel upload-form">
        <fieldset disabled={busy} className="form-lock">
          {!!error && <ErrorNotice error={error} />}
          <h2>Powiązanie z klientem</h2>
          {client ? (
            <div className="selected-client">
              <div className="avatar">
                <FileText size={20} />
              </div>
              <span>
                <strong>{client.display_name}</strong>
                <small>Główna kartoteka dokumentu</small>
              </span>
              {!initialClient && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setClient(null);
                    setPolicy(null);
                    setDirty(true);
                  }}
                  aria-label="Zmień klienta"
                >
                  <X size={17} />
                </Button>
              )}
            </div>
          ) : (
            <ClientPicker
              onSelect={(selected) => {
                setClient(selected);
                setDirty(true);
              }}
            />
          )}
          <div className="form-grid">
            <FieldLabel label="Kategoria" required>
              <select
                value={category}
                onChange={(event) => {
                  setCategory(event.target.value);
                  setDirty(true);
                }}
              >
                <option>Wniosek brokerski</option>
                <option>Polisa</option>
                <option>Aneks</option>
                <option>Załącznik</option>
                <option>Inny dokument</option>
              </select>
            </FieldLabel>
            {client && (
              <PolicyPicker
                key={client.id}
                clientId={client.id}
                selected={policy}
                onSelect={(value) => {
                  setPolicy(value);
                  setDirty(true);
                }}
              />
            )}
          </div>
          <div className="form-divider" />
          <h2>Plik dokumentu</h2>
          <label className={`upload-zone ${file ? 'has-file' : ''}`}>
            <UploadCloud size={34} strokeWidth={1.5} />
            <strong>{file ? file.name : 'Wybierz plik z komputera'}</strong>
            <span>
              {file
                ? `${(file.size / 1024 / 1024).toFixed(2)} MB · kliknij, aby zmienić`
                : 'PDF, JPEG, PNG, DOCX lub XLSX'}
            </span>
            <input
              type="file"
              aria-label="Plik dokumentu"
              accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx"
              required
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setDirty(true);
              }}
            />
          </label>
          <p className="muted">
            Limity demonstracyjne: 20 MB i 30 stron. PDF i obrazy mogą zostać odczytane lokalnie.
            DOCX i XLSX są przechowywane jako załączniki.
          </p>
          <Alert kind="info">
            Automatyczny profil obejmuje wniosek brokerski komunikacyjny. Odczyt wymaga sprawdzenia
            przez pracownika.
          </Alert>
          <div className="form-actions">
            <Link
              className="button secondary"
              to={initialClient ? `/clients/${initialClient.id}` : '/documents'}
            >
              Anuluj
            </Link>
            <Button type="submit" disabled={busy || !client || !file}>
              <UploadCloud size={17} />
              {busy ? 'Wgrywanie…' : 'Wgraj dokument'}
            </Button>
          </div>
        </fieldset>
      </form>
    </>
  );
}

export function ReviewPage() {
  const { id } = useParams();
  const documentResource = useApi<DocumentRecord>(`/api/documents/${id}/`, 4000);
  const reviewResource = useApi<Review>(`/api/documents/${id}/review/`, 4000);
  if (documentResource.error && !documentResource.data)
    return <ErrorNotice error={documentResource.error} onReload={documentResource.reload} />;
  if (reviewResource.error && !reviewResource.data)
    return <ErrorNotice error={reviewResource.error} onReload={reviewResource.reload} />;
  if (!documentResource.data || !reviewResource.data)
    return <Loading label="Wczytywanie dokumentu i odczytu…" />;
  return (
    <ReviewWorkspace
      key={id}
      document={documentResource.data}
      review={reviewResource.data}
      refresh={() => {
        documentResource.reload();
        reviewResource.reload();
      }}
      networkError={documentResource.error || reviewResource.error}
    />
  );
}
const groupLabels: Record<string, string> = {
  application: 'Wniosek',
  participants: 'Uczestnicy ubezpieczenia',
  vehicle: 'Pojazd',
  coverage: 'Okres i wartości ogólne',
  coverage_items: 'Wnioskowane elementy ochrony',
  previous: 'Poprzednie ubezpieczenie',
  payment: 'Płatność',
};
export const fieldKey = (field: Pick<Field, 'group' | 'group_id' | 'index' | 'code'>) =>
  `${field.group_id ?? `${field.group}:${field.index}`}:${field.code}`;
export function groupFields(fields: Field[]): [string, Field[]][] {
  const groups = new Map<string, Field[]>();
  fields.forEach((field) => {
    const group = groups.get(field.group) ?? [];
    group.push(field);
    groups.set(field.group, group);
  });
  const order = Object.keys(groupLabels);
  return [...groups].sort(
    ([a], [b]) =>
      (order.indexOf(a) < 0 ? 99 : order.indexOf(a)) -
      (order.indexOf(b) < 0 ? 99 : order.indexOf(b)),
  );
}
export function updateField(
  fields: Field[],
  key: string,
  change: Pick<Partial<Field>, 'value' | 'absent'>,
): Field[] {
  return fields.map((field) => (fieldKey(field) === key ? { ...field, ...change } : field));
}
export function ReviewWorkspace({
  document,
  review,
  refresh,
  networkError,
}: {
  document: DocumentRecord;
  review: Review;
  refresh: () => void;
  networkError: string;
}) {
  const mounted = useMounted();
  const [draft, setDraft] = useState<Draft | null>(review.draft),
    [fields, setFields] = useState<Field[]>(review.draft?.fields ?? []),
    [dirty, setDirty] = useState(false),
    [page, setPage] = useState(1),
    [zoom, setZoom] = useState(100),
    [previewError, setPreviewError] = useState(false),
    [busy, setBusy] = useState(''),
    [error, setError] = useState<unknown>(null),
    [notice, setNotice] = useState(''),
    [confirm, setConfirm] = useState<'approve' | 'reset' | 'reread' | 'reload' | 'manual' | null>(
      null,
    ),
    [warningAcknowledged, setWarningAcknowledged] = useState(false),
    [approvalNote, setApprovalNote] = useState(''),
    [removeGroup, setRemoveGroup] = useState<{ id: string; label: string } | null>(null),
    [selectedRevision, setSelectedRevision] = useState<Revision | null>(null);
  useEffect(() => {
    if (
      !dirty &&
      !busy &&
      !confirm &&
      review.draft &&
      review.draft.version >= (draft?.version ?? 0)
    ) {
      setDraft(review.draft);
      setFields(review.draft.fields);
    }
  }, [review.draft, dirty, busy, confirm, draft?.version]);
  useEffect(() => setPreviewError(false), [page, document.page_count, review.job?.status]);
  const job = review.job ?? document.latest_job;
  const running = job?.status === 'queued' || job?.status === 'running';
  const attachment = document.review_status === 'attachment';
  const unsupported = review.engine_result?.profile === null;
  const missing = fields.filter((field) => !field.value && !field.absent).length;
  const changed = fields.filter(
    (field) =>
      field.manual ||
      field.value !==
        draft?.fields.find((original) => fieldKey(original) === fieldKey(field))?.value ||
      field.absent !==
        draft?.fields.find((original) => fieldKey(original) === fieldKey(field))?.absent,
  ).length;
  function changeField(field: Field, change: Pick<Partial<Field>, 'value' | 'absent'>) {
    if (busy) return;
    setFields((current) => updateField(current, fieldKey(field), change));
    setWarningAcknowledged(false);
    setApprovalNote('');
    setDirty(true);
    setNotice('');
  }
  async function save() {
    if (!draft || busy) return;
    setBusy('save');
    setError(null);
    try {
      const result = await patch<Draft>(`/api/documents/${document.id}/review/`, {
        version: draft.version,
        fields,
      });
      if (!mounted.current) return;
      setDraft(result);
      setFields(result.fields);
      setDirty(false);
      setNotice('Wersja robocza została zapisana.');
      setWarningAcknowledged(false);
      setApprovalNote('');
      refresh();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy('');
    }
  }
  async function run(action: 'approve' | 'reset' | 'reread' | 'reload' | 'manual') {
    if (busy) return;
    setConfirm(null);
    setBusy(action);
    setError(null);
    setNotice('');
    try {
      if (action === 'manual') {
        const result = await post<Draft>(`/api/documents/${document.id}/review/manual/`);
        if (!mounted.current) return;
        setDraft(result);
        setFields(result.fields);
        setDirty(false);
        setNotice(
          'Utworzono ręczną wersję roboczą wniosku komunikacyjnego. Wynik silnika pozostaje bez zmian.',
        );
      } else if (action === 'reread') {
        await post<Job>(`/api/documents/${document.id}/extract/`);
        setNotice(
          'Zlecono lokalny odczyt. Aktualna wersja robocza i zatwierdzenia pozostają dostępne.',
        );
      } else if (action === 'reload') {
        const latest = await api<Review>(`/api/documents/${document.id}/review/`);
        if (!mounted.current) return;
        setDraft(latest.draft);
        setFields(latest.draft?.fields ?? []);
        setDirty(false);
        setNotice('Wczytano bieżącą wersję z serwera.');
      } else if (action === 'reset') {
        const result = await post<Draft>(`/api/documents/${document.id}/review/reset/`, {
          version: draft?.version ?? 0,
        });
        if (!mounted.current) return;
        setDraft(result);
        setFields(result.fields);
        setDirty(false);
        setNotice('Wczytano najnowszy wynik silnika do wersji roboczej.');
      } else {
        const result = await post<Revision>(`/api/documents/${document.id}/approve/`, {
          version: draft?.version,
          warning_digest: draft?.warning_digest,
          confirm_warnings: warningAcknowledged,
          note: approvalNote,
        });
        if (!mounted.current) return;
        setDraft((current) => (current ? { ...current, approved_version: current.version } : null));
        setNotice(`Zatwierdzono rewizję ${result.number}. Możesz pobrać jej eksport kontrolny.`);
      }
      setWarningAcknowledged(false);
      setApprovalNote('');
      refresh();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy('');
    }
  }
  async function mutateGroup(
    operation: { group: 'participants' | 'coverage_items' } | { group_id: string },
  ) {
    if (!draft || busy || dirty) return;
    setRemoveGroup(null);
    setBusy('group');
    setError(null);
    try {
      const result = await api<Draft>(`/api/documents/${document.id}/review/groups/`, {
        method: 'group' in operation ? 'POST' : 'DELETE',
        body: JSON.stringify({ version: draft.version, ...operation }),
      });
      if (!mounted.current) return;
      setDraft(result);
      setFields(result.fields);
      setDirty(false);
      setWarningAcknowledged(false);
      setApprovalNote('');
      setNotice('Zapisano zmianę struktury wersji roboczej.');
      refresh();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy('');
    }
  }
  async function openRevision(revision: Revision) {
    setBusy('revision');
    setError(null);
    try {
      setSelectedRevision(await api<Revision>(`/api/revisions/${revision.id}/`));
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy('');
    }
  }
  const revisions = [...review.revisions].sort((a, b) => b.number - a.number);
  const latestRevision = revisions[0];
  return (
    <>
      <UnsavedGuard dirty={dirty || !!busy} />
      <PageHeading
        title={document.original_name}
        eyebrow="WERYFIKACJA DOKUMENTU"
        back={{ to: `/clients/${document.client}`, label: document.client_name }}
        actions={
          <>
            <a className="button secondary" href={`/api/documents/${document.id}/original/`}>
              <Download size={16} />
              Oryginał
            </a>
            {latestRevision && (
              <a className="button primary" href={`/api/revisions/${latestRevision.id}/export/`}>
                <Download size={16} />
                Eksport XLSX · rew. {latestRevision.number}
              </a>
            )}
          </>
        }
      />
      <div className="review-summary">
        <DocumentStatus document={document} />
        <span>
          {document.category} · {document.author_name} · {dateTime(document.created_at)}
        </span>
        <span className="push-right">
          <span className="status-dot" />
          Odczyt lokalny
        </span>
      </div>
      {document.mail_source && (
        <Alert kind="info">
          Dokument pochodzi z załącznika wiadomości w skrzynce.{' '}
          <Link to={`/mailbox/${document.mail_source.message}`}>Wróć do obsługi wiadomości</Link>
        </Alert>
      )}
      <Warnings items={document.duplicate_warnings} />
      {networkError && <ErrorNotice error={networkError} onReload={refresh} />}
      <Warnings items={review.engine_result?.warnings} />
      {!!error && <ErrorNotice error={error} onReload={() => setConfirm('reload')} />}{' '}
      {notice && <Alert kind="success">{notice}</Alert>}
      {job?.status === 'failed' && (
        <Alert>Odczyt nie powiódł się. {job.error || 'Sprawdź dokument i ponów odczyt.'}</Alert>
      )}
      {running && (
        <Alert kind="info">
          {job.status === 'queued'
            ? 'Dokument czeka na lokalny odczyt.'
            : 'Trwa lokalny odczyt dokumentu.'}{' '}
          Stan zaktualizuje się automatycznie. Możesz wrócić do kartoteki.
        </Alert>
      )}
      <div className="review-layout">
        <section className="preview-panel panel" aria-label="Podgląd dokumentu">
          <div className="preview-toolbar">
            <div className="toolbar-group">
              <Button
                variant="ghost"
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                disabled={page <= 1}
                aria-label="Poprzednia strona dokumentu"
              >
                <ChevronLeft size={17} />
              </Button>
              <label>
                Strona{' '}
                <select
                  aria-label="Strona dokumentu"
                  value={page}
                  onChange={(event) => setPage(Number(event.target.value))}
                >
                  {Array.from({ length: Math.max(1, document.page_count) }, (_, index) => (
                    <option key={index + 1}>{index + 1}</option>
                  ))}
                </select>{' '}
                z {document.page_count || '—'}
              </label>
              <Button
                variant="ghost"
                onClick={() => setPage((value) => Math.min(document.page_count, value + 1))}
                disabled={page >= document.page_count}
                aria-label="Następna strona dokumentu"
              >
                <ChevronRight size={17} />
              </Button>
            </div>
            <div className="toolbar-group">
              <Button
                variant="ghost"
                disabled={zoom <= 50}
                onClick={() => setZoom((value) => value - 25)}
                aria-label="Pomniejsz"
              >
                <Minus size={16} />
              </Button>
              <span>{zoom}%</span>
              <Button
                variant="ghost"
                disabled={zoom >= 200}
                onClick={() => setZoom((value) => value + 25)}
                aria-label="Powiększ"
              >
                <Plus size={16} />
              </Button>
            </div>
          </div>
          <div className="preview-canvas">
            {attachment ? (
              <Empty
                title="Załącznik biurowy"
                description="DOCX i XLSX są dostępne do pobrania w oryginalnym formacie."
                action={
                  <a className="button secondary" href={`/api/documents/${document.id}/original/`}>
                    <Download size={16} />
                    Pobierz oryginał
                  </a>
                }
              />
            ) : document.page_count &&
              (review.engine_result || draft?.origin === 'manual' || job?.status === 'failed') &&
              !previewError ? (
              <img
                className="document-preview"
                src={`/api/documents/${document.id}/pages/${page}/?result=${review.engine_result?.id ?? 0}`}
                alt={`Podgląd dokumentu, strona ${page}`}
                style={{ width: `${zoom}%`, maxWidth: 'none' }}
                onError={() => setPreviewError(true)}
              />
            ) : (
              <Empty
                title={running ? 'Przygotowywanie podglądu' : 'Podgląd nie jest jeszcze dostępny'}
                description={
                  running
                    ? 'Strony pojawią się po zakończeniu zadania.'
                    : 'Uruchom odczyt lub pobierz oryginał dokumentu.'
                }
              />
            )}
          </div>
          <div className="preview-footer">
            <FileText size={14} />
            Oryginał pozostaje niezmieniony
            {review.engine_result?.pages.find((item) => item.number === page) && (
              <span>
                Strona:{' '}
                {review.engine_result.pages.find((item) => item.number === page)?.method === 'ocr'
                  ? 'lokalny OCR'
                  : 'warstwa tekstowa'}
              </span>
            )}
          </div>
        </section>
        <section className="review-form panel" aria-label="Formularz weryfikacji">
          <div className="review-form-header">
            <div>
              <h2>Dane z dokumentu</h2>
              <p>Sprawdź wartości ze źródłem przed zatwierdzeniem.</p>
            </div>
            <Badge tone={dirty ? 'amber' : 'neutral'}>
              {dirty
                ? 'Niezapisane zmiany'
                : draft
                  ? `Wersja robocza ${draft.version}`
                  : 'Brak odczytu'}
            </Badge>
          </div>
          {draft && (
            <div className="review-counters">
              <span>
                <Info size={15} />
                {missing} pól do uzupełnienia lub oznaczenia
              </span>
              <span>
                <PencilMark />
                {changed} korekt ręcznych
              </span>
            </div>
          )}
          {attachment ? (
            <div className="padded">
              <Alert kind="info">
                Załączniki DOCX i XLSX nie podlegają automatycznemu odczytowi ani eksportowi
                odczytu.
              </Alert>
            </div>
          ) : unsupported && !draft ? (
            <Empty
              title="Brak profilu automatycznego odczytu"
              description="Ten dokument nie został rozpoznany jako wniosek brokerski komunikacyjny. Oryginał pozostaje dostępny."
              action={
                <Button
                  disabled={!!busy || running}
                  variant="secondary"
                  onClick={() => setConfirm('manual')}
                >
                  Uzupełnij ręcznie — wniosek komunikacyjny
                </Button>
              }
            />
          ) : !draft ? (
            <Empty
              title={running ? 'Czekamy na odczyt' : 'Rozpocznij odczyt dokumentu'}
              description="Pilot rozpoznaje wybrane dane wniosku brokerskiego komunikacyjnego."
              action={
                !running ? (
                  <>
                    <Button disabled={!!busy} onClick={() => void run('reread')}>
                      <RotateCcw size={16} />
                      Uruchom odczyt
                    </Button>
                    {job?.status === 'failed' && (
                      <Button
                        variant="secondary"
                        disabled={!!busy}
                        onClick={() => setConfirm('manual')}
                      >
                        Uzupełnij ręcznie — wniosek komunikacyjny
                      </Button>
                    )}
                  </>
                ) : undefined
              }
            />
          ) : (
            <div className="extraction-groups">
              {draft.origin === 'manual' && (
                <Alert kind="info">
                  Ręczne uzupełnienie profilu komunikacyjnego. Puste pola i dodane grupy nie są
                  wynikiem OCR; autor i czas zmian są zapisywane.
                </Alert>
              )}
              {!!draft.warnings?.length && (
                <Alert kind="warning">
                  <strong>Walidacja zapisanej wersji {draft.version}</strong>
                  {dirty && <p>Po zapisaniu zmian serwer ponownie sprawdzi ostrzeżenia.</p>}
                  <ul>
                    {draft.warnings.map((warning) => (
                      <li key={warning.id}>
                        {warning.message}
                        {warning.requires_note ? ' Wymaga notatki przy zatwierdzeniu.' : ''}
                      </li>
                    ))}
                  </ul>
                </Alert>
              )}
              {groupFields(fields).map(([group, items]) => {
                const repeated = group === 'participants' || group === 'coverage_items';
                const groups = new Map<string, Field[]>();
                items.forEach((field) => {
                  const key = field.group_id ?? `${group}:${field.index}`;
                  groups.set(key, [...(groups.get(key) ?? []), field]);
                });
                return (
                  <section className="extraction-group" key={group}>
                    <h3>
                      <span className="group-index">
                        {groupFields(fields).findIndex(([name]) => name === group) + 1}
                      </span>
                      {groupLabels[group] ?? group}
                    </h3>
                    {repeated
                      ? [...groups].map(([identity, groupItems]) => (
                          <div className="repeat-group" key={identity}>
                            <div className="card-heading">
                              <h4>
                                {group === 'participants' ? 'Uczestnik' : 'Element ochrony'}{' '}
                                {groupItems[0]!.index + 1}
                              </h4>
                              {groupItems[0]?.group_id && (
                                <Button
                                  variant="ghost"
                                  disabled={dirty || !!busy}
                                  onClick={() =>
                                    setRemoveGroup({
                                      id: identity,
                                      label: `${group === 'participants' ? 'uczestnika' : 'element ochrony'} ${groupItems[0]!.index + 1}`,
                                    })
                                  }
                                >
                                  Usuń {group === 'participants' ? 'uczestnika' : 'element'}
                                </Button>
                              )}
                            </div>
                            {groupItems.map((field) => (
                              <ReviewField
                                key={fieldKey(field)}
                                field={field}
                                disabled={!!busy}
                                original={draft.fields.find(
                                  (original) => fieldKey(original) === fieldKey(field),
                                )}
                                onChange={(change) => changeField(field, change)}
                                onSource={() => setPage(field.page ?? 1)}
                              />
                            ))}
                          </div>
                        ))
                      : items.map((field) => (
                          <ReviewField
                            key={fieldKey(field)}
                            field={field}
                            disabled={!!busy}
                            original={draft.fields.find(
                              (original) => fieldKey(original) === fieldKey(field),
                            )}
                            onChange={(change) => changeField(field, change)}
                            onSource={() => setPage(field.page ?? 1)}
                          />
                        ))}
                  </section>
                );
              })}
              <div className="group-actions">
                <Button
                  variant="secondary"
                  disabled={dirty || !!busy}
                  onClick={() => void mutateGroup({ group: 'participants' })}
                >
                  <Plus size={16} />
                  Dodaj uczestnika ręcznie
                </Button>
                <Button
                  variant="secondary"
                  disabled={dirty || !!busy}
                  onClick={() => void mutateGroup({ group: 'coverage_items' })}
                >
                  <Plus size={16} />
                  Dodaj element ochrony ręcznie
                </Button>
                {dirty && <small>Zapisz bieżące pola przed dodaniem lub usunięciem grupy.</small>}
              </div>
            </div>
          )}
          {draft && (
            <div className="review-actions">
              <span>
                {dirty
                  ? 'Zapisz zmiany przed zatwierdzeniem.'
                  : `Zapisano ${dateTime(draft.updated_at)}`}
              </span>
              <div>
                <Button variant="secondary" disabled={!dirty || !!busy} onClick={() => void save()}>
                  <Save size={16} />
                  {busy === 'save' ? 'Zapisywanie…' : 'Zapisz wersję roboczą'}
                </Button>
                <Button
                  disabled={dirty || !!busy || running || draft.approved_version === draft.version}
                  onClick={() => {
                    setWarningAcknowledged(false);
                    setApprovalNote('');
                    setConfirm('approve');
                  }}
                >
                  <Check size={17} />
                  Zatwierdź wersję
                </Button>
              </div>
            </div>
          )}
        </section>
      </div>
      <div className="review-bottom">
        <section className="panel info-card revision-card">
          <div className="card-heading">
            <h2>
              <History size={18} />
              Zatwierdzone rewizje
            </h2>
            <Badge>{revisions.length}</Badge>
          </div>
          <p className="muted">
            Eksport kontrolny — układ demonstracyjny, do uzgodnienia. Profil review_export_v0.
          </p>
          {revisions.length ? (
            <div className="revision-list">
              {revisions.map((revision) => (
                <div className="revision-row" key={revision.id}>
                  <span className="revision-mark">
                    <CheckCircle2 size={19} />
                  </span>
                  <span>
                    <strong>Rewizja {revision.number}</strong>
                    <small>
                      {revision.author_name} · {dateTime(revision.created_at)}
                    </small>
                  </span>
                  <Button
                    variant="ghost"
                    disabled={!!busy}
                    onClick={() => void openRevision(revision)}
                  >
                    Podejrzyj
                  </Button>
                  <a className="button secondary" href={`/api/revisions/${revision.id}/export/`}>
                    <Download size={15} />
                    XLSX <span className="sr-only">rewizji {revision.number}</span>
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Eksport będzie dostępny po pierwszym zatwierdzeniu odczytu.</p>
          )}
        </section>
        {!attachment && (
          <section className="panel info-card">
            <h2>Ponowny odczyt</h2>
            <p className="muted">
              Nowy wynik silnika pozostaje oddzielony od poprawek pracownika i zatwierdzonych
              rewizji.
            </p>
            <div className="stack-actions">
              <Button
                variant="secondary"
                disabled={running || !!busy || dirty}
                onClick={() => setConfirm('reread')}
              >
                <RotateCcw size={16} />
                Odczytaj ponownie
              </Button>
              {draft && (
                <Button
                  variant="ghost"
                  disabled={running || !!busy || !review.engine_result?.profile}
                  onClick={() => setConfirm('reset')}
                >
                  Zastąp roboczą wynikiem silnika
                </Button>
              )}
            </div>
          </section>
        )}
      </div>
      {confirm && (
        <Modal
          title={
            {
              approve: 'Zatwierdź wersję odczytu',
              manual: 'Uzupełnij ręcznie wniosek komunikacyjny',
              reset: 'Zastąp wersję roboczą',
              reread: 'Uruchom ponowny odczyt',
              reload: 'Wczytaj bieżącą wersję',
            }[confirm]
          }
          onClose={() => setConfirm(null)}
        >
          <p>
            {
              {
                manual:
                  'Świadomie wybierasz ograniczony profil wniosku komunikacyjnego. Otrzymasz ręczny szkic i dostępny podgląd. Nie zmienisz wyniku rozpoznania ani nie utworzysz kartoteki klienta lub polisy.',
                approve:
                  'Zatwierdzenie zapisze niezmienną rewizję z Twoim nazwiskiem i datą. Późniejsza korekta będzie wymagała kolejnej rewizji. Dane kartoteki i polisy nie zostaną zmienione.',
                reset:
                  'Aktualne poprawki wersji roboczej i niezapisane zmiany zostaną zastąpione najnowszym wynikiem silnika. Zatwierdzone rewizje pozostaną dostępne.',
                reread:
                  'Dokument zostanie ponownie odczytany lokalnie. Zapisane poprawki i zatwierdzone rewizje pozostaną zachowane.',
                reload:
                  'Niezapisane zmiany zostaną odrzucone. Przed wczytaniem możesz je skopiować i zachować.',
              }[confirm]
            }
          </p>
          {confirm === 'approve' && !!draft?.warnings?.length && (
            <>
              <Alert kind="warning">
                <strong>Ostrzeżenia wersji {draft.version}</strong>
                <ul>
                  {draft.warnings.map((warning) => (
                    <li key={warning.id}>{warning.message}</li>
                  ))}
                </ul>
              </Alert>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={warningAcknowledged}
                  onChange={(event) => setWarningAcknowledged(event.target.checked)}
                />
                Zapoznałem się z aktualnymi ostrzeżeniami i świadomie zatwierdzam tę wersję.
              </label>
              <FieldLabel
                label="Notatka do zatwierdzenia"
                required={draft.warnings.some((item) => item.requires_note)}
                hint="Przy istotnej sprzeczności wyjaśnij decyzję. Nie uzupełniaj danych domysłem."
              >
                <textarea
                  value={approvalNote}
                  rows={3}
                  maxLength={2000}
                  onChange={(event) => setApprovalNote(event.target.value)}
                />
              </FieldLabel>
            </>
          )}
          <div className="form-actions">
            <Button variant="secondary" onClick={() => setConfirm(null)}>
              Anuluj
            </Button>
            <Button
              disabled={
                !!busy ||
                (confirm === 'approve' &&
                  !!draft?.warnings?.length &&
                  (!warningAcknowledged ||
                    (draft.warnings.some((item) => item.requires_note) &&
                      approvalNote.trim().length < 3)))
              }
              variant={confirm === 'reset' ? 'danger' : 'primary'}
              onClick={() => void run(confirm)}
            >
              {confirm === 'approve'
                ? 'Potwierdź zatwierdzenie'
                : confirm === 'reset'
                  ? 'Zastąp wersję roboczą'
                  : confirm === 'manual'
                    ? 'Utwórz ręczny szkic'
                    : confirm === 'reload'
                      ? 'Wczytaj aktualne dane'
                      : 'Zleć ponowny odczyt'}
            </Button>
          </div>
        </Modal>
      )}
      {removeGroup && (
        <Modal title={`Usuń ${removeGroup.label}`} onClose={() => setRemoveGroup(null)}>
          <p>
            Grupa zostanie usunięta z wersji roboczej. Pozostałe grupy zachowają tożsamość, a
            historyczne rewizje pozostaną niezmienione.
          </p>
          <div className="form-actions">
            <Button variant="secondary" onClick={() => setRemoveGroup(null)}>
              Anuluj
            </Button>
            <Button variant="danger" onClick={() => void mutateGroup({ group_id: removeGroup.id })}>
              Potwierdź usunięcie grupy
            </Button>
          </div>
        </Modal>
      )}
      {selectedRevision && (
        <Modal
          title={`Zatwierdzona rewizja ${selectedRevision.number}`}
          onClose={() => setSelectedRevision(null)}
        >
          <p className="muted">
            {selectedRevision.author_name} · {dateTime(selectedRevision.created_at)} · wersja tylko
            do odczytu
          </p>
          <div className="snapshot-fields">
            {selectedRevision.fields?.map((field) => (
              <div key={fieldKey(field)}>
                <span>
                  {groupLabels[field.group] ?? field.group} / {field.index + 1} · {field.label}
                </span>
                <strong>
                  {field.absent ? 'Brak w dokumencie' : (field.value ?? 'Nie podano')} {field.unit}
                </strong>
                {field.manual && <Badge>Korekta ręczna</Badge>}
              </div>
            ))}
          </div>
          <div className="form-actions">
            <a className="button primary" href={`/api/revisions/${selectedRevision.id}/export/`}>
              <Download size={16} />
              Pobierz XLSX tej rewizji
            </a>
          </div>
        </Modal>
      )}
    </>
  );
}
function PencilMark() {
  return <span aria-hidden="true">✎</span>;
}
export function ReviewField({
  field,
  original,
  onChange,
  onSource,
  disabled = false,
}: {
  disabled?: boolean;
  field: Field;
  original?: Field;
  onChange: (change: Pick<Partial<Field>, 'value' | 'absent'>) => void;
  onSource: () => void;
}) {
  const locallyChanged =
    original && (field.value !== original.value || field.absent !== original.absent);
  const manual = field.manual || locallyChanged;
  const id = `field-${fieldKey(field).replace(/:/g, '-')}`;
  const missing = !field.value && !field.absent;
  return (
    <div className={`review-field ${missing ? 'missing' : ''}`}>
      <div className="field-title">
        <label htmlFor={id}>
          {field.label}
          {field.group === 'participants' && <small> · osoba {field.index + 1}</small>}
          {field.unit && <small> ({field.unit})</small>}
        </label>
        {manual ? (
          <Badge>Korekta ręczna</Badge>
        ) : missing ? (
          <Badge tone="amber">Puste pole</Badge>
        ) : null}
      </div>
      {field.code === 'role' ? (
        <select
          id={id}
          value={field.value ?? ''}
          disabled={disabled || field.absent}
          onChange={(event) => onChange({ value: event.target.value || null, absent: false })}
        >
          <option value="">Wybierz rolę</option>
          <option value="policyholder">Ubezpieczający</option>
          <option value="insured">Ubezpieczony</option>
          <option value="owner">Właściciel</option>
          <option value="policyholder,insured">Ubezpieczający i ubezpieczony</option>
          <option value="policyholder,owner">Ubezpieczający i właściciel</option>
          <option value="insured,owner">Ubezpieczony i właściciel</option>
          <option value="policyholder,insured,owner">
            Ubezpieczający, ubezpieczony i właściciel
          </option>
          {field.value &&
            ![
              'policyholder',
              'insured',
              'owner',
              'policyholder,insured',
              'policyholder,owner',
              'insured,owner',
              'policyholder,insured,owner',
            ].includes(field.value) && <option value={field.value}>{field.value}</option>}
        </select>
      ) : (
        <input
          id={id}
          type="text"
          inputMode={
            field.type === 'decimal' ? 'decimal' : field.type === 'integer' ? 'numeric' : undefined
          }
          value={field.value ?? ''}
          disabled={disabled || field.absent}
          placeholder={
            field.absent
              ? 'Brak w dokumencie'
              : field.type === 'date'
                ? 'RRRR-MM-DD'
                : 'Uzupełnij lub oznacz brak'
          }
          onChange={(event) =>
            onChange({
              value: event.target.value === '' ? null : event.target.value,
              absent: false,
            })
          }
        />
      )}
      <div className="field-metadata">
        <label className="checkbox-label">
          <input
            type="checkbox"
            disabled={disabled}
            checked={field.absent}
            onChange={(event) =>
              onChange({
                absent: event.target.checked,
                ...(event.target.checked ? { value: null } : {}),
              })
            }
          />
          Brak w dokumencie
        </label>
        {!manual && field.page && field.source ? (
          <button type="button" className="source-link" onClick={onSource} title={field.source}>
            Źródło · str. {field.page}
            <ChevronRight size={12} />
          </button>
        ) : (
          <span>{manual ? 'Wartość wprowadzona ręcznie' : 'Bez wskazanego źródła'}</span>
        )}
      </div>
      {!manual && field.source && <p className="source-text">„{field.source}”</p>}
      {field.warnings?.length > 0 && (
        <p className="field-warning">
          {locallyChanged ? 'Ostrzeżenie poprzednio zapisanej wartości: ' : ''}
          {field.warnings.join(' · ')}
        </p>
      )}
      {field.manual && field.updated_at && (
        <p className="field-audit">
          {field.updated_by ?? 'Pracownik'} · {dateTime(field.updated_at)}
        </p>
      )}
    </div>
  );
}

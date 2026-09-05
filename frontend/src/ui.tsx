import { useCallback, useEffect, useRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link, useBeforeUnload, useBlocker } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileText,
  LoaderCircle,
  X,
} from 'lucide-react';
import { ApiError, date, dateTime } from './api';
import type { DocumentRecord, Page, Policy } from './types';

export function Button({
  children,
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  children: ReactNode;
}) {
  return (
    <button className={`button ${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}
export function Alert({
  children,
  kind = 'error',
}: {
  children: ReactNode;
  kind?: 'error' | 'warning' | 'success' | 'info';
}) {
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`alert ${kind}`}>
      {kind === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
      <div>{children}</div>
    </div>
  );
}
export function ErrorNotice({ error, onReload }: { error: unknown; onReload?: () => void }) {
  return (
    <Alert>
      {error instanceof ApiError && error.status === 409
        ? 'Konflikt wersji. Ktoś zapisał nowsze dane. Twoje zmiany pozostają w formularzu; skopiuj je przed wczytaniem aktualnej wersji. '
        : ''}
      {error instanceof Error ? error.message : String(error)}
      {onReload && (
        <Button variant="ghost" onClick={onReload}>
          Wczytaj ponownie
        </Button>
      )}
    </Alert>
  );
}
export function Loading({ label = 'Wczytywanie danych…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} />
      {label}
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <FileText size={27} strokeWidth={1.4} />
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
  back,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  back?: { to: string; label: string };
}) {
  return (
    <>
      <div className="page-heading">
        {back && (
          <Link to={back.to} className="back">
            <ArrowLeft size={15} />
            {back.label}
          </Link>
        )}
        <div className="heading-row">
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            <h1>{title}</h1>
            {description && <p>{description}</p>}
          </div>
          {actions && <div className="heading-actions">{actions}</div>}
        </div>
      </div>
    </>
  );
}
export function FieldLabel({
  label,
  children,
  hint,
  required = false,
  className = '',
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  required?: boolean;
  className?: string;
}) {
  return (
    <label className={`field ${className}`}>
      <span>
        {label}
        {required && (
          <span className="required" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Warnings({ items }: { items?: string[] }) {
  return items?.length ? (
    <Alert kind="warning">
      <ul>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </Alert>
  ) : null;
}
export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'green' | 'amber' | 'red' | 'blue';
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function DocumentStatus({ document }: { document: DocumentRecord }) {
  const job = document.latest_job;
  if (job?.status === 'failed') return <Badge tone="red">Błąd odczytu</Badge>;
  if (job?.status === 'running') return <Badge tone="blue">Odczyt w toku</Badge>;
  if (job?.status === 'queued') return <Badge tone="blue">W kolejce</Badge>;
  const statuses = {
    pending: ['Oczekuje na odczyt', 'neutral'],
    draft: ['Do sprawdzenia', 'amber'],
    approved: ['Zatwierdzony', 'green'],
    unsupported: ['Brak profilu', 'neutral'],
    attachment: ['Załącznik', 'neutral'],
  } as const;
  const [label, tone] = statuses[document.review_status] ?? statuses.pending;
  return <Badge tone={tone}>{label}</Badge>;
}
export function DocumentTable({
  documents,
  compact = false,
}: {
  documents: DocumentRecord[];
  compact?: boolean;
}) {
  return documents.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Dokument</th>
            {!compact && <th>Klient</th>}
            <th>Status</th>
            <th>Dodano</th>
            <th>
              <span className="sr-only">Otwórz</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((item) => (
            <tr key={item.id}>
              <td>
                <Link className="row-link file-name" to={`/documents/${item.id}`}>
                  <FileText size={18} />
                  <span>
                    {item.original_name}
                    <small>
                      {item.category || 'Dokument'} · {Math.ceil(item.size / 1024)} KB
                    </small>
                  </span>
                </Link>
              </td>
              {!compact && (
                <td>
                  <Link to={`/clients/${item.client}`}>{item.client_name}</Link>
                </td>
              )}
              <td>
                <DocumentStatus document={item} />
              </td>
              <td className="nowrap muted">{date(item.created_at)}</td>
              <td>
                <Link
                  to={`/documents/${item.id}`}
                  className="icon-link"
                  aria-label={`Otwórz ${item.original_name}`}
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
    <Empty title="Brak dokumentów" description="Dodane pliki pojawią się w tym miejscu." />
  );
}
export function PolicyTable({ policies }: { policies: Policy[] }) {
  const labels = { upcoming: 'Planowana', active: 'Aktywna', expired: 'Zakończona' };
  return policies.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Numer / ubezpieczyciel</th>
            <th>Rodzaj</th>
            <th>Koniec ochrony</th>
            <th>Status</th>
            <th>
              <span className="sr-only">Otwórz</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {policies.map((item) => (
            <tr key={item.id}>
              <td>
                <Link className="row-link" to={`/policies/${item.id}`}>
                  {item.number}
                  <small>{item.insurer}</small>
                </Link>
              </td>
              <td>{item.insurance_type}</td>
              <td className="nowrap">{date(item.end_date)}</td>
              <td>
                <Badge
                  tone={
                    item.coverage_status === 'active'
                      ? 'green'
                      : item.coverage_status === 'expired'
                        ? 'neutral'
                        : 'blue'
                  }
                >
                  {item.archived ? 'Zarchiwizowana' : labels[item.coverage_status]}
                </Badge>
              </td>
              <td>
                <Link
                  className="icon-link"
                  to={`/policies/${item.id}`}
                  aria-label={`Otwórz polisę ${item.number}`}
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
      title="Brak polis"
      description="Polisy są wprowadzane ręcznie na podstawie zawartej umowy."
    />
  );
}
export function Pagination({
  data,
  page,
  onPage,
}: {
  data: Pick<Page<unknown>, 'count' | 'next' | 'previous'>;
  page: number;
  onPage: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {data.count === 0
          ? 'Brak wyników'
          : `${(page - 1) * 20 + 1}–${Math.min(page * 20, data.count)} z ${data.count}`}
      </span>
      <div>
        <Button
          variant="secondary"
          disabled={!data.previous}
          onClick={() => onPage(page - 1)}
          aria-label="Poprzednia strona"
        >
          <ChevronLeft size={16} />
        </Button>
        <span>Strona {page}</span>
        <Button
          variant="secondary"
          disabled={!data.next}
          onClick={() => onPage(page + 1)}
          aria-label="Następna strona"
        >
          <ChevronRight size={16} />
        </Button>
      </div>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = ref.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="modal-heading">
        <h2>{title}</h2>
        <Button variant="ghost" onClick={onClose} aria-label="Zamknij">
          <X size={20} />
        </Button>
      </div>
      {children}
    </dialog>
  );
}
const dirtyForms = new Set<symbol>();
export function hasUnsavedChanges(): boolean {
  return dirtyForms.size > 0;
}
export function UnsavedGuard({ dirty }: { dirty: boolean }) {
  const formId = useRef(Symbol('form'));
  useEffect(() => {
    const id = formId.current;
    if (dirty) dirtyForms.add(id);
    else dirtyForms.delete(id);
    return () => {
      dirtyForms.delete(id);
    };
  }, [dirty]);
  const blocker = useBlocker(dirty);
  useBeforeUnload(
    useCallback(
      (event: BeforeUnloadEvent) => {
        if (dirty) {
          event.preventDefault();
          event.returnValue = '';
        }
      },
      [dirty],
    ),
  );
  return blocker.state === 'blocked' ? (
    <Modal title="Masz niezapisane zmiany" onClose={() => blocker.reset()}>
      <p>Opuszczenie tej strony spowoduje utratę zmian w formularzu.</p>
      <div className="form-actions">
        <Button variant="secondary" onClick={() => blocker.reset()}>
          Zostań w formularzu
        </Button>
        <Button variant="danger" onClick={() => blocker.proceed()}>
          Odrzuć zmiany i wyjdź
        </Button>
      </div>
    </Modal>
  ) : null;
}
export function MetaDate({ value }: { value: string }) {
  return <time dateTime={value}>{dateTime(value)}</time>;
}

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  role: 'ADMIN' | 'EMPLOYEE';
}
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface Client {
  id: number;
  kind: 'person' | 'organization';
  first_name: string;
  last_name: string;
  organization_name: string;
  display_name: string;
  pesel: string;
  nip: string;
  email: string;
  phone: string;
  address: string;
  note: string;
  archived: boolean;
  version: number;
  created_at: string;
  duplicate_warnings: string[];
}
export interface Participant {
  client: number;
  role: 'policyholder' | 'insured';
  client_name: string;
}
export interface Policy {
  id: number;
  insurer: string;
  number: string;
  insurance_type: string;
  start_date: string;
  end_date: string;
  premium: string | null;
  currency: string;
  subject: string;
  archived: boolean;
  version: number;
  participants: Participant[];
  document_ids: number[];
  coverage_status: 'upcoming' | 'active' | 'expired';
  duplicate_warnings: string[];
}
export interface Job {
  id: number;
  document: number;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  error: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}
export interface DocumentRecord {
  mail_source?: { message: number; attachment: number; part_key: string } | null;
  id: number;
  client: number;
  client_name: string;
  policy: number | null;
  original_name: string;
  mime_type: string;
  size: number;
  checksum: string;
  category: string;
  page_count: number;
  created_at: string;
  author_name: string;
  duplicate_warnings: string[];
  latest_job: Job | null;
  review_status: 'pending' | 'draft' | 'approved' | 'unsupported' | 'attachment';
}
export interface Field {
  code: string;
  label: string;
  value: string | null;
  type: 'text' | 'date' | 'decimal' | 'integer';
  unit: string;
  group: string;
  group_id?: string;
  index: number;
  page: number | null;
  source: string;
  method: string;
  warnings: string[];
  manual: boolean;
  absent: boolean;
  updated_by?: string;
  updated_at?: string;
}
export interface EngineResult {
  id: number;
  profile: string | null;
  fields: Field[];
  warnings: string[];
  pages: { number: number; method: 'text' | 'ocr' }[];
}
export interface DraftWarning {
  id: string;
  field: string | null;
  code: string;
  message: string;
  requires_note: boolean;
}
export interface Draft {
  profile?: string;
  origin?: 'engine' | 'manual';
  warnings?: DraftWarning[];
  warning_digest?: string;
  id: number;
  version: number;
  fields: Field[];
  updated_at: string;
  approved_version?: number | null;
}
export interface Revision {
  id: number;
  number: number;
  author_name: string;
  created_at: string;
  fields?: Field[];
  document?: number;
}
export interface Review {
  job: Job | null;
  engine_result: EngineResult | null;
  draft: Draft | null;
  revisions: Revision[];
}
export interface AuditEvent {
  id: number;
  action: string;
  actor_name: string;
  created_at: string;
  object_type: string;
  object_id: number;
}
export interface Dashboard {
  mail_action_count?: number;
  mail_unassigned_count?: number;
  mail_mine_count?: number;
  clients_count: number;
  review_count: number;
  failed_count: number;
  expiring_count: number;
  review_documents: DocumentRecord[];
  failed_documents: DocumentRecord[];
  expiring_policies: Policy[];
}

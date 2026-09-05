import type { Page } from './types';
export type WorkStatus = 'todo' | 'in_progress' | 'waiting' | 'done' | 'no_action';
export interface MailUser {
  id: number;
  username: string;
  is_active: boolean;
}
export interface Mailbox {
  is_current: boolean;
  id: number;
  kind: 'demo' | 'imap';
  folder: string;
  enabled: boolean;
  state: string;
  error_message: string;
  last_success: string | null;
  last_attempt: string | null;
  boundary_uid: number | null;
  uidvalidity: number | null;
  pending_count: number;
  error_count: number;
  version: number;
}
export interface MailAttachment {
  id: number;
  part_key: string;
  original_name: string;
  mime_type: string;
  size: number;
  blocked_reason: string;
  document: number | null;
}
export interface MessageRow {
  id: number;
  subject: string;
  sender_name: string;
  sender_address: string;
  received_at: string | null;
  declared_at: string | null;
  imported_at: string;
  status: WorkStatus;
  owner: MailUser | null;
  claimed_at: string | null;
  completed_by: MailUser | null;
  completed_at: string | null;
  client: number | null;
  client_name: string | null;
  policy: number | null;
  version: number;
  is_read: boolean;
  attachment_count: number;
  fetch_state: 'pending' | 'ready' | 'error';
  fetch_error: string;
  mailbox: number;
  source_kind: 'demo' | 'imap';
}
export interface MailMessage extends MessageRow {
  body_text: string;
  note: string;
  headers: [string, string][];
  warnings: string[];
  attachments: MailAttachment[];
  history: {
    id: number;
    action: string;
    actor_name: string;
    created_at: string;
    metadata: Record<string, unknown>;
  }[];
  client_candidates: { id: number; display_name: string; archived: boolean }[];
  related_messages: { id: number; subject: string; status: WorkStatus }[];
  recovery_candidates?: number[];
  recovery_status?: 'none' | 'review' | 'matched';
  client_candidate_count?: number;
}
export interface MailPage extends Page<MessageRow> {
  counts: Record<WorkStatus | 'total', number>;
}

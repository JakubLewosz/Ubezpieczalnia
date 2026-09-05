# API Broker Office

Sesja Django, końcowy `/`, JSON, CSRF w nagłówku `X-CSRFToken` z ciasteczka `csrftoken`. Anonimowy/CSRF/rola: 403; walidacja: 400; nieaktualna wersja lub współbieżne przejęcie: 409. Listy `{count,next,previous,results}`, po 20 rekordów, `page=2`. Nie ma publicznych URL magazynu ani haseł w API.

## Konta i Start

- GET `/api/auth/csrf/`; POST `/api/auth/login/` `{username,password}`; POST `/api/auth/logout/`; GET `/api/auth/me/` → `{id,username,first_name,last_name,role:ADMIN|EMPLOYEE}`.
- GET `/api/dashboard/` → dotychczasowe `clients_count,review_count,failed_count,expiring_count,review_documents,failed_documents,expiring_policies` oraz `mail_action_count,mail_unassigned_count,mail_mine_count`. Wszystkie liczniki są obliczane w bazie.

## Klienci, polisy i dokumenty

- `/api/clients/` GET/POST; `/{id}/` GET/PATCH. Filtry `search,ordering=display_name|-created_at,archived=false|true|all,exclude=1,2`. Wykluczenia przed paginacją. Edycja wymaga `version`. Osoba: imię/nazwisko; organizacja: organization_name; opcjonalne identyfikatory, kontakt, adres, note. GET `/{id}/history/`.
- `/api/policies/` GET/POST; `/{id}/` GET/PATCH. Filtry `client,expires_in=7|30|60,archived,search,ordering=end_date|-end_date|number|-number`. Polisa zawiera `participants:[{client,role:policyholder|insured,client_name}]`, `document_ids`, daty ISO, składkę Decimal-string/NULL, walutę i wersję. Archiwalna polisa nie jest propozycją uploadu.
- `/api/documents/` GET, POST multipart `{client,policy?,category?,file}`. Filtry `client,policy,ids=1,2,search,eligible_for_policy=<id|new>,participant_clients=1,2`. Ostatnie dwa zwracają nieprzypisane dokumenty uczestników i zachowują dokumenty bieżącej polisy. Wybrane ID można pobrać osobno bez pobierania całej bazy.
- Document: `{id,client,client_name,policy,original_name,mime_type,size,checksum,category,page_count,created_at,author_name,duplicate_warnings,latest_job,review_status,mail_source}`. `mail_source` jest tylko do odczytu: `{message,attachment,part_key}` albo NULL; źródłowa część MIME nie zmienia się po późniejszej edycji klienta maila.
- GET `/api/documents/{id}/original/` — prywatne pobranie attachment; GET `/api/documents/{id}/pages/{page}/` — uwierzytelniony PNG po odczycie.

## Odczyt, grupy i zatwierdzenia

- POST `/api/documents/{id}/extract/` → Job, 202. Job `{id,document,status:queued|running|succeeded|failed,error,created_at,started_at,finished_at}`.
- GET `/api/documents/{id}/review/` → `{job,engine_result,draft,revisions}`. Wynik silnika ma `profile,fields,warnings,pages:[{number,method:text|ocr}]`. Nieobsługiwany profil pozostaje NULL; nie tworzymy fałszywego wyniku dla ratunku ręcznego.
- Field: `{code,label,value:string|null,type:text|date|decimal|integer,unit,group,group_id,index,page,source,method,warnings,manual,absent,updated_by?,updated_at?}`. Brak, nieodczytanie, ręczna wartość i zero są odrębne. Nowe szkice mają UUID grup; historyczne rewizje pozostają niezmienne.
- Draft: `{id,version,approved_version,fields,updated_at,profile,origin:engine|manual,warnings,warning_digest}`. Warning `{id,field,code,message,requires_note}`. PATCH `/review/` `{version,fields}` ponownie waliduje bieżące dane; niedozwolona struktura/rola/znak XML → 400, niepewne wartości mogą pozostać w szkicu z ostrzeżeniem.
- POST `/review/groups/` `{version,group:participants|coverage_items}`; DELETE `/review/groups/` `{version,group_id}`. Serwer nadaje schemat i nowe UUID; nie używa ponownie usuniętych tożsamości. Dopuszczone role uczestnika profilu: `policyholder`, `insured`, `owner`, połączone w jednym polu przez przecinek. Limity 100 uczestników/30 pozycji zakresu.
- POST `/review/manual/` jawnie tworzy szkic profilu komunikacyjnego po ukończonym nieudanym/nierozpoznanym odczycie. Nie zastępuje wcześniejszego wyniku. POST `/review/reset/` `{version}` świadomie przejmuje najnowszy wynik do nowej wersji szkicu.
- POST `/api/documents/{id}/approve/` `{version,confirm_warnings,warning_digest,note}` → niezmienna rewizja 201. Przy ostrzeżeniach wymagane true i aktualny digest; `requires_note` wymaga 3–2000 znaków. Zmiana wersji/pól unieważnia stare potwierdzenie. Powtórne zatwierdzenie tej samej wersji → 409.
- GET `/api/revisions/{id}/` → snapshot z `document,fields,profile,warnings,origin,warning_confirmation` i metadanymi autora/czasu/numeru. GET `/export/` → kontrolny XLSX tej rewizji. Niedozwolony historyczny tekst → kontrolowane 400 z instrukcją korekty, bez zmiany rewizji; nigdy ciche obcięcie lub aktywna formuła.

## Wiadomości

- GET `/api/messages/` filtry `queue=action|unassigned|mine|all` (domyślnie action), `status=todo|in_progress|waiting|done|no_action`, `client,mailbox,search,ordering=received_at|-received_at`. Domyślnie najstarsze wymagające działania; brak daty dostawcy sortuje po lokalnym czasie, ale nie podszywa się pod nią w UI. Dodatkowo `counts:{total,todo,in_progress,waiting,done,no_action}` dla całego filtrowanego zbioru.
- Lista: `{id,mailbox,source_kind,subject,sender_name,sender_address,received_at,declared_at,imported_at,status,owner,claimed_at,completed_by,completed_at,client,client_name,policy,version,is_read,attachment_count,fetch_state,fetch_error,recovery_status}`. Owner/completed_by `{id,username,is_active}` lub NULL.
- GET `/api/messages/{id}/`: dodatkowo pełny `body_text` (zawsze tekst), `note,headers,warnings,attachments,history,client_candidates,client_candidate_count,related_messages,recovery_candidates,raw_sha256`. Kandydat klienta `{id,display_name,archived}`. Relacje nagłówków są pomocnicze, nie łączą obsługi. Detail ma ostatnie 100 zdarzeń, GET `/history/` pełną paginowaną historię `{id,action,actor_name,created_at,metadata}`.
- POST `/api/messages/{id}/read/` → `{is_read:true}`. Idempotentne, osobiste, nie zmienia wersji pracy, nie generuje historii przy pollingu. GET nie oznacza przeczytania.
- POST `/api/messages/{id}/claim/` `{version}` → aktualny pełny Message. Atomowe przejęcie nieprzydzielonego todo.
- POST `/api/messages/{id}/work/` `{version,action:update,status?,note?,client?,policy?}` → pełny Message. Właściciel/ADMIN. Inne akcje: `release`, `reopen`, `assign` (ta ostatnia wyłącznie ADMIN z `owner:<active user id>`). Pole `todo` osiąga się przez release, zakończoną pozycję otwiera tylko reopen. Szczegółowa tabela w MAILBOX.
- GET `/api/messages/{id}/raw/`: uwierzytelnione źródło `.eml` jako attachment/no-store. Stan `pending|ready|error` jest techniczny i nie zastępuje statusu obsługi.

## Załączniki i integracja

- Attachment: `{id,part_key,original_name,mime_type,size,blocked_reason,document}`. GET `/api/mail-attachments/{id}/download/` prywatny attachment/no-store; zablokowana część → 400.
- POST `/api/mail-attachments/{id}/promote/` `{version:<message version>,client,policy:null|id}` → `{document:Document,message_version}` 201; replay zwraca ten sam dokument 200 bez skutków ubocznych, również przy poprzedniej wersji. Tylko właściciel/ADMIN. Powiązanie źródła jest trwałe. Operacja nie uruchamia OCR ani nie zmienia klienta wiadomości.
- GET `/api/mailboxes/`: paginowane rekordy `{id,kind,is_current,folder,enabled,state,error_code,error_message,uidvalidity,boundary_uid,discovered_uid,pending_uidvalidity,last_success,last_attempt,version,pending_count,error_count}`. W razie błędnej konfiguracji może wystąpić `configuration_error` na poziomie odpowiedzi. Dawne konfiguracje pozostają historią, sterowanie dotyczy `is_current=true`.
- POST `/api/mailboxes/{id}/control/` `{version,action:test|start|pause|sync|recover}`, tylko ADMIN. Test zwraca `{ok,state,error_code,error_message,...}` i nie pobiera treści. Sync zwraca `{queued,state,error_code?}`. Pozostałe operacje zwracają aktualny Mailbox. Nie można podać z API hosta/loginu/sekretu.
- GET `/api/mail-users/?search=&page=` — paginowana lista aktywnych `{id,username,is_active}`, tylko ADMIN, do przekazania obsługi.

Przeczytanie, pobranie pliku i powiązanie klienta nigdy nie zamykają pracy. Endpointów SMTP, odpowiedzi, kasowania i zmiany flag dostawcy nie ma.

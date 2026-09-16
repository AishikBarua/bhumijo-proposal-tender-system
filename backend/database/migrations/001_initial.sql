-- ---------------------------------------------------------------------
-- 001_initial — the shape the JSONL files always implied but never enforced.
--
-- Every field that exists in the current data is preserved. Where a value
-- had to be cleaned (dates, money, categories), the untouched original is
-- kept beside it in an original_* column so nothing is lost in translation.
-- ---------------------------------------------------------------------

PRAGMA foreign_keys = ON;

-- --- reference data ---------------------------------------------------

CREATE TABLE entities (
    code        TEXT PRIMARY KEY,          -- P&D, FM, WASH, Tech
    name        TEXT NOT NULL,             -- as shown in the sidebar
    folder_name TEXT NOT NULL,             -- the old per-entity folder
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    is_active   INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- --- people -----------------------------------------------------------

CREATE TABLE roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,      -- admin, manager, entity_lead, contributor, viewer
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE permissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,      -- proposal.create, proposal.delete, ...
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE role_permissions (
    role_id       INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT NOT NULL UNIQUE,
    display_name   TEXT NOT NULL,
    email          TEXT,
    password_hash  TEXT,                   -- never a readable password
    role_id        INTEGER REFERENCES roles(id),
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at  TEXT
);

-- Which entities a user may see. No rows for a user with all-entity access.
CREATE TABLE user_entities (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_code TEXT NOT NULL REFERENCES entities(code) ON DELETE CASCADE,
    PRIMARY KEY (user_id, entity_code)
);

-- --- clients ----------------------------------------------------------

CREATE TABLE clients (
    id                  TEXT PRIMARY KEY,     -- keeps the existing c_… ids
    name                TEXT NOT NULL,
    entity_code         TEXT REFERENCES entities(code),
    project             TEXT NOT NULL DEFAULT '',
    value_amount        REAL,                 -- cleaned number, NULL if unparseable
    value_currency      TEXT DEFAULT 'BDT',
    original_value      TEXT NOT NULL DEFAULT '',
    responsible         TEXT NOT NULL DEFAULT '',
    start_date          TEXT,                 -- ISO yyyy-mm-dd
    end_date            TEXT,
    original_start_date TEXT NOT NULL DEFAULT '',
    original_end_date   TEXT NOT NULL DEFAULT '',
    notes               TEXT NOT NULL DEFAULT '',
    from_proposal_id    TEXT,
    -- present on only 2 of the 45 records; the rest must not gain one
    original_created_at TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_clients_entity ON clients(entity_code);
CREATE INDEX idx_clients_name   ON clients(name);

-- --- proposals --------------------------------------------------------

CREATE TABLE proposals (
    id                   TEXT PRIMARY KEY,   -- keeps the existing p_… / s… ids
    title                TEXT NOT NULL DEFAULT '',
    entity_code          TEXT REFERENCES entities(code),
    category_id          INTEGER REFERENCES categories(id),
    original_category    TEXT NOT NULL DEFAULT '',
    client_name          TEXT NOT NULL DEFAULT '',
    client_id            TEXT REFERENCES clients(id),
    value_amount         REAL,
    value_currency       TEXT DEFAULT 'BDT',
    original_value       TEXT NOT NULL DEFAULT '',
    responsible          TEXT NOT NULL DEFAULT '',
    open_date            TEXT,
    close_date           TEXT,
    start_date           TEXT,
    end_date             TEXT,
    original_open_date   TEXT NOT NULL DEFAULT '',
    original_close_date  TEXT NOT NULL DEFAULT '',
    original_start_date  TEXT NOT NULL DEFAULT '',
    original_end_date    TEXT NOT NULL DEFAULT '',
    status               TEXT NOT NULL DEFAULT '',
    result               TEXT NOT NULL DEFAULT '',
    contract             TEXT NOT NULL DEFAULT '',
    remark               TEXT NOT NULL DEFAULT '',
    -- what the old file held in its createdAt field; blank on 156 of 179 records
    original_created_at  TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
    created_by           INTEGER REFERENCES users(id),
    updated_by           INTEGER REFERENCES users(id)
);

CREATE INDEX idx_proposals_entity ON proposals(entity_code);
CREATE INDEX idx_proposals_status ON proposals(status);
CREATE INDEX idx_proposals_result ON proposals(result);
CREATE INDEX idx_proposals_close  ON proposals(close_date);
CREATE INDEX idx_proposals_client ON proposals(client_name);

-- --- grant programmes (the hitlist) -----------------------------------

CREATE TABLE grant_programmes (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL DEFAULT '',
    investor            TEXT NOT NULL DEFAULT '',
    hq                  TEXT NOT NULL DEFAULT '',
    type                TEXT NOT NULL DEFAULT '',
    cls                 TEXT NOT NULL DEFAULT '',   -- rolling / annual / one-off
    focus               TEXT NOT NULL DEFAULT '',
    ticket              TEXT NOT NULL DEFAULT '',
    geo                 TEXT NOT NULL DEFAULT '',
    closing_date        TEXT,
    -- NULL where the source had no closing date at all (124 of 192 records).
    -- Blank and absent are different things and the screens can tell.
    original_closing    TEXT,
    link                TEXT NOT NULL DEFAULT '',
    file_loc            TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT '',
    result              TEXT NOT NULL DEFAULT '',
    comment             TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          INTEGER REFERENCES users(id),
    updated_by          INTEGER REFERENCES users(id)
);

CREATE INDEX idx_grants_closing ON grant_programmes(closing_date);
CREATE INDEX idx_grants_status  ON grant_programmes(status);

-- --- attachments ------------------------------------------------------

CREATE TABLE attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type   TEXT NOT NULL,          -- proposal | grant | client
    record_id     TEXT NOT NULL,
    filename      TEXT NOT NULL,
    stored_path   TEXT NOT NULL,
    content_type  TEXT NOT NULL DEFAULT '',
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    uploaded_at   TEXT NOT NULL DEFAULT (datetime('now')),
    uploaded_by   INTEGER REFERENCES users(id)
);

CREATE INDEX idx_attachments_record ON attachments(record_type, record_id);

-- --- the audit trail --------------------------------------------------
-- Every create, edit and delete. before_json/after_json make an undo possible.

CREATE TABLE audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at   TEXT NOT NULL DEFAULT (datetime('now')),
    user_id       INTEGER REFERENCES users(id),
    username      TEXT NOT NULL DEFAULT 'system',
    action        TEXT NOT NULL,          -- create | update | delete | restore | login
    record_type   TEXT NOT NULL,
    record_id     TEXT NOT NULL DEFAULT '',
    summary       TEXT NOT NULL DEFAULT '',
    before_json   TEXT,
    after_json    TEXT,
    client_ip     TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_audit_record   ON audit_log(record_type, record_id);
CREATE INDEX idx_audit_occurred ON audit_log(occurred_at);

-- --- seed the reference data -----------------------------------------

INSERT INTO entities (code, name, folder_name, sort_order) VALUES
    ('P&D',  'Planning & Design',   'Planning & Design',   1),
    ('FM',   'Facility Management', 'Facility Management', 2),
    ('WASH', 'WASH/Toilets',        'WASH-Toilets',        3),
    ('Tech', 'Technology',          'Technology',          4);

INSERT INTO roles (code, name, description) VALUES
    ('admin',       'Administrator', 'Everything, including managing users and restoring deleted records'),
    ('manager',     'Manager',       'All entities: create, edit, delete, approve, report'),
    ('entity_lead', 'Entity lead',   'Their own entity: create, edit, delete their own, report'),
    ('contributor', 'Contributor',   'Their own entity: create and edit only'),
    ('viewer',      'Viewer',        'Read and export only');

INSERT INTO permissions (code, description) VALUES
    ('proposal.view',   'See proposals'),
    ('proposal.create', 'Add a proposal'),
    ('proposal.edit',   'Change a proposal'),
    ('proposal.delete', 'Delete a proposal'),
    ('grant.view',      'See grant programmes'),
    ('grant.create',    'Add a grant programme'),
    ('grant.edit',      'Change a grant programme'),
    ('grant.delete',    'Delete a grant programme'),
    ('client.view',     'See clients'),
    ('client.edit',     'Change clients'),
    ('report.view',     'Run and export reports'),
    ('user.manage',     'Manage user accounts'),
    ('audit.view',      'See the audit trail'),
    ('record.restore',  'Restore a deleted record');

-- Governance Portal — reference data for roles, permissions, role_permissions, request_statuses, artifact_names,
-- review_types and pdlc_checkpoints (SQLite). The API inserts the same defaults into empty tables; after that
-- admins manage them on the Reference Data page. Reviewers are seeded by the API (DEFAULT_REVIEWERS).
--
-- Extracted from api/governance.db. Load it after schema.sql:
--   sqlite3 governance.db < architecture/sql/schema.sql
--   sqlite3 governance.db < architecture/sql/reference-data.sql
--
-- Safe to run more than once: existing rows are left untouched (ON CONFLICT DO NOTHING).
-- Grants look roles up by code, so they work whatever ids the roles receive.
-- created_by / updated_by are NULL because the system created these rows; NULL is also required
-- here because the users they would point to may not exist in the target database.

PRAGMA foreign_keys = ON;

BEGIN;

-- ---------------------------------------------------------------------------
-- roles
-- ---------------------------------------------------------------------------
INSERT INTO roles (code, name, ad_group, description, created_at, updated_at, created_by, updated_by) VALUES
    ('REQUESTOR', 'Requestor', 'AAD-GovPortal-Requestors', 'Submits intakes and tracks their own requests.', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z', NULL, NULL),
    ('REVIEWER', 'Reviewer', 'AAD-GovPortal-Reviewers', 'Reviews the queue and moves requests through the lifecycle.', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z', NULL, NULL),
    ('CHIEF_ARCHITECT', 'Chief Architect', 'AAD-GovPortal-ChiefArchitects', 'Reviews the queue and approves Critical-risk requests in Chief Architecture Review.', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z', NULL, NULL),
    ('ADMIN', 'Admin', 'AAD-GovPortal-Admins', 'Full access, including users and permissions.', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z', NULL, NULL)
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- permissions
-- ---------------------------------------------------------------------------
INSERT INTO permissions (code, category, label, description, position, created_at, created_by, updated_at, updated_by) VALUES
    ('request:create', 'Requests', 'Create requests', 'Submit new intake requests.', 0, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:view:own', 'Requests', 'View own requests', 'See requests you submitted.', 1, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:view:all', 'Requests', 'View all requests', 'See every request in the portal.', 2, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:edit:own', 'Requests', 'Edit own requests', 'Edit your own request while DRAFT, SUBMITTED or CHANGES_REQUESTED. Review fields excluded.', 3, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:edit:all', 'Requests', 'Edit any request', 'Edit any request, including status, review dates and comments.', 4, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:withdraw:own', 'Requests', 'Withdraw own requests', 'Withdraw your own request while it is DRAFT or SUBMITTED.', 5, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:delete:all', 'Requests', 'Delete any request', 'Permanently delete any request.', 6, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:resubmit', 'Review', 'Resubmit after changes', 'Send your own request back to SUBMITTED after changes were requested.', 7, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:review', 'Review', 'Review requests', 'Approve, reject or send back other people''s requests.', 8, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:schedule', 'Review', 'Schedule ARB meetings', 'Move other people''s requests to SCHEDULED and set or change the ARB meeting date and time.', 9, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:signoff', 'Review', 'Chief Architect sign-off', 'Decide Critical-risk requests in CHIEF_ARCHITECTURE_REVIEW and lower a risk tier.', 10, '2026-10-10T00:00:00Z', NULL, '2026-10-10T00:00:00Z', NULL),
    ('board:card:edit', 'Team Board', 'Edit board cards', 'Add, edit, move and delete Team Board cards.', 11, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('board:field:manage', 'Team Board', 'Manage board fields', 'Add, rename and delete Team Board fields and lanes.', 12, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('calendar:view', 'ARB Calendar', 'View ARB calendar', 'Open the Calendar of ARB meetings.', 13, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('insights:view', 'Insights', 'View insights', 'Open the Insights scorecard.', 14, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('insights:export', 'Insights', 'Export insights', 'Download Insights data as CSV.', 15, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('user:manage', 'Administration', 'Manage users', 'Add, rename and delete users and set their group.', 16, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('reference:manage', 'Administration', 'Manage reference data', 'Add, edit, order, activate, deactivate and remove review types, PDLC checkpoints, reference link names and reviewers, and edit status text.', 17, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('role:assign', 'Administration', 'Assign permissions', 'Edit the permission matrix and create roles.', 18, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL)
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- role_permissions
-- ---------------------------------------------------------------------------
-- REQUESTOR: 6 permissions
INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by)
SELECT r.id, g.permission_code, g.created_at, NULL, g.updated_at, NULL
FROM roles r
JOIN (
    SELECT 'request:create' AS permission_code, '2026-10-03T02:55:54Z' AS created_at, '2026-10-03T02:55:54Z' AS updated_at
    UNION ALL SELECT 'request:view:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:edit:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:withdraw:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:resubmit', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'calendar:view', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
) g
WHERE r.code = 'REQUESTOR'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- REVIEWER: 6 permissions
INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by)
SELECT r.id, g.permission_code, g.created_at, NULL, g.updated_at, NULL
FROM roles r
JOIN (
    SELECT 'request:view:all' AS permission_code, '2026-10-03T02:55:54Z' AS created_at, '2026-10-03T02:55:54Z' AS updated_at
    UNION ALL SELECT 'request:review', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:schedule', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'board:card:edit', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'calendar:view', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'insights:view', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
) g
WHERE r.code = 'REVIEWER'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- CHIEF_ARCHITECT: 7 permissions
INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by)
SELECT r.id, g.permission_code, g.created_at, NULL, g.updated_at, NULL
FROM roles r
JOIN (
    SELECT 'request:view:all' AS permission_code, '2026-10-10T00:00:00Z' AS created_at, '2026-10-10T00:00:00Z' AS updated_at
    UNION ALL SELECT 'request:review', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z'
    UNION ALL SELECT 'request:schedule', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z'
    UNION ALL SELECT 'request:signoff', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z'
    UNION ALL SELECT 'board:card:edit', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z'
    UNION ALL SELECT 'calendar:view', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z'
    UNION ALL SELECT 'insights:view', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z'
) g
WHERE r.code = 'CHIEF_ARCHITECT'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- ADMIN: 19 permissions
INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by)
SELECT r.id, g.permission_code, g.created_at, NULL, g.updated_at, NULL
FROM roles r
JOIN (
    SELECT 'request:create' AS permission_code, '2026-10-03T02:55:54Z' AS created_at, '2026-10-03T02:55:54Z' AS updated_at
    UNION ALL SELECT 'request:view:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:view:all', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:edit:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:edit:all', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:withdraw:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:delete:all', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:resubmit', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:review', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:schedule', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:signoff', '2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z'
    UNION ALL SELECT 'board:card:edit', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'board:field:manage', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'calendar:view', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'insights:view', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'insights:export', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'user:manage', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'reference:manage', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z'
    UNION ALL SELECT 'role:assign', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
) g
WHERE r.code = 'ADMIN'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- request_statuses
-- ---------------------------------------------------------------------------
INSERT INTO request_statuses (code, label, meaning, who_acts, position, builtin, created_at, created_by, updated_at, updated_by) VALUES
    ('DRAFT', 'Draft', 'Saved, not submitted', 'Requestor', 0, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('SUBMITTED', 'Submitted', 'Waiting for a reviewer to pick it up', 'Reviewer', 1, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('IN_REVIEW', 'In Review', 'Reviewer is assessing it', 'Reviewer', 2, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('CHANGES_REQUESTED', 'Changes Requested', 'Sent back for changes', 'Requestor', 3, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('SCHEDULED', 'Scheduled', 'Booked for an Architecture Review Board meeting', 'Admin / Chief Architect / Reviewer', 4, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('CHIEF_ARCHITECTURE_REVIEW', 'Chief Architecture Review', 'Critical risk: waiting for Chief Architect approval', 'Chief Architect', 5, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('APPROVED', 'Approved', 'Final approval', 'Admin / Chief Architect / Reviewer', 6, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('APPROVED_WITH_CONDITIONS', 'Approved with Conditions', 'Approved, with conditions attached', 'Admin / Chief Architect / Reviewer', 7, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('REJECTED', 'Rejected', 'Final rejection', 'Admin / Chief Architect / Reviewer', 8, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL),
    ('WITHDRAWN', 'Withdrawn', 'Cancelled by the Requestor', 'Requestor', 9, 1, '2026-10-03T00:00:00Z', NULL, '2026-10-03T00:00:00Z', NULL)
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- artifact_names
-- ---------------------------------------------------------------------------
INSERT INTO artifact_names (code, label, required_for, position, created_at, created_by, updated_at, updated_by) VALUES
    ('SAD', 'SAD', '["Solution Architecture (SAD)", "Architecture Decision Records (ADR)", "Event-Driven Architecture Design", "Data Architecture & Modeling", "Architecture Certification"]', 0, '2026-10-14T00:00:00Z', NULL, '2026-10-14T00:00:00Z', NULL),
    ('ADR', 'ADR', '["Architecture Decision Records (ADR)"]', 1, '2026-10-14T00:00:00Z', NULL, '2026-10-14T00:00:00Z', NULL),
    ('PATTERNS', 'Patterns & Standards', '["Architecture Patterns & Standards"]', 2, '2026-10-14T00:00:00Z', NULL, '2026-10-14T00:00:00Z', NULL),
    ('DUE_DILIGENCE', 'Due Diligence', '["Architecture Due Diligence"]', 3, '2026-10-14T00:00:00Z', NULL, '2026-10-14T00:00:00Z', NULL),
    ('API_SPEC', 'API Specification', '["API Contract & Design"]', 4, '2026-10-14T00:00:00Z', NULL, '2026-10-14T00:00:00Z', NULL),
    ('DATA_DESIGN', 'Data Design', '[]', 5, '2026-10-14T00:00:00Z', NULL, '2026-10-14T00:00:00Z', NULL),
    ('OTHER', 'Others', '[]', 6, '2026-10-14T00:00:00Z', NULL, '2026-10-14T00:00:00Z', NULL)
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- review_types
-- ---------------------------------------------------------------------------
INSERT INTO review_types (name, active, created_at, created_by, updated_at, updated_by) VALUES
    ('Solution Architecture (SAD)', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Architecture Decision Records (ADR)', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Event-Driven Architecture Design', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('AI/ML Solution Architecture', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('API Contract & Design', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Architecture Patterns & Standards', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Data Architecture & Modeling', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Architecture Certification', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Architecture Due Diligence', 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL)
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- pdlc_checkpoints
-- ---------------------------------------------------------------------------
INSERT INTO pdlc_checkpoints (name, position, active, created_at, created_by, updated_at, updated_by) VALUES
    ('Inception', 0, 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Elaboration', 1, 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Construction', 2, 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL),
    ('Delivery', 3, 1, '2026-10-15T00:00:00Z', NULL, '2026-10-15T00:00:00Z', NULL)
ON CONFLICT (name) DO NOTHING;

COMMIT;

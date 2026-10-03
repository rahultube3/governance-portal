-- Governance Portal — reference data for roles, permissions and role_permissions (SQLite)
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
    ('ADMIN', 'Admin', 'AAD-GovPortal-Admins', 'Full access, including users and permissions.', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z', NULL, NULL)
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- permissions
-- ---------------------------------------------------------------------------
INSERT INTO permissions (code, category, label, description, position, created_at, created_by, updated_at, updated_by) VALUES
    ('request:create', 'Requests', 'Create requests', 'Submit new intake requests.', 0, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:view:own', 'Requests', 'View own requests', 'See requests you submitted.', 1, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:view:all', 'Requests', 'View all requests', 'See every request in the portal.', 2, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:edit:own', 'Requests', 'Edit own requests', 'Edit your own request while PENDING or in REWORK. Review fields excluded.', 3, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:edit:all', 'Requests', 'Edit any request', 'Edit any request, including status, review dates and comments.', 4, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:withdraw:own', 'Requests', 'Withdraw own requests', 'Delete your own request while it is PENDING.', 5, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:delete:all', 'Requests', 'Delete any request', 'Permanently delete any request.', 6, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:resubmit', 'Review', 'Resubmit after rework', 'Move your own REWORK request back to PENDING.', 7, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('request:review', 'Review', 'Review requests', 'Approve, reject or send back other people''s requests.', 8, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('board:card:edit', 'Team Board', 'Edit board cards', 'Add, edit, move and delete Team Board cards.', 9, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('board:field:manage', 'Team Board', 'Manage board fields', 'Add, rename and delete Team Board fields and lanes.', 10, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('insights:view', 'Insights', 'View insights', 'Open the Insights scorecard.', 11, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('insights:export', 'Insights', 'Export insights', 'Download Insights data as CSV.', 12, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('user:manage', 'Administration', 'Manage users', 'Add, rename and delete users and set their group.', 13, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL),
    ('role:assign', 'Administration', 'Assign permissions', 'Edit this permission matrix and the AD group mapping.', 14, '2026-10-03T03:33:02Z', NULL, '2026-10-03T03:33:02Z', NULL)
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- role_permissions
-- ---------------------------------------------------------------------------
-- REQUESTOR: 5 permissions
INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by)
SELECT r.id, g.permission_code, g.created_at, NULL, g.updated_at, NULL
FROM roles r
JOIN (
    SELECT 'request:create' AS permission_code, '2026-10-03T02:55:54Z' AS created_at, '2026-10-03T02:55:54Z' AS updated_at
    UNION ALL SELECT 'request:view:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:edit:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:withdraw:own', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'request:resubmit', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
) g
WHERE r.code = 'REQUESTOR'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- REVIEWER: 4 permissions
INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by)
SELECT r.id, g.permission_code, g.created_at, NULL, g.updated_at, NULL
FROM roles r
JOIN (
    SELECT 'request:view:all' AS permission_code, '2026-10-03T02:55:54Z' AS created_at, '2026-10-03T02:55:54Z' AS updated_at
    UNION ALL SELECT 'request:review', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'board:card:edit', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'insights:view', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
) g
WHERE r.code = 'REVIEWER'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- ADMIN: 15 permissions
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
    UNION ALL SELECT 'board:card:edit', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'board:field:manage', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'insights:view', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'insights:export', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'user:manage', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
    UNION ALL SELECT 'role:assign', '2026-10-03T02:55:54Z', '2026-10-03T02:55:54Z'
) g
WHERE r.code = 'ADMIN'
ON CONFLICT (role_id, permission_code) DO NOTHING;

COMMIT;

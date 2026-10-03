-- Governance Portal — useful read queries for every table (SQLite)
--
-- Run in the sqlite3 shell from the repo root:
--   sqlite3 -header -column api/governance.db
--   sqlite> .param set :user_id 4
--   sqlite> .param set :request_id 12
--   sqlite> .read architecture/sql/queries.sql      (or paste a single query)
--
-- Parameters used below: :user_id, :request_id, :status, :role_code, :since (ISO date, e.g. '2026-10-01').
-- A NULL *_by column means the system wrote the row; those show as 'System'.

-- ===========================================================================
-- Overview
-- ===========================================================================

-- Row count per table.
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL SELECT 'roles', COUNT(*) FROM roles
UNION ALL SELECT 'permissions', COUNT(*) FROM permissions
UNION ALL SELECT 'role_permissions', COUNT(*) FROM role_permissions
UNION ALL SELECT 'requests', COUNT(*) FROM requests
UNION ALL SELECT 'status_history', COUNT(*) FROM status_history
UNION ALL SELECT 'request_statuses', COUNT(*) FROM request_statuses
UNION ALL SELECT 'board_fields', COUNT(*) FROM board_fields
UNION ALL SELECT 'board_cards', COUNT(*) FROM board_cards;

-- ===========================================================================
-- users
-- ===========================================================================

-- All users with their role, AD group and who last changed them.
SELECT u.id, u.name, u.email, u.role, r.name AS role_name, r.ad_group,
       u.created_at, COALESCE(cb.name, 'System') AS created_by,
       u.updated_at, COALESCE(ub.name, 'System') AS updated_by
FROM users u
LEFT JOIN roles r  ON r.code = u.role
LEFT JOIN users cb ON cb.id = u.created_by
LEFT JOIN users ub ON ub.id = u.updated_by
ORDER BY u.role, u.name;

-- Effective permissions for one user (:user_id). Mirrors the API: user -> AD group -> every role
-- mapped to that group -> granted permissions.
SELECT u.name, er.code AS role_code, p.code AS permission, p.label
FROM users u
JOIN roles ur ON ur.code = u.role
JOIN roles er ON er.ad_group = ur.ad_group AND COALESCE(ur.ad_group, '') != ''
JOIN role_permissions rp ON rp.role_id = er.id
JOIN permissions p ON p.code = rp.permission_code
WHERE u.id = :user_id
ORDER BY p.position;

-- Users who can assign permissions (the API refuses changes that would leave this empty).
SELECT DISTINCT u.id, u.name, u.email
FROM users u
JOIN roles ur ON ur.code = u.role
JOIN roles er ON er.ad_group = ur.ad_group AND COALESCE(ur.ad_group, '') != ''
JOIN role_permissions rp ON rp.role_id = er.id AND rp.permission_code = 'role:assign';

-- ===========================================================================
-- roles
-- ===========================================================================

-- Roles with AD group, member count and number of permissions.
SELECT r.code, r.name, r.ad_group,
       (SELECT COUNT(*) FROM users u WHERE u.role = r.code) AS members,
       (SELECT COUNT(*) FROM role_permissions rp WHERE rp.role_id = r.id) AS permissions,
       r.updated_at, COALESCE(ub.name, 'System') AS updated_by
FROM roles r
LEFT JOIN users ub ON ub.id = r.updated_by
ORDER BY r.id;

-- Roles with no AD group mapped (nobody receives them).
SELECT code, name FROM roles WHERE COALESCE(ad_group, '') = '';

-- ===========================================================================
-- permissions
-- ===========================================================================

-- Permission catalog in display order.
SELECT code, category, label, description FROM permissions ORDER BY position;

-- Permissions no role currently holds.
SELECT p.code, p.label
FROM permissions p
LEFT JOIN role_permissions rp ON rp.permission_code = p.code
WHERE rp.role_id IS NULL
ORDER BY p.position;

-- ===========================================================================
-- role_permissions
-- ===========================================================================

-- Permission matrix (one column per role), like the Permissions page.
SELECT p.category, p.code,
       MAX(CASE WHEN r.code = 'REQUESTOR' THEN 'X' ELSE '' END) AS requestor,
       MAX(CASE WHEN r.code = 'REVIEWER'  THEN 'X' ELSE '' END) AS reviewer,
       MAX(CASE WHEN r.code = 'ADMIN'     THEN 'X' ELSE '' END) AS admin
FROM permissions p
LEFT JOIN role_permissions rp ON rp.permission_code = p.code
LEFT JOIN roles r ON r.id = rp.role_id
GROUP BY p.code
ORDER BY p.position;

-- Grants for one role (:role_code) with who granted them and when.
SELECT r.code AS role_code, rp.permission_code, rp.created_at AS granted_at,
       COALESCE(gb.name, 'System') AS granted_by
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
LEFT JOIN users gb ON gb.id = rp.created_by
WHERE r.code = :role_code
ORDER BY rp.created_at DESC;

-- ===========================================================================
-- requests
-- ===========================================================================

-- All requests with owner and last editor, newest activity first.
SELECT q.id, 'ARB-' || q.id AS arb_number, q.arb_title, q.status, q.artifact_type, q.app_name, q.pr,
       COALESCE(cb.name, 'System') AS created_by, q.created_at,
       COALESCE(ub.name, 'System') AS updated_by, q.updated_at
FROM requests q
LEFT JOIN users cb ON cb.id = q.created_by
LEFT JOIN users ub ON ub.id = q.updated_by
ORDER BY q.updated_at DESC;

-- One request (:request_id).
SELECT * FROM requests WHERE id = :request_id;

-- Requests in one status (:status), e.g. 'SUBMITTED'.
SELECT id, arb_title, app_name, date_submitted FROM requests WHERE status = :status ORDER BY date_submitted;

-- Requests owned by one user (:user_id) — what a requestor sees as "My Requests".
SELECT id, arb_title, status, updated_at FROM requests WHERE created_by = :user_id ORDER BY updated_at DESC;

-- Counts by status, in lifecycle order (Dashboard lifecycle rail).
SELECT s.code, s.label, COUNT(r.id) AS requests
FROM request_statuses s
LEFT JOIN requests r ON r.status = s.code
GROUP BY s.code
ORDER BY s.position;

-- Counts by Kanban Board column.
SELECT CASE status
         WHEN 'SUBMITTED'                 THEN 'Submitted'
         WHEN 'IN_REVIEW'                 THEN 'In Review'
         WHEN 'SCHEDULED'                 THEN 'In Review'
         WHEN 'CHANGES_REQUESTED'         THEN 'Changes Requested'
         WHEN 'CHIEF_ARCHITECTURE_REVIEW' THEN 'Chief Architecture Review'
         WHEN 'APPROVED'                  THEN 'Approved'
         WHEN 'APPROVED_WITH_CONDITIONS'  THEN 'Approved'
         WHEN 'REJECTED'                  THEN 'Rejected'
       END AS kanban_column,
       COUNT(*) AS requests
FROM requests
WHERE status NOT IN ('DRAFT', 'WITHDRAWN')
GROUP BY kanban_column;

-- Counts by review type.
SELECT artifact_type, COUNT(*) AS requests FROM requests GROUP BY artifact_type ORDER BY requests DESC;

-- Monthly intake vs completed (Insights).
SELECT substr(date_submitted, 1, 7) AS month,
       COUNT(*) AS intake,
       SUM(status IN ('APPROVED', 'APPROVED_WITH_CONDITIONS')) AS completed
FROM requests
GROUP BY month
ORDER BY month;

-- Requests with no owner (seeded requests whose architect matches no demo requestor, or whose owner was deleted).
SELECT id, arb_title, solution_architect FROM requests WHERE created_by IS NULL;

-- Upcoming ARB meetings (the Calendar), soonest first.
SELECT r.meeting_date, r.meeting_time, r.id, r.arb_title, s.label AS status
FROM requests r
JOIN request_statuses s ON s.code = r.status
WHERE r.meeting_date >= date('now')
ORDER BY r.meeting_date, r.meeting_time;

-- ===========================================================================
-- request_statuses
-- ===========================================================================

-- Status lookup in lifecycle order, with how many requests are in each.
SELECT s.position, s.code, s.label, s.meaning, s.who_acts, COUNT(r.id) AS requests
FROM request_statuses s
LEFT JOIN requests r ON r.status = s.code
GROUP BY s.code
ORDER BY s.position;

-- ===========================================================================
-- status_history
-- ===========================================================================

-- Timeline for one request (:request_id) with who made each change.
SELECT h.created_at, h.from_status, h.to_status, h.note, COALESCE(u.name, 'System') AS changed_by
FROM status_history h
LEFT JOIN users u ON u.id = h.created_by
WHERE h.request_id = :request_id
ORDER BY h.id;

-- Most recent 20 status changes across all requests.
SELECT h.created_at, 'ARB-' || q.id AS arb_number, q.arb_title, h.from_status, h.to_status,
       COALESCE(u.name, 'System') AS changed_by
FROM status_history h
JOIN requests q ON q.id = h.request_id
LEFT JOIN users u ON u.id = h.created_by
ORDER BY h.id DESC
LIMIT 20;

-- Reviewer activity: status changes per person.
SELECT COALESCE(u.name, 'System') AS changed_by, COUNT(*) AS changes
FROM status_history h
LEFT JOIN users u ON u.id = h.created_by
GROUP BY h.created_by
ORDER BY changes DESC;

-- ===========================================================================
-- board_fields
-- ===========================================================================

-- Field definitions in display order; flags the title and grouping fields.
SELECT f.id, f.key, f.label, f.type, f.options,
       CASE WHEN f.is_title THEN 'title' WHEN f.is_group THEN 'grouping' ELSE '' END AS field_role,
       f.updated_at, COALESCE(ub.name, 'System') AS updated_by
FROM board_fields f
LEFT JOIN users ub ON ub.id = f.updated_by
ORDER BY f.position, f.id;

-- ===========================================================================
-- board_cards
-- ===========================================================================

-- Cards with the default fields pulled out of the JSON data.
SELECT c.id,
       json_extract(c.data, '$.title')    AS title,
       json_extract(c.data, '$.status')   AS status,
       json_extract(c.data, '$.team')     AS team,
       json_extract(c.data, '$.priority') AS priority,
       json_extract(c.data, '$.dueDate')  AS due_date,
       COALESCE(ub.name, 'System') AS updated_by, c.updated_at
FROM board_cards c
LEFT JOIN users ub ON ub.id = c.updated_by
ORDER BY c.position, c.id;

-- Cards per value of the grouping field (the board's lanes).
SELECT json_extract(c.data, '$.' || f.key) AS lane, COUNT(*) AS cards
FROM board_cards c
CROSS JOIN board_fields f
WHERE f.is_group = 1
GROUP BY lane;

-- Overdue cards: due date in the past and not Done.
SELECT id, json_extract(data, '$.title') AS title, json_extract(data, '$.dueDate') AS due_date
FROM board_cards
WHERE json_extract(data, '$.dueDate') < date('now')
  AND COALESCE(json_extract(data, '$.status'), '') NOT IN ('Done', 'Completed', 'Closed');

-- ===========================================================================
-- Audit (all tables)
-- ===========================================================================

-- Every change since :since across all tables, newest first.
SELECT a.table_name, a.row_key, a.changed_at, COALESCE(u.name, 'System') AS changed_by FROM (
    SELECT 'requests' AS table_name, CAST(id AS TEXT) AS row_key, updated_at AS changed_at, updated_by AS user_id FROM requests
    UNION ALL SELECT 'status_history', CAST(id AS TEXT), created_at, created_by FROM status_history
    UNION ALL SELECT 'users', CAST(id AS TEXT), updated_at, updated_by FROM users
    UNION ALL SELECT 'roles', code, updated_at, updated_by FROM roles
    UNION ALL SELECT 'permissions', code, updated_at, updated_by FROM permissions
    UNION ALL SELECT 'role_permissions', role_id || ':' || permission_code, created_at, created_by FROM role_permissions
    UNION ALL SELECT 'request_statuses', code, updated_at, updated_by FROM request_statuses
    UNION ALL SELECT 'board_fields', key, updated_at, updated_by FROM board_fields
    UNION ALL SELECT 'board_cards', CAST(id AS TEXT), updated_at, updated_by FROM board_cards
) a
LEFT JOIN users u ON u.id = a.user_id
WHERE a.changed_at >= :since
ORDER BY a.changed_at DESC;

-- Everything one user (:user_id) created or last updated.
SELECT 'requests' AS table_name, id AS row_id, arb_title AS label, created_by = :user_id AS created, updated_by = :user_id AS updated
FROM requests WHERE :user_id IN (created_by, updated_by)
UNION ALL
SELECT 'board_cards', id, json_extract(data, '$.title'), created_by = :user_id, updated_by = :user_id
FROM board_cards WHERE :user_id IN (created_by, updated_by)
UNION ALL
SELECT 'users', id, name, created_by = :user_id, updated_by = :user_id
FROM users WHERE :user_id IN (created_by, updated_by);

-- 002 — which role may do what. Separate from 001 so the grid can be
-- changed later without touching the table definitions.

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'admin';

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'manager'
  AND p.code IN ('proposal.view','proposal.create','proposal.edit','proposal.delete',
                 'grant.view','grant.create','grant.edit','grant.delete',
                 'client.view','client.edit','report.view','audit.view','record.restore');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'entity_lead'
  AND p.code IN ('proposal.view','proposal.create','proposal.edit','proposal.delete',
                 'grant.view','grant.create','grant.edit',
                 'client.view','client.edit','report.view');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'contributor'
  AND p.code IN ('proposal.view','proposal.create','proposal.edit',
                 'grant.view','grant.create','grant.edit',
                 'client.view','report.view');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'viewer'
  AND p.code IN ('proposal.view','grant.view','client.view','report.view');

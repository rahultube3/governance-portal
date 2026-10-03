import { Audited } from './audit.model';
import { Permission, Role } from './user.model';

export interface PermissionDef {
  code: Permission;
  category: string;
  label: string;
  description: string;
}

export interface Grant {
  grantedAt: string;
  grantedBy: number | null;
}

export interface RoleDef extends Audited {
  id: number;
  code: Role;
  name: string;
  adGroup: string;
  description: string;
  permissions: Permission[];
  grants: Partial<Record<Permission, Grant>>;
  memberCount: number;
}

export interface RbacSnapshot {
  permissions: PermissionDef[];
  roles: RoleDef[];
}

export interface RoleSummary {
  code: Role;
  name: string;
  adGroup: string;
}

export interface RoleInfo {
  code: Role;
  name: string;
  description: string;
}

export interface RoleInput {
  code: Role;
  name: string;
  adGroup: string;
  description: string;
  permissions: Permission[];
}

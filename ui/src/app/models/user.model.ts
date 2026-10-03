import { Audited } from './audit.model';

export type Role = 'REQUESTOR' | 'REVIEWER' | 'ADMIN';

export const ROLES: Role[] = ['REQUESTOR', 'REVIEWER', 'ADMIN'];

export const ROLE_LABELS: Record<Role, string> = {
  REQUESTOR: 'Requestor',
  REVIEWER: 'Reviewer',
  ADMIN: 'Admin',
};

export type Permission =
  | 'request:create'
  | 'request:view:own'
  | 'request:view:all'
  | 'request:edit:own'
  | 'request:edit:all'
  | 'request:withdraw:own'
  | 'request:delete:all'
  | 'request:resubmit'
  | 'request:review'
  | 'board:card:edit'
  | 'board:field:manage'
  | 'insights:view'
  | 'insights:export'
  | 'user:manage'
  | 'role:assign';

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
}

export interface ManagedUser extends User, Audited {}

export interface SessionUser extends User {
  adGroups: string[];
  roles: Role[];
  roleNames: string[];
  permissions: Permission[];
}

export interface UserInput {
  name: string;
  email: string;
  role: Role;
}

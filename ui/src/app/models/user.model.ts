import { Audited } from './audit.model';

// Role codes come from the `roles` table; admins can add new ones.
export type Role = string;

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
  | 'request:schedule'
  | 'calendar:view'
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

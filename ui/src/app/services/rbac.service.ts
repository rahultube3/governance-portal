import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { RbacSnapshot, RoleInput, RoleSummary } from '../models/rbac.model';
import { Permission, Role } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class RbacService {
  constructor(private http: HttpClient) {}

  get(): Observable<RbacSnapshot> {
    return this.http.get<RbacSnapshot>('/api/v1/rbac');
  }

  roles(): Observable<RoleSummary[]> {
    return this.http.get<RoleSummary[]>('/api/v1/roles');
  }

  setGrants(grants: Partial<Record<Role, Permission[]>>): Observable<RbacSnapshot> {
    return this.http.put<RbacSnapshot>('/api/v1/rbac/grants', { grants });
  }

  createRole(role: RoleInput): Observable<RbacSnapshot> {
    return this.http.post<RbacSnapshot>('/api/v1/rbac/roles', role);
  }

}

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { RbacSnapshot, RolePatch, RoleSummary } from '../models/rbac.model';
import { Permission, Role } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class RbacService {
  constructor(private http: HttpClient) {}

  get(): Observable<RbacSnapshot> {
    return this.http.get<RbacSnapshot>('/api/rbac');
  }

  roles(): Observable<RoleSummary[]> {
    return this.http.get<RoleSummary[]>('/api/roles');
  }

  setGrants(grants: Partial<Record<Role, Permission[]>>): Observable<RbacSnapshot> {
    return this.http.put<RbacSnapshot>('/api/rbac/grants', { grants });
  }

  updateRole(code: Role, patch: RolePatch): Observable<RbacSnapshot> {
    return this.http.patch<RbacSnapshot>(`/api/rbac/roles/${code}`, patch);
  }
}

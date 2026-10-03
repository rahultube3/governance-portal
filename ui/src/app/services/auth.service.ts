import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of, tap } from 'rxjs';
import { Permission, SessionUser, User } from '../models/user.model';
import { GovRequest, LifecycleStatus } from '../models/request.model';
import { RoleInfo } from '../models/rbac.model';

const OWNER_EDITABLE: LifecycleStatus[] = ['DRAFT', 'SUBMITTED', 'CHANGES_REQUESTED'];

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly current = signal<SessionUser | null>(null);
  private readonly granted = computed(() => new Set(this.current()?.permissions ?? []));
  readonly user = this.current.asReadonly();

  constructor(private http: HttpClient) {}

  restore(): Observable<SessionUser | null> {
    return this.http.get<SessionUser>('/api/v1/auth/me').pipe(
      catchError(() => of(null)),
      tap(u => this.current.set(u)),
    );
  }

  directory(): Observable<User[]> {
    return this.http.get<User[]>('/api/v1/auth/users');
  }

  roles(): Observable<RoleInfo[]> {
    return this.http.get<RoleInfo[]>('/api/v1/auth/roles');
  }

  login(userId: number): Observable<SessionUser> {
    return this.http.post<SessionUser>('/api/v1/auth/login', { userId }).pipe(tap(u => this.current.set(u)));
  }

  logout(): Observable<unknown> {
    return this.http.post('/api/v1/auth/logout', {}).pipe(tap(() => this.clear()));
  }

  clear(): void {
    this.current.set(null);
  }

  can(...permissions: Permission[]): boolean {
    const granted = this.granted();
    return permissions.some(p => granted.has(p));
  }

  owns(r: GovRequest): boolean {
    return r.createdBy != null && r.createdBy === this.current()?.id;
  }

  canEdit(r: GovRequest): boolean {
    return this.can('request:edit:all')
      || (this.can('request:edit:own') && this.owns(r) && OWNER_EDITABLE.includes(r.status));
  }

  canDelete(): boolean {
    return this.can('request:delete:all');
  }

  canWithdraw(r: GovRequest): boolean {
    return this.can('request:withdraw:own') && this.owns(r) && (r.status === 'DRAFT' || r.status === 'SUBMITTED');
  }

  canSubmitDraft(r: GovRequest): boolean {
    return this.can('request:create') && this.owns(r) && r.status === 'DRAFT';
  }

  canReview(r: GovRequest): boolean {
    return this.can('request:review', 'request:schedule') && !this.owns(r);
  }

  canResubmit(r: GovRequest): boolean {
    return this.can('request:resubmit') && this.owns(r) && r.status === 'CHANGES_REQUESTED';
  }
}

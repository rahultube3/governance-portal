import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of, tap } from 'rxjs';
import { Permission, SessionUser, User } from '../models/user.model';
import { GovRequest } from '../models/request.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly current = signal<SessionUser | null>(null);
  private readonly granted = computed(() => new Set(this.current()?.permissions ?? []));
  readonly user = this.current.asReadonly();

  constructor(private http: HttpClient) {}

  restore(): Observable<SessionUser | null> {
    return this.http.get<SessionUser>('/api/auth/me').pipe(
      catchError(() => of(null)),
      tap(u => this.current.set(u)),
    );
  }

  directory(): Observable<User[]> {
    return this.http.get<User[]>('/api/auth/users');
  }

  login(userId: number): Observable<SessionUser> {
    return this.http.post<SessionUser>('/api/auth/login', { userId }).pipe(tap(u => this.current.set(u)));
  }

  logout(): Observable<unknown> {
    return this.http.post('/api/auth/logout', {}).pipe(tap(() => this.clear()));
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
      || (this.can('request:edit:own') && this.owns(r) && (r.status === 'PENDING' || r.status === 'REWORK'));
  }

  canDelete(r: GovRequest): boolean {
    return this.can('request:delete:all')
      || (this.can('request:withdraw:own') && this.owns(r) && r.status === 'PENDING');
  }

  canReview(r: GovRequest): boolean {
    return this.can('request:review') && !this.owns(r);
  }

  canResubmit(r: GovRequest): boolean {
    return this.can('request:resubmit') && this.owns(r) && r.status === 'REWORK';
  }
}

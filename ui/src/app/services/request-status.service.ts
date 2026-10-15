import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { LifecycleStatus, RequestStatus } from '../models/request.model';

@Injectable({ providedIn: 'root' })
export class RequestStatusService {
  readonly statuses = signal<RequestStatus[]>([]);
  private loaded = false;

  constructor(private http: HttpClient) {}

  ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    this.http.get<RequestStatus[]>('/api/v1/request-statuses').subscribe(list => this.statuses.set(list));
  }

  // Keeps every page's labels current after an admin edits a status on the Reference Data page.
  replace(status: RequestStatus): void {
    this.statuses.update(list => list.map(s => (s.code === status.code ? status : s)));
  }

  isActive(code: LifecycleStatus): boolean {
    return this.statuses().find(s => s.code === code)?.active ?? true;
  }

  // Adds a status an admin just created, keeping position order.
  add(status: RequestStatus): void {
    this.statuses.update(list => [...list, status].sort((a, b) => a.position - b.position));
  }

  remove(code: LifecycleStatus): void {
    this.statuses.update(list => list.filter(s => s.code !== code));
  }

  label(code: LifecycleStatus | null | undefined): string {
    if (!code) return '';
    return this.statuses().find(s => s.code === code)?.label ?? code;
  }
}

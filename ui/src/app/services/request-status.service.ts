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

  label(code: LifecycleStatus | null | undefined): string {
    if (!code) return '';
    return this.statuses().find(s => s.code === code)?.label ?? code;
  }
}

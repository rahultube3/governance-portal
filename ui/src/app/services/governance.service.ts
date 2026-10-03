import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { GovRequest, Meta, Stats, LifecycleStatus } from '../models/request.model';

@Injectable({ providedIn: 'root' })
export class GovernanceService {
  private base = '/api/v1';

  constructor(private http: HttpClient) {}

  getMeta(): Observable<Meta> {
    return this.http.get<Meta>(`${this.base}/meta`);
  }

  getStats(): Observable<Stats> {
    return this.http.get<Stats>(`${this.base}/stats`);
  }

  list(filters: { status?: string; artifactType?: string; search?: string } = {}): Observable<GovRequest[]> {
    let params = new HttpParams();
    if (filters.status) params = params.set('status', filters.status);
    if (filters.artifactType) params = params.set('artifactType', filters.artifactType);
    if (filters.search) params = params.set('search', filters.search);
    return this.http.get<GovRequest[]>(`${this.base}/requests`, { params });
  }

  get(id: number): Observable<GovRequest> {
    return this.http.get<GovRequest>(`${this.base}/requests/${id}`);
  }

  create(req: GovRequest): Observable<GovRequest> {
    return this.http.post<GovRequest>(`${this.base}/requests`, req);
  }

  update(id: number, req: Partial<GovRequest>): Observable<GovRequest> {
    return this.http.put<GovRequest>(`${this.base}/requests/${id}`, req);
  }

  changeStatus(id: number, status: LifecycleStatus, note?: string,
               meeting?: { meetingDate: string; meetingTime: string }): Observable<GovRequest> {
    return this.http.patch<GovRequest>(`${this.base}/requests/${id}/status`, { status, note, ...meeting });
  }

  remove(id: number): Observable<{ deleted: number }> {
    return this.http.delete<{ deleted: number }>(`${this.base}/requests/${id}`);
  }
}

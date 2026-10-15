import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ManagedArtifactName, ManagedOption, ManagedReviewer, RequestStatus, ReviewerRoleCode,
} from '../models/request.model';

// The two simple Reference Data lists share one API shape.
export type OptionList = 'review-types' | 'pdlc-checkpoints';

// Reference Data admin API: every list supports add, edit, activate/deactivate and remove (refused while a
// request uses the entry); ordered lists also take a full new order.
@Injectable({ providedIn: 'root' })
export class ReferenceService {
  private base = '/api/v1';

  constructor(private http: HttpClient) {}

  options(list: OptionList): Observable<ManagedOption[]> {
    return this.http.get<ManagedOption[]>(`${this.base}/${list}`);
  }

  addOption(list: OptionList, name: string): Observable<ManagedOption> {
    return this.http.post<ManagedOption>(`${this.base}/${list}`, { name });
  }

  updateOption(list: OptionList, id: number, patch: { name?: string; active?: boolean }): Observable<ManagedOption> {
    return this.http.patch<ManagedOption>(`${this.base}/${list}/${id}`, patch);
  }

  removeOption(list: OptionList, id: number): Observable<unknown> {
    return this.http.delete(`${this.base}/${list}/${id}`);
  }

  orderOptions(list: OptionList, order: number[]): Observable<ManagedOption[]> {
    return this.http.put<ManagedOption[]>(`${this.base}/${list}/order`, { order });
  }

  referenceNames(): Observable<ManagedArtifactName[]> {
    return this.http.get<ManagedArtifactName[]>(`${this.base}/artifact-names`);
  }

  addReferenceName(body: { label: string; requiredFor: string[] }): Observable<ManagedArtifactName> {
    return this.http.post<ManagedArtifactName>(`${this.base}/artifact-names`, body);
  }

  updateReferenceName(code: string, patch: { label?: string; requiredFor?: string[]; active?: boolean }): Observable<ManagedArtifactName> {
    return this.http.patch<ManagedArtifactName>(`${this.base}/artifact-names/${code}`, patch);
  }

  removeReferenceName(code: string): Observable<unknown> {
    return this.http.delete(`${this.base}/artifact-names/${code}`);
  }

  orderReferenceNames(order: string[]): Observable<ManagedArtifactName[]> {
    return this.http.put<ManagedArtifactName[]>(`${this.base}/artifact-names/order`, { order });
  }

  reviewers(): Observable<ManagedReviewer[]> {
    return this.http.get<ManagedReviewer[]>(`${this.base}/reviewers`);
  }

  addReviewer(body: { name: string; role: ReviewerRoleCode }): Observable<ManagedReviewer> {
    return this.http.post<ManagedReviewer>(`${this.base}/reviewers`, body);
  }

  updateReviewer(id: number, patch: { name?: string; active?: boolean }): Observable<ManagedReviewer> {
    return this.http.patch<ManagedReviewer>(`${this.base}/reviewers/${id}`, patch);
  }

  removeReviewer(id: number): Observable<unknown> {
    return this.http.delete(`${this.base}/reviewers/${id}`);
  }

  addStatus(body: { label: string; meaning: string; whoActs: string }): Observable<RequestStatus> {
    return this.http.post<RequestStatus>(`${this.base}/request-statuses`, body);
  }

  updateStatus(code: string, patch: { label?: string; meaning?: string; whoActs?: string; active?: boolean }): Observable<RequestStatus> {
    return this.http.patch<RequestStatus>(`${this.base}/request-statuses/${code}`, patch);
  }

  removeStatus(code: string): Observable<unknown> {
    return this.http.delete(`${this.base}/request-statuses/${code}`);
  }
}

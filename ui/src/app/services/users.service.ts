import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ManagedUser, UserInput } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class UsersService {
  private base = '/api/v1/users';

  constructor(private http: HttpClient) {}

  list(): Observable<ManagedUser[]> {
    return this.http.get<ManagedUser[]>(this.base);
  }

  create(body: UserInput): Observable<ManagedUser> {
    return this.http.post<ManagedUser>(this.base, body);
  }

  update(id: number, patch: Partial<UserInput>): Observable<ManagedUser> {
    return this.http.patch<ManagedUser>(`${this.base}/${id}`, patch);
  }

  remove(id: number): Observable<{ deleted: number }> {
    return this.http.delete<{ deleted: number }>(`${this.base}/${id}`);
  }
}

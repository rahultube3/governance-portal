import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { User } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class UserDirectoryService {
  private readonly names = signal(new Map<number, string>());
  private loaded = false;

  constructor(private http: HttpClient) {}

  ensureLoaded(): void {
    if (!this.loaded) this.refresh();
  }

  refresh(): void {
    this.loaded = true;
    this.http.get<User[]>('/api/auth/users')
      .subscribe(list => this.names.set(new Map(list.map(u => [u.id, u.name]))));
  }

  // A NULL audit column means the row was seeded or synced by the system, or its author was deleted.
  name(id: number | null | undefined): string {
    if (id == null) return 'System';
    return this.names().get(id) ?? `User #${id}`;
  }
}

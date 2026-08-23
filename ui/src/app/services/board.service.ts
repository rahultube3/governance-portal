import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  BoardCard,
  BoardField,
  BoardFieldCreate,
  BoardFieldPatch,
  BoardSnapshot,
} from '../models/board.model';

@Injectable({ providedIn: 'root' })
export class BoardService {
  private base = '/api/board';

  constructor(private http: HttpClient) {}

  getAll(): Observable<BoardSnapshot> {
    return this.http.get<BoardSnapshot>(this.base);
  }

  createField(body: BoardFieldCreate): Observable<BoardField> {
    return this.http.post<BoardField>(`${this.base}/fields`, body);
  }

  updateField(id: number, body: BoardFieldPatch): Observable<BoardField> {
    return this.http.patch<BoardField>(`${this.base}/fields/${id}`, body);
  }

  deleteField(id: number): Observable<{ deleted: number }> {
    return this.http.delete<{ deleted: number }>(`${this.base}/fields/${id}`);
  }

  createCard(data: Record<string, unknown>): Observable<BoardCard> {
    return this.http.post<BoardCard>(`${this.base}/cards`, { data });
  }

  updateCard(id: number, patch: { data?: Record<string, unknown>; position?: number }): Observable<BoardCard> {
    return this.http.patch<BoardCard>(`${this.base}/cards/${id}`, patch);
  }

  deleteCard(id: number): Observable<{ deleted: number }> {
    return this.http.delete<{ deleted: number }>(`${this.base}/cards/${id}`);
  }
}

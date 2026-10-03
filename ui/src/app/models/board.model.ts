export type BoardFieldType = 'text' | 'number' | 'date' | 'select' | 'checkbox';

export interface BoardField {
  id: number;
  key: string;
  label: string;
  type: BoardFieldType;
  options: string[];
  position: number;
  isTitle: boolean;
  isGroup: boolean;
  createdAt: string | null;
  createdBy: number | null;
  updatedAt: string | null;
  updatedBy: number | null;
}

export interface BoardCard {
  id: number;
  data: Record<string, string | number | boolean | null>;
  position: number;
  createdAt: string;
  updatedAt: string;
  createdBy: number | null;
  updatedBy: number | null;
}

export interface BoardSnapshot {
  fields: BoardField[];
  cards: BoardCard[];
}

export interface BoardFieldCreate {
  label: string;
  type: BoardFieldType;
  options?: string[];
  isTitle?: boolean;
  isGroup?: boolean;
}

export interface BoardFieldPatch {
  label?: string;
  options?: string[];
  position?: number;
  isTitle?: boolean;
  isGroup?: boolean;
}

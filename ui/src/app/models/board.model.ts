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
}

export interface BoardCard {
  id: number;
  data: Record<string, string | number | boolean | null>;
  position: number;
  createdAt: string;
  updatedAt: string;
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

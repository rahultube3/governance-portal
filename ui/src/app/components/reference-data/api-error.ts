import { HttpErrorResponse } from '@angular/common/http';

export function apiError(e: unknown): string {
  const msg = e instanceof HttpErrorResponse ? e.error?.error : null;
  return typeof msg === 'string' ? msg : 'The request failed. Try again.';
}

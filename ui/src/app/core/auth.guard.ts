import { inject } from '@angular/core';
import { CanActivateChildFn, CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { Permission } from '../models/user.model';

export const authGuard: CanActivateChildFn = route => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.user()) return router.createUrlTree(['/login']);
  const required = route.data['permissions'] as Permission[] | undefined;
  return !required || auth.can(...required) ? true : router.createUrlTree(['/']);
};

export const guestGuard: CanActivateFn = () => {
  const user = inject(AuthService).user();
  return user ? inject(Router).createUrlTree(['/']) : true;
};

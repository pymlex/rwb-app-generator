import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideServiceWorker } from '@angular/service-worker';
import { App } from './app';

bootstrapApplication(App, {
  providers: [
    provideAnimationsAsync(),
    provideHttpClient(withInterceptors([(request, next) => {
      const token = sessionStorage.getItem('access_token');
      return next(token && request.url.startsWith('/api/')
        ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
        : request);
    }])),
    provideServiceWorker('ngsw-worker.js', { enabled: true, registrationStrategy: 'registerWhenStable:30000' })
  ]
});

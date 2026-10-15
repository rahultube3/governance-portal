import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';
import { OptionListComponent } from './option-list.component';
import { ReferenceLinksComponent } from './reference-links.component';
import { ReviewersTabComponent } from './reviewers-tab.component';
import { StatusesTabComponent } from './statuses-tab.component';

const TABS = [
  { key: 'review-types', label: 'Review Types' },
  { key: 'pdlc', label: 'PDLC Checkpoints' },
  { key: 'reference-links', label: 'Reference Links' },
  { key: 'reviewers', label: 'Reviewers' },
  { key: 'statuses', label: 'Lifecycle Statuses' },
];

// One admin page for every list behind the intake form; the open tab is kept in the URL (?tab=...).
@Component({
  selector: 'app-reference-data',
  standalone: true,
  imports: [CommonModule, OptionListComponent, ReferenceLinksComponent, ReviewersTabComponent, StatusesTabComponent],
  templateUrl: './reference-data.component.html',
  styleUrls: ['./reference-data.component.css'],
})
export class ReferenceDataComponent {
  readonly tabs = TABS;
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private tabParam = toSignal(this.route.queryParamMap.pipe(map(p => p.get('tab'))));
  tab = computed(() => TABS.some(t => t.key === this.tabParam()) ? this.tabParam()! : TABS[0].key);

  open(key: string): void {
    this.router.navigate([], { relativeTo: this.route, queryParams: { tab: key } });
  }
}

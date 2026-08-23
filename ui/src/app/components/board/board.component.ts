import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BoardService } from '../../services/board.service';
import {
  BoardCard,
  BoardField,
  BoardFieldType,
} from '../../models/board.model';

type ChartKind = 'donut' | 'bar';

interface Lane {
  key: string;
  label: string;
  cards: BoardCard[];
}

interface DonutSlice {
  label: string;
  value: number;
  color: string;
  dash: string;
  offset: number;
}

interface BarSlice {
  label: string;
  value: number;
  color: string;
  pct: number;
}

const CHART_PALETTE = [
  '#46C2CE', '#E8A33D', '#6BD08A', '#B98CE8', '#E86A5C',
  '#8497B4', '#5EC0E8', '#F0C46A', '#A8DE99', '#D48CE8',
];

const UNCATEGORIZED = '__uncategorized__';

@Component({
  selector: 'app-board',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './board.component.html',
  styleUrls: ['./board.component.css'],
})
export class BoardComponent implements OnInit {
  loading = signal(true);
  fields = signal<BoardField[]>([]);
  cards = signal<BoardCard[]>([]);

  // group by field key (default = whichever field is marked isGroup, else first select)
  groupByKey = signal<string>('');
  chartFieldKey = signal<string>('');
  chartKind = signal<ChartKind>('donut');

  drawerCard = signal<BoardCard | null>(null);
  manageOpen = signal(false);

  newFieldLabel = '';
  newFieldType: BoardFieldType = 'text';
  newFieldOptions = '';

  addingLaneFor = signal<string | null>(null); // groupByKey when adding a card inline; value is lane key
  newCardTitle = '';

  addingNewLane = signal(false);
  newLaneName = '';

  draggingCardId: number | null = null;

  constructor(private svc: BoardService) {}

  ngOnInit(): void {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.svc.getAll().subscribe(snap => {
      this.fields.set(snap.fields);
      this.cards.set(snap.cards);
      this.initDefaults();
      this.loading.set(false);
    });
  }

  private initDefaults() {
    const fs = this.fields();
    const group = fs.find(f => f.isGroup) ?? fs.find(f => f.type === 'select');
    if (group && !this.groupByKey()) this.groupByKey.set(group.key);
    if (!this.chartFieldKey()) this.chartFieldKey.set(group?.key ?? fs.find(f => f.type === 'select')?.key ?? '');
  }

  titleField = computed<BoardField | undefined>(() =>
    this.fields().find(f => f.isTitle) ?? this.fields().find(f => f.type === 'text'));

  groupField = computed<BoardField | undefined>(() =>
    this.fields().find(f => f.key === this.groupByKey()));

  groupableFields = computed<BoardField[]>(() =>
    this.fields().filter(f => f.type === 'select' || f.type === 'text'));

  chartableFields = computed<BoardField[]>(() =>
    this.fields().filter(f => f.type === 'select' || f.type === 'text' || f.type === 'checkbox'));

  visibleCardFields = computed<BoardField[]>(() => {
    const title = this.titleField()?.key;
    const group = this.groupField()?.key;
    return this.fields()
      .filter(f => f.key !== title && f.key !== group)
      .slice(0, 3);
  });

  lanes = computed<Lane[]>(() => {
    const g = this.groupField();
    if (!g) return [];
    const cards = this.cards();
    const options = g.type === 'select' && g.options.length
      ? [...g.options]
      : Array.from(new Set(cards.map(c => String(c.data[g.key] ?? '')).filter(v => v)));
    const map = new Map<string, BoardCard[]>();
    for (const opt of options) map.set(opt, []);
    map.set(UNCATEGORIZED, []);
    for (const c of cards) {
      const v = c.data[g.key];
      const key = v == null || v === '' ? UNCATEGORIZED : String(v);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(c);
    }
    const lanes: Lane[] = [];
    for (const [key, list] of map) {
      if (key === UNCATEGORIZED && !list.length) continue;
      lanes.push({
        key,
        label: key === UNCATEGORIZED ? 'Uncategorized' : key,
        cards: list.sort((a, b) => a.position - b.position),
      });
    }
    return lanes;
  });

  totalCards = computed(() => this.cards().length);

  overdueCount = computed(() => {
    const dueField = this.fields().find(f => f.type === 'date' && /due/i.test(f.label))
      ?? this.fields().find(f => f.type === 'date');
    const doneValues = new Set(['Done', 'Completed', 'Closed']);
    if (!dueField) return 0;
    const today = new Date().toISOString().slice(0, 10);
    const g = this.groupField();
    return this.cards().filter(c => {
      const d = c.data[dueField.key];
      if (!d) return false;
      const gv = g ? String(c.data[g.key] ?? '') : '';
      if (doneValues.has(gv)) return false;
      return String(d) < today;
    }).length;
  });

  completedThisWeek = computed(() => {
    const g = this.groupField();
    if (!g) return 0;
    const doneValues = new Set(['Done', 'Completed', 'Closed']);
    const weekAgo = new Date(Date.now() - 7 * 86400 * 1000).toISOString();
    return this.cards().filter(c =>
      doneValues.has(String(c.data[g.key] ?? '')) && c.updatedAt >= weekAgo).length;
  });

  chartCounts = computed(() => {
    const key = this.chartFieldKey();
    const field = this.fields().find(f => f.key === key);
    if (!field) return [] as { label: string; value: number }[];
    const map = new Map<string, number>();
    if (field.type === 'select' && field.options.length) {
      for (const o of field.options) map.set(o, 0);
    }
    for (const c of this.cards()) {
      const v = c.data[key];
      let label: string;
      if (field.type === 'checkbox') label = v ? 'Yes' : 'No';
      else if (v == null || v === '') label = 'Empty';
      else label = String(v);
      map.set(label, (map.get(label) ?? 0) + 1);
    }
    return Array.from(map.entries()).map(([label, value]) => ({ label, value }));
  });

  donutSlices = computed<DonutSlice[]>(() => {
    const items = this.chartCounts().filter(i => i.value > 0);
    const total = items.reduce((s, i) => s + i.value, 0);
    if (!total) return [];
    const C = 2 * Math.PI * 42;
    let acc = 0;
    return items.map((it, idx) => {
      const frac = it.value / total;
      const dash = `${frac * C} ${C}`;
      const offset = -acc * C;
      acc += frac;
      return {
        label: it.label,
        value: it.value,
        color: CHART_PALETTE[idx % CHART_PALETTE.length],
        dash,
        offset,
      };
    });
  });

  barSlices = computed<BarSlice[]>(() => {
    const items = this.chartCounts();
    const max = Math.max(1, ...items.map(i => i.value));
    return items.map((it, idx) => ({
      label: it.label,
      value: it.value,
      color: CHART_PALETTE[idx % CHART_PALETTE.length],
      pct: Math.round((it.value / max) * 100),
    }));
  });

  chartTotal = computed(() => this.chartCounts().reduce((s, i) => s + i.value, 0));

  // ---------- interactions ----------
  setGroupBy(key: string) { this.groupByKey.set(key); }
  setChartField(key: string) { this.chartFieldKey.set(key); }
  setChartKind(k: ChartKind) { this.chartKind.set(k); }

  openCard(card: BoardCard) { this.drawerCard.set({ ...card, data: { ...card.data } }); }
  closeDrawer() { this.drawerCard.set(null); }

  onDrawerFieldChange(key: string, value: unknown) {
    const c = this.drawerCard();
    if (!c) return;
    this.drawerCard.set({ ...c, data: { ...c.data, [key]: value as any } });
  }

  saveDrawer() {
    const c = this.drawerCard();
    if (!c) return;
    this.svc.updateCard(c.id, { data: c.data }).subscribe(updated => {
      this.cards.update(list => list.map(x => x.id === updated.id ? updated : x));
      this.drawerCard.set(null);
    });
  }

  deleteDrawerCard() {
    const c = this.drawerCard();
    if (!c) return;
    if (!confirm('Delete this card?')) return;
    this.svc.deleteCard(c.id).subscribe(() => {
      this.cards.update(list => list.filter(x => x.id !== c.id));
      this.drawerCard.set(null);
    });
  }

  // inline add card
  beginAddCard(laneKey: string) {
    this.addingLaneFor.set(laneKey);
    this.newCardTitle = '';
    setTimeout(() => {
      const el = document.querySelector<HTMLInputElement>('.new-card-input');
      el?.focus();
    });
  }

  commitAddCard(laneKey: string) {
    const title = this.newCardTitle.trim();
    if (!title) { this.addingLaneFor.set(null); return; }
    const titleKey = this.titleField()?.key;
    const groupKey = this.groupField()?.key;
    const data: Record<string, unknown> = {};
    if (titleKey) data[titleKey] = title;
    if (groupKey && laneKey !== UNCATEGORIZED) data[groupKey] = laneKey;
    this.svc.createCard(data).subscribe(created => {
      this.cards.update(list => [...list, created]);
      this.newCardTitle = '';
      this.addingLaneFor.set(null);
    });
  }

  cancelAddCard() {
    this.addingLaneFor.set(null);
    this.newCardTitle = '';
  }

  // add new lane (only for select group field)
  beginAddLane() {
    if (this.groupField()?.type !== 'select') return;
    this.addingNewLane.set(true);
    this.newLaneName = '';
    setTimeout(() => {
      const el = document.querySelector<HTMLInputElement>('.new-lane-input');
      el?.focus();
    });
  }

  commitAddLane() {
    const name = this.newLaneName.trim();
    const g = this.groupField();
    if (!name || !g || g.type !== 'select') { this.addingNewLane.set(false); return; }
    if (g.options.includes(name)) {
      this.addingNewLane.set(false);
      return;
    }
    const next = [...g.options, name];
    this.svc.updateField(g.id, { options: next }).subscribe(updated => {
      this.fields.update(list => list.map(f => f.id === updated.id ? updated : f));
      this.addingNewLane.set(false);
      this.newLaneName = '';
    });
  }

  cancelAddLane() {
    this.addingNewLane.set(false);
    this.newLaneName = '';
  }

  // drag-and-drop between lanes
  onDragStart(ev: DragEvent, card: BoardCard) {
    this.draggingCardId = card.id;
    ev.dataTransfer?.setData('text/plain', String(card.id));
    ev.dataTransfer!.effectAllowed = 'move';
  }

  onDragOver(ev: DragEvent) {
    ev.preventDefault();
    ev.dataTransfer!.dropEffect = 'move';
  }

  onDrop(ev: DragEvent, laneKey: string) {
    ev.preventDefault();
    const id = this.draggingCardId ?? Number(ev.dataTransfer?.getData('text/plain'));
    this.draggingCardId = null;
    if (!id) return;
    const card = this.cards().find(c => c.id === id);
    const g = this.groupField();
    if (!card || !g) return;
    const newValue = laneKey === UNCATEGORIZED ? '' : laneKey;
    if (String(card.data[g.key] ?? '') === newValue) return;
    const patchData = { ...card.data, [g.key]: newValue };
    // optimistic update
    this.cards.update(list => list.map(c => c.id === id ? { ...c, data: patchData as any } : c));
    this.svc.updateCard(id, { data: { [g.key]: newValue } }).subscribe({
      next: updated => this.cards.update(list => list.map(c => c.id === updated.id ? updated : c)),
      error: () => this.load(),
    });
  }

  // manage fields
  openManage() { this.manageOpen.set(true); }
  closeManage() {
    this.manageOpen.set(false);
    this.newFieldLabel = '';
    this.newFieldType = 'text';
    this.newFieldOptions = '';
  }

  addField() {
    const label = this.newFieldLabel.trim();
    if (!label) return;
    const options = this.newFieldType === 'select'
      ? this.newFieldOptions.split(',').map(s => s.trim()).filter(Boolean)
      : [];
    this.svc.createField({ label, type: this.newFieldType, options }).subscribe(f => {
      this.fields.update(list => [...list, f]);
      this.newFieldLabel = '';
      this.newFieldOptions = '';
    });
  }

  updateFieldLabel(f: BoardField, label: string) {
    if (!label.trim() || label === f.label) return;
    this.svc.updateField(f.id, { label: label.trim() }).subscribe(updated =>
      this.fields.update(list => list.map(x => x.id === updated.id ? updated : x)));
  }

  updateFieldOptions(f: BoardField, raw: string) {
    const opts = raw.split(',').map(s => s.trim()).filter(Boolean);
    this.svc.updateField(f.id, { options: opts }).subscribe(updated =>
      this.fields.update(list => list.map(x => x.id === updated.id ? updated : x)));
  }

  deleteField(f: BoardField) {
    if (f.isTitle || f.isGroup) return;
    if (!confirm(`Delete field "${f.label}"? Values will be removed from all cards.`)) return;
    this.svc.deleteField(f.id).subscribe(() =>
      this.fields.update(list => list.filter(x => x.id !== f.id)));
  }

  setTitleField(f: BoardField) {
    if (f.type !== 'text') { alert('Title must be a text field'); return; }
    this.svc.updateField(f.id, { isTitle: true }).subscribe(() => this.load());
  }

  setGroupField(f: BoardField) {
    if (f.type !== 'select') { alert('Grouping field must be a select field'); return; }
    this.svc.updateField(f.id, { isGroup: true }).subscribe(() => {
      this.groupByKey.set(f.key);
      this.load();
    });
  }

  laneColor(idx: number): string {
    return CHART_PALETTE[idx % CHART_PALETTE.length];
  }

  cardTitle(c: BoardCard): string {
    const tf = this.titleField();
    if (!tf) return `Card #${c.id}`;
    return String(c.data[tf.key] ?? `Card #${c.id}`);
  }

  displayValue(c: BoardCard, f: BoardField): string {
    const v = c.data[f.key];
    if (v == null || v === '') return '—';
    if (f.type === 'checkbox') return v ? '✓' : '—';
    return String(v);
  }

  drawerFields = computed(() => this.fields());

  trackFieldId = (_: number, f: BoardField) => f.id;
  trackCardId = (_: number, c: BoardCard) => c.id;
  trackLaneKey = (_: number, l: Lane) => l.key;
}

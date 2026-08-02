import { Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface Standard {
  code: string;
  title: string;
  summary: string;
  appliesTo: string[];
  url: string;
}

interface QuickLink {
  label: string;
  note: string;
  url: string;
}

interface TemplateDoc {
  name: string;
  kind: string;
  note: string;
  url: string;
}

interface Faq {
  q: string;
  a: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  error?: boolean;
}

@Component({
  selector: 'app-help',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './help.component.html',
  styleUrls: ['./help.component.css'],
})
export class HelpComponent {
  @ViewChild('thread') private thread?: ElementRef<HTMLDivElement>;

  chatMessages: ChatMessage[] = [];
  chatInput = '';
  chatBusy = false;

  starterQuestions: string[] = [
    'When do I need an ARB review?',
    'Where is the ADR template?',
    'What does REWORK mean?',
    'What are the rules for a new Kafka topic?',
  ];

  async sendChat(preset?: string): Promise<void> {
    const q = (preset ?? this.chatInput).trim();
    if (!q || this.chatBusy) return;
    this.chatInput = '';
    this.chatBusy = true;

    this.chatMessages.push({ role: 'user', text: q });
    const payload = this.chatMessages
      .filter(m => !m.error && m.text)
      .map(m => ({ role: m.role, content: m.text }));
    const assistant: ChatMessage = { role: 'assistant', text: '' };
    this.chatMessages.push(assistant);
    this.scrollThread();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: payload }),
      });
      if (!res.ok || !res.body) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.error ?? `Request failed (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const events = buf.split('\n\n');
        buf = events.pop() ?? '';
        for (const evt of events) {
          const line = evt.trim();
          if (!line.startsWith('data:')) continue;
          const msg = JSON.parse(line.slice(5));
          if (msg.error) throw new Error(msg.error);
          if (msg.text) {
            assistant.text += msg.text;
            this.scrollThread();
          }
        }
      }
      if (!assistant.text) throw new Error('No response received. Try again.');
    } catch (e) {
      assistant.error = true;
      assistant.text = e instanceof Error ? e.message : 'Something went wrong. Try again.';
    } finally {
      this.chatBusy = false;
      this.scrollThread();
    }
  }

  clearChat(): void {
    if (!this.chatBusy) this.chatMessages = [];
  }

  // Escape first, then linkify — the resulting HTML contains only text and <a>/<br>.
  render(text: string): string {
    const esc = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    return esc
      .replace(/https?:\/\/[^\s<)]+[^\s<).,]/g, u =>
        `<a href="${u}" target="_blank" rel="noopener">${u}</a>`)
      .replace(/\n/g, '<br>');
  }

  private scrollThread(): void {
    setTimeout(() => {
      const el = this.thread?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
  // Sample content — replace urls and text with your company's own sources.
  standards: Standard[] = [
    {
      code: 'STD-001',
      title: 'ARB Intake & Review',
      summary:
        'When a review is required, what evidence to attach, review board quorum, and the SLA for each lifecycle stage.',
      appliesTo: ['ARB', 'All intakes'],
      url: 'https://wiki.example.com/architecture/standards/arb-intake-review',
    },
    {
      code: 'STD-002',
      title: 'Architecture Decision Records',
      summary:
        'Every significant decision gets an ADR: context, options considered, decision, and consequences — filed with the owning app.',
      appliesTo: ['ADR'],
      url: 'https://wiki.example.com/architecture/standards/adr',
    },
    {
      code: 'STD-003',
      title: 'API & Integration Design',
      summary:
        'REST and contract conventions, versioning and deprecation policy, error model, and gateway onboarding requirements.',
      appliesTo: ['ARB', 'ADR'],
      url: 'https://wiki.example.com/architecture/standards/api-design',
    },
    {
      code: 'STD-004',
      title: 'Data Governance',
      summary:
        'Data classification, ownership, retention, and the data-contract checklist required before any new store or feed goes live.',
      appliesTo: ['Data'],
      url: 'https://wiki.example.com/architecture/standards/data-governance',
    },
    {
      code: 'STD-005',
      title: 'Messaging & Event Streams',
      summary:
        'Topic naming, schema registry usage, compatibility rules, and delivery guarantees for event-driven integrations.',
      appliesTo: ['Messaging'],
      url: 'https://wiki.example.com/architecture/standards/messaging-events',
    },
    {
      code: 'STD-006',
      title: 'AI/ML Model Governance',
      summary:
        'Model risk tiering, evaluation evidence, human-oversight requirements, and the model card that accompanies every deployment.',
      appliesTo: ['AI/ML'],
      url: 'https://wiki.example.com/architecture/standards/ai-ml-governance',
    },
  ];

  quickLinks: QuickLink[] = [
    { label: 'Architecture wiki', note: 'Standards, reference architectures, past decisions', url: 'https://wiki.example.com/architecture' },
    { label: 'ARB meeting calendar', note: 'Review slots, agendas, and minutes', url: 'https://calendar.example.com/arb' },
    { label: 'TrackIT', note: 'Change and demand management', url: 'https://trackit.example.com' },
    { label: 'Reference architectures repo', note: 'Approved patterns and golden paths', url: 'https://git.example.com/architecture/reference' },
    { label: '#arch-governance', note: 'Questions, triage, and announcements', url: 'https://teams.example.com/channels/arch-governance' },
  ];

  templates: TemplateDoc[] = [
    { name: 'ADR template', kind: 'Markdown', note: 'Context / options / decision / consequences', url: 'https://wiki.example.com/architecture/templates/adr.md' },
    { name: 'ARB review deck', kind: 'Slides', note: 'Required sections for a board walkthrough', url: 'https://wiki.example.com/architecture/templates/arb-deck' },
    { name: 'Data contract template', kind: 'YAML', note: 'Schema, ownership, SLAs, classification', url: 'https://wiki.example.com/architecture/templates/data-contract.yaml' },
    { name: 'Threat model checklist', kind: 'PDF', note: 'Complete before security sign-off', url: 'https://wiki.example.com/architecture/templates/threat-model.pdf' },
    { name: 'Model card template', kind: 'Markdown', note: 'Required for every AI/ML deployment', url: 'https://wiki.example.com/architecture/templates/model-card.md' },
  ];

  faqs: Faq[] = [
    {
      q: 'When do I need an architecture review?',
      a: 'Any new application, new external integration, new data store or feed, or a material change to an approved design. If in doubt, submit — triage takes less than a day.',
    },
    {
      q: 'What happens after I submit an intake?',
      a: 'Your request starts as PENDING, is triaged to the right reviewers, and moves through APPROVED FB and APPROVED EA. You can follow every stage from the Requests page.',
    },
    {
      q: 'My request came back as REWORK — now what?',
      a: 'Reviewer notes on the request detail page list what needs to change. Update the artifact, then resubmit from the same request so the history stays in one place.',
    },
    {
      q: 'What evidence should I attach?',
      a: 'A current architecture diagram, the relevant template from this page filled in, and links to the App ID and TrackIT records. Incomplete evidence is the most common cause of rework.',
    },
  ];
}

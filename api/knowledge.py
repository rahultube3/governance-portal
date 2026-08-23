"""
Sample governance document corpus for the /api/chat assistant.
Replace the document contents and URLs with your company's own sources —
keep the structure (id, title, url, content) so the system prompt builder works.
"""

DOCUMENTS: list[dict[str, str]] = [
    {
        "id": "STD-001",
        "title": "ARB Intake & Review Standard",
        "url": "https://wiki.example.com/architecture/standards/arb-intake-review",
        "content": (
            "An architecture review is required for: any new application or service, any new "
            "external integration, any new data store or feed, and any material change to a "
            "previously approved design. Intakes are submitted through the Governance Portal "
            "and triaged within one business day.\n"
            "Required evidence: a current architecture diagram, the relevant template filled in, "
            "and links to the App ID and TrackIT records. Incomplete evidence is the most common "
            "cause of REWORK.\n"
            "Lifecycle: PENDING -> APPROVED FB (business-unit governance) -> APPROVED EA "
            "(enterprise architecture endorsement). FOLLOW UP means reviewers need more "
            "information; REWORK means the artifact must be revised and resubmitted on the same "
            "request so history stays in one place.\n"
            "SLAs: triage within 1 business day, first review within 5 business days, rework "
            "re-review within 3 business days. The review board meets weekly; quorum is three "
            "reviewers including one EA governance representative."
        ),
    },
    {
        "id": "STD-002",
        "title": "Architecture Decision Records Standard",
        "url": "https://wiki.example.com/architecture/standards/adr",
        "content": (
            "Every significant architecture decision gets an ADR filed with the owning "
            "application. Significant means: hard to reverse, affects more than one team, or "
            "deviates from a reference architecture.\n"
            "ADRs follow the template: Context, Options considered, Decision, Consequences. "
            "Keep them short (one to two pages) and write them at decision time, not after "
            "delivery. ADRs are submitted through the portal as an ADR Submission artifact and "
            "reviewed in the same lifecycle as other intakes."
        ),
    },
    {
        "id": "STD-003",
        "title": "API & Integration Design Standard",
        "url": "https://wiki.example.com/architecture/standards/api-design",
        "content": (
            "REST APIs use versioned base paths (/v1), plural resource nouns, and the standard "
            "error envelope (code, message, traceId). Breaking changes require a new major "
            "version and a 6-month deprecation window for the old one.\n"
            "All external-facing APIs onboard through the API gateway; direct service-to-service "
            "exposure outside the mesh is not permitted. Contract-first design is required: the "
            "OpenAPI spec is reviewed before implementation starts."
        ),
    },
    {
        "id": "STD-004",
        "title": "Data Governance Standard",
        "url": "https://wiki.example.com/architecture/standards/data-governance",
        "content": (
            "Every new data store or feed needs a data contract before go-live: schema, owner, "
            "classification, retention, and SLAs. Data is classified as Public, Internal, "
            "Confidential, or Restricted; Restricted data requires encryption at rest and in "
            "transit plus access reviews every quarter.\n"
            "Retention defaults: transactional data 7 years, logs 13 months, analytics copies 25 "
            "months, unless a regulation says otherwise. Data intakes are submitted as a Data "
            "Architecture Intake Request in the portal."
        ),
    },
    {
        "id": "STD-005",
        "title": "Messaging & Event Streams Standard",
        "url": "https://wiki.example.com/architecture/standards/messaging-events",
        "content": (
            "Topics are named domain.entity.event (past tense), e.g. brokerage.trade.settled. "
            "All schemas are registered in the schema registry with BACKWARD compatibility as "
            "the default; FULL compatibility is required for topics with more than three "
            "consumers.\n"
            "Delivery is at-least-once; consumers must be idempotent. Event payloads carry "
            "eventId, occurredAt, and producer fields. Messaging intakes are submitted as a "
            "Messaging & Streaming Architecture Intake Request."
        ),
    },
    {
        "id": "STD-006",
        "title": "AI/ML Model Governance Standard",
        "url": "https://wiki.example.com/architecture/standards/ai-ml-governance",
        "content": (
            "Models are risk-tiered: Tier 1 (customer-impacting or regulated decisions), Tier 2 "
            "(internal decisioning), Tier 3 (productivity/experimentation). Tier 1 and 2 "
            "deployments require a model card, documented evaluation evidence, and a named "
            "human-oversight owner before approval.\n"
            "All AI/ML intakes are submitted as an AI/ML Architecture Intake Request and "
            "reviewed against this standard. Generative AI use with Confidential or Restricted "
            "data requires explicit EA governance sign-off."
        ),
    },
    {
        "id": "REF-001",
        "title": "Portal reference: links, templates, contacts",
        "url": "https://wiki.example.com/architecture",
        "content": (
            "Quick links: Architecture wiki (https://wiki.example.com/architecture), ARB meeting "
            "calendar (https://calendar.example.com/arb), TrackIT (https://trackit.example.com), "
            "reference architectures repo (https://git.example.com/architecture/reference), "
            "#arch-governance channel (https://teams.example.com/channels/arch-governance).\n"
            "Templates: ADR template (Markdown, https://wiki.example.com/architecture/templates/adr.md), "
            "ARB review deck (Slides, https://wiki.example.com/architecture/templates/arb-deck), "
            "data contract template (YAML, https://wiki.example.com/architecture/templates/data-contract.yaml), "
            "threat model checklist (PDF, https://wiki.example.com/architecture/templates/threat-model.pdf), "
            "model card template (Markdown, https://wiki.example.com/architecture/templates/model-card.md).\n"
            "Contacts: ask in #arch-governance, email governance@example.com, or join EA office "
            "hours Thursdays 2-3 PM ET."
        ),
    },
]


def build_system_prompt() -> str:
    docs = "\n\n".join(
        f"<document id=\"{d['id']}\" title=\"{d['title']}\" url=\"{d['url']}\">\n"
        f"{d['content']}\n</document>"
        for d in DOCUMENTS
    )
    return (
        "You are the governance assistant for the Governance Portal help center. "
        "You answer questions from engineers and architects about the governance standards, "
        "templates, links, and review process, using ONLY the documents below.\n\n"
        "Rules:\n"
        "- Answer in plain text, no markdown formatting. Keep answers to 2-6 sentences.\n"
        "- When your answer draws on a standard, cite its id (e.g. STD-004) and include its URL.\n"
        "- If the documents don't contain the answer, say so and point the user to the "
        "#arch-governance channel (https://teams.example.com/channels/arch-governance).\n"
        "- Questions unrelated to architecture governance are out of scope; say so briefly.\n\n"
        f"{docs}"
    )


SYSTEM_PROMPT: str = build_system_prompt()

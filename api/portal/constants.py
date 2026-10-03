ARTIFACT_TYPES = [
    "Architecture Review Board (ARB) Intake Request",
    "Data Architecture Intake Request",
    "Architecture Decision Record (ADR) Submission",
    "Messaging & Streaming Architecture Intake Request",
    "AI/ML Architecture Intake Request",
]

PDLC_CHECKPOINTS = [
    "Inception", "Elaboration", "Construction", "Delivery"
]

# Request status lookup, synced into `request_statuses` on startup: (code, label, meaning, who acts).
REQUEST_STATUSES = [
    ("DRAFT",                     "Draft",                     "Saved, not submitted",                            "Requestor"),
    ("SUBMITTED",                 "Submitted",                 "Waiting for a reviewer to pick it up",            "Reviewer"),
    ("IN_REVIEW",                 "In Review",                 "Reviewer is assessing it",                        "Reviewer"),
    ("CHANGES_REQUESTED",         "Changes Requested",         "Sent back for changes",                           "Requestor"),
    ("SCHEDULED",                 "Scheduled",                 "Booked for an Architecture Review Board meeting", "Admin / Chief Architect / Reviewer"),
    ("CHIEF_ARCHITECTURE_REVIEW", "Chief Architecture Review", "Escalated for final architecture sign-off",       "Chief Architect"),
    ("APPROVED",                  "Approved",                  "Final approval",                                  "Admin / Chief Architect / Reviewer"),
    ("APPROVED_WITH_CONDITIONS",  "Approved with Conditions",  "Approved, with conditions attached",              "Admin / Chief Architect / Reviewer"),
    ("REJECTED",                  "Rejected",                  "Final rejection",                                 "Admin / Chief Architect / Reviewer"),
    ("WITHDRAWN",                 "Withdrawn",                 "Cancelled by the Requestor",                      "Requestor"),
]

# The API enforces these codes, so the catalog lives in code and is synced into the
# `permissions` table on startup; which role holds which permission lives only in the DB.
PERMISSION_CATALOG = [
    ("request:create",       "Requests",       "Create requests",            "Submit new intake requests."),
    ("request:view:own",     "Requests",       "View own requests",          "See requests you submitted."),
    ("request:view:all",     "Requests",       "View all requests",          "See every request in the portal."),
    ("request:edit:own",     "Requests",       "Edit own requests",          "Edit your own request while DRAFT, SUBMITTED or CHANGES_REQUESTED. Review fields excluded."),
    ("request:edit:all",     "Requests",       "Edit any request",           "Edit any request, including status, review dates and comments."),
    ("request:withdraw:own", "Requests",       "Withdraw own requests",      "Withdraw your own request while it is DRAFT or SUBMITTED."),
    ("request:delete:all",   "Requests",       "Delete any request",         "Permanently delete any request."),
    ("request:resubmit",     "Review",         "Resubmit after changes",      "Send your own request back to SUBMITTED after changes were requested."),
    ("request:review",       "Review",         "Review requests",            "Approve, reject or send back other people's requests."),
    ("request:schedule",     "Review",         "Schedule ARB meetings",      "Move other people's requests to SCHEDULED and set or change the ARB meeting date and time."),
    ("board:card:edit",      "Team Board",     "Edit board cards",           "Add, edit, move and delete Team Board cards."),
    ("board:field:manage",   "Team Board",     "Manage board fields",        "Add, rename and delete Team Board fields and lanes."),
    ("calendar:view",        "ARB Calendar",   "View ARB calendar",          "Open the Calendar of ARB meetings."),
    ("insights:view",        "Insights",       "View insights",              "Open the Insights scorecard."),
    ("insights:export",      "Insights",       "Export insights",            "Download Insights data as CSV."),
    ("user:manage",          "Administration", "Manage users",               "Add, rename and delete users and set their group."),
    ("role:assign",          "Administration", "Assign permissions",         "Edit the permission matrix and create roles."),
]

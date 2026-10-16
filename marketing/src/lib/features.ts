// Every feature the app has. `plan` names a plans.json feature, so its tag comes from the plan that
// includes it; features without one are on every plan. Descriptions say only what the code does today.
import { plans } from "./plans"

export type Group = "Writing" | "Checking" | "Publishing" | "Teams and control"
export type Feature = { title: string; body: string; group: Group; plan?: string }

const maxReviewers = Math.max(...plans.map((p) => p.limits.reviewers_required ?? 0))

export const FEATURES: Feature[] = [
  { group: "Writing", plan: "outline", title: "Outlines from your notes", body: "Title, slug, summary, tags, TL;DR and sections, drafted from the writer's notes. Every field is editable." },
  { group: "Writing", plan: "draft", title: "Drafts in your components", body: "The body streams in as MDX, using only the components your blog declares." },
  { group: "Writing", plan: "brand_voice", title: "One house voice", body: "A shared voice guide and component guide, used in every draft by every writer." },
  { group: "Writing", plan: "thumbnails", title: "Diagram thumbnails", body: "An architecture diagram of the system in the post, drawn in your blog's palette." },
  { group: "Writing", title: "Built-in preview", body: "Read the post the way it will look, rendered by Masthead. No dev server or deploy needed." },
  { group: "Checking", plan: "confidentiality_check", title: "Confidentiality and fact check", body: "Unapproved names, internal hosts, secrets, security weaknesses, personal data and numbers that aren't in the notes. The MDX is compiled too." },
  { group: "Checking", plan: "review_workflow", title: "Reviewer sign-off", body: "Someone other than the author approves each post. An edit after approval needs approving again." },
  { group: "Checking", plan: "approval_rules", title: "Approval rules", body: `Require up to ${maxReviewers} approvals before a post on a blog can ship.` },
  { group: "Publishing", plan: "pull_requests", title: "A pull request per post", body: "The post and its thumbnail land on their own branch. Protected branches stay protected." },
  { group: "Publishing", plan: "scheduling", title: "Scheduled publishing", body: "Pick a date. The post goes out when it arrives." },
  { group: "Publishing", plan: "campaigns", title: "Campaigns and series", body: "Group a launch week, or number a series so each part carries its place in it." },
  { group: "Publishing", plan: "distribution_copy", title: "Distribution copy", body: "A LinkedIn post, an X thread and a newsletter blurb for every post, linked to it." },
  { group: "Teams and control", plan: "roles", title: "Roles", body: "Owner, editor, writer and reviewer, each with the access the job needs." },
  { group: "Teams and control", plan: "audit_log", title: "Audit log", body: "A record of every draft, check, approval, publish and membership change." },
  { group: "Teams and control", title: "Your Anthropic key", body: "Every model call runs on your key, billed by Anthropic at Anthropic's rates." },
  { group: "Teams and control", title: "Spend per post", body: "What each post cost in model usage, and the month's total for the workspace." },
  { group: "Teams and control", plan: "sso", title: "Single sign-on", body: "SAML sign-in for your whole company." },
  { group: "Teams and control", plan: "priority_support", title: "Priority support", body: "Questions from Business workspaces go to the front of the queue." },
]

export const GROUPS: Group[] = ["Writing", "Checking", "Publishing", "Teams and control"]

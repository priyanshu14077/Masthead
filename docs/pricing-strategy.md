# Masthead pricing strategy

Status: draft for the founder. Competitor prices checked October 2026. Nothing here is legal or tax advice.

## 1. Positioning and value metric

Masthead sells a publishing desk, not AI output. Customers bring their own Anthropic key, so tokens cannot be the value metric. The value grows with the number of people who write and sign off on posts. That makes the seat the right unit.

Per-seat pricing suits DevRel buyers because:

- DevRel budgets are planned per head. A manager can say "4 seats at $19" without forecasting usage.
- It matches how competitors bill (Jasper, Writer, GitBook users), so procurement has a reference point.
- Price is predictable. Usage-based billing on top of a separate Anthropic bill would mean two variable invoices.

**What is a seat.** A seat is anyone who can create or edit a post: owner, editor, writer.

**Recommendation on reviewers and viewers.**

| Role | Billed? | Reason |
| --- | --- | --- |
| Owner, editor, writer | Yes | They create the value. |
| Reviewer (sign-off only, can comment, cannot edit) | Free, capped | Sign-off from engineers, legal and security is the core safety story. Charging for it pushes teams to skip review. |
| Viewer (read-only) | Free, unlimited | Costs nothing and spreads the product inside the company. |

Cap free reviewers at 2 per paid seat on Team and leave them uncapped on Business. Ghost uses a similar rule: contributors do not count toward staff limits ([Ghost FAQ](https://ghost.org/faq/views-and-staff-users)). A reviewer who starts editing should be prompted to take a paid seat.

## 2. Tier design

| Tier | Who it is for | Why it exists |
| --- | --- | --- |
| Free | One DevRel engineer trying it on their own blog | Proves the idea-to-PR loop with zero cost to Masthead, since AI runs on their key. |
| Team, $19/seat | A DevRel team of 2 to 15 | Collaboration: review, roles, scheduling, campaigns, shared voice. |
| Business, $39/seat | Companies with legal or security review rules | Governance: approval rules, audit log, SSO. These are what procurement asks for. |

### Proposed changes to `plans.json` (not applied)

| Change | Current | Proposed | Reason |
| --- | --- | --- | --- |
| Move `distribution_copy` to Free | Team only | All plans | It is part of the core pipeline, costs Masthead nothing under BYOK, and the full loop is the best demo. Team should sell collaboration, not a missing step. |
| Define what a post is | `posts_per_month: 5` | Count a post when its pull request is opened | Drafting and rework stay unlimited. Users are not punished for exploring. |
| Add free reviewer and viewer rules | none | `free_reviewers_per_seat: 2` on Team, `null` on Business; viewers unlimited | See section 1. |
| Rename `reviewers_required` | 0 / 1 / 3 | `max_required_reviewers` | The current name reads as a requirement, not a ceiling. |
| Team seat cap | 50 | 25 | A 25+ seat DevRel org will want SSO and audit. The cap nudges them to Business. |
| Add trial field | none | `trial_days: 14` on Team | Makes the trial a plan property the app and Stripe both read. |
| Define priority support | `priority_support` | "Reply within 1 business day" | A solo founder cannot promise 24/7. Say what it means. |

Prices stay at $19 and $39 for launch. See section 8 for the price test.

### Free-plan abuse

The marginal AI cost of a free user is zero to Masthead because of BYOK. The real abuse is a team running on several Free workspaces to avoid paying for seats. Guards:

- Bind a repo to one workspace. A second workspace cannot connect a repo that is already connected.
- Limit Free to one workspace per GitHub organisation.
- Free has no roles, so a shared login is the only workaround. Shared GitHub logins are visible in commit history and are rare in companies.

### Upgrade triggers

Show the upgrade prompt at these moments, in this order of strength:

1. Inviting a second writer (needs Team).
2. Asking a colleague to review before publish (needs Team).
3. Scheduling a post or creating a series.
4. Hitting the 5th post in a month.
5. Connecting a second repo.
6. For Business: turning on SSO, asking for an audit export, or setting per-repo required reviewers.

## 3. Competitor and comparable pricing

Date checked: October 2026. Prices are USD and taken from official pages unless noted.

| Product | Plan | Price | Unit | What's included | Source |
| --- | --- | --- | --- | --- | --- |
| Jasper | Pro | $69 monthly, $59 annual | per seat/month | 7-day trial, 2 brand voices, image generation | [jasper.ai/pricing](https://www.jasper.ai/pricing) |
| Jasper | Business | Custom | contract | Unlimited brand voices, SSO, API | [jasper.ai/pricing](https://www.jasper.ai/pricing) |
| Writer | Starter | $39 monthly, $29 annual (see note) | per user/month | Up to 5 users, 14-day trial, no card | [writer.com/plans](https://writer.com/plans) |
| Copy.ai | Chat | $29 monthly, $24 annual | per workspace, 5 seats | Chat on OpenAI, Anthropic and Gemini models | [copy.ai/prices](https://www.copy.ai/prices) |
| Copy.ai | Growth | $1,000/month, annual only | 75 seats | 20K workflow credits/month | [copy.ai/prices](https://www.copy.ai/prices) |
| GitBook | Essential | $65 + $12/user | per site/month (annual) | Custom domain, AI credits, 14-day trial | [gitbook.com/pricing](https://www.gitbook.com/pricing) |
| GitBook | Ultimate | $249 + $12/user | per site/month (annual) | Auth access, AI chat, priority support | [gitbook.com/pricing](https://www.gitbook.com/pricing) |
| Mintlify | Pro | $450 annual, $540 monthly | per month, unlimited seats | Agent, assistant, preview deploys | [mintlify.com/pricing](https://www.mintlify.com/pricing) |
| Hashnode | Pro | $5/month or $50/year | per publication | Custom domain, headless mode, scheduling | [hashnode.com/pro](https://hashnode.com/pro) |
| Ghost(Pro) | Publisher | $29/month (yearly) | per site, 3 staff | Custom themes, paid subscriptions | [ghost.org/pricing](https://ghost.org/pricing/) |
| Ghost(Pro) | Business | $199/month (yearly) | per site, 15 staff | Priority support, higher limits | [ghost.org/pricing](https://ghost.org/pricing/) |
| Novelcrafter (BYOK) | Hobbyist to Specialist | $8 to $20/month | per user | BYOK on all but the $4 tier; teams only on Specialist | [novelcrafter.com/pricing](https://www.novelcrafter.com/pricing) |

Notes and gaps:

- **Writer:** the $39/$29 figures appear in the search index of writer.com/plans, but the prices did not render when the page was fetched directly. Re-check before quoting publicly.
- **Hashnode team plan:** a third-party site lists a $199/month Startup plan with 5 members ([FitGap](https://us.fitgap.com/products/hashnode)). I could not confirm it on hashnode.com, so it is left out of the table.
- **Ghost monthly prices** were not shown on the fetched page. Only yearly figures are listed.
- **BYOK comparables:** Novelcrafter is the clearest published BYOK subscription. TypingMind's team product does not publish prices ([TypingMind docs](https://docs.typingmind.com/general-faqs)). I found no BYOK tool aimed at DevRel publishing.

**Read-across.** Seat prices for AI writing tools run $29 to $69. Masthead at $19 plus about $1 to $3 of Anthropic usage per month sits well below that. Docs platforms charge per site with a large fixed fee. Masthead has room to raise Team later.

## 4. The customer's AI cost under BYOK

Prices as given: Sonnet 5.5 at $2 per million input tokens and $10 per million output. Haiku 5.5 at $0.10 input and $0.50 output. Token counts other than the draft are my assumptions and should be replaced with numbers from the Studio's spend log.

| Step | Model | Input tokens | Output tokens | Input cost | Output cost | Step cost |
| --- | --- | --- | --- | --- | --- | --- |
| Outline | Sonnet | 6,000 | 1,500 | $0.0120 | $0.0150 | $0.0270 |
| Draft | Sonnet | 12,000 | 5,000 | $0.0240 | $0.0500 | $0.0740 |
| Check | Haiku | 10,000 | 1,000 | $0.0010 | $0.0005 | $0.0015 |
| Thumbnail | Sonnet | 4,000 | 3,000 | $0.0080 | $0.0300 | $0.0380 |
| Social copy | Haiku | 7,000 | 1,000 | $0.0007 | $0.0005 | $0.0012 |
| **One pass** | | | | | | **$0.142** |

Example: draft input is 12,000 x $2 / 1,000,000 = $0.024. Draft output is 5,000 x $10 / 1,000,000 = $0.050.

**Heavy case** with rework: outline x2, draft x3, check x3, thumbnail x3, social x2 = $0.054 + $0.222 + $0.0045 + $0.114 + $0.0024 = **$0.397**.

**Per post: about $0.14 to $0.40.** For a team publishing 8 posts a month: 8 x $0.142 = **$1.13** to 8 x $0.397 = **$3.18** a month. Prompt caching would lower this. Longer notes or long posts would raise it.

Suggested pricing-page line: "A typical post uses about $0.15 to $0.40 of Anthropic credit on your own key. Masthead adds nothing to that."

## 5. Trials, discounts and packaging

| Topic | Recommendation |
| --- | --- |
| Trial | 14-day Team trial, no card. At the end the workspace drops to Free, nothing is deleted. Business trial on request. Writer and GitBook both use 14 days; Jasper uses 7. |
| Annual discount | Keep 10 months for 12 (16.7% off). Simple to explain as "2 months free". |
| Startup discount | 50% off Team for 12 months for companies under 3 years old with under 20 staff. Apply with a Stripe coupon, by application. |
| Open source | Free Team for up to 5 seats for non-commercial open-source project blogs. Review by hand. |
| Seat minimums | Keep Team at 2 and Business at 5. Enforce in the app and in Checkout. |
| Proration | Added seats are prorated immediately. Removed seats take effect at renewal, with no credit. Plan upgrades prorate immediately; downgrades take effect at period end. |
| At a limit | Soft prompt at 4 of 5 posts. Hard block at opening the 6th pull request, but drafting stays open so no work is lost. Seat limit: block the invite, offer to add a seat. |
| Downgrade | Data kept. Extra repos disconnect, not deleted. Scheduled posts pause and are listed. Extra members become viewers. Business to Team: 14 days' notice before SSO turns off; audit log stays exportable for 90 days. |
| Failed payment | 14-day grace with banner and email, then read-only, then Free. |

## 6. Stripe setup

### Products and prices

| Product | lookup_key | Amount | Interval | Type |
| --- | --- | --- | --- | --- |
| Masthead Team | `team_monthly` | $19 | month | licensed, per_unit |
| Masthead Team | `team_yearly` | $190 | year | licensed, per_unit |
| Masthead Business | `business_monthly` | $39 | month | licensed, per_unit |
| Masthead Business | `business_yearly` | $390 | year | licensed, per_unit |

Quantity is the number of paid seats. Free has no Stripe price. Read the plan from the price's `lookup_key`, never from the amount.

### Checkout

- `mode: subscription`, one line item with the seat quantity and `adjustable_quantity` set to the plan minimum and maximum.
- `client_reference_id` and `subscription_data.metadata` carry the workspace id.
- `subscription_data.trial_period_days: 14` with `payment_method_collection: if_required` for a no-card trial.
- `billing_address_collection: required` and `tax_id_collection` enabled. Stripe India needs the customer's name and billing address on every international charge for services ([Stripe docs](https://docs.stripe.com/india-accept-international-payments)).

### Customer portal

Enable: payment method update, invoice history, billing address and tax ID update, cancel at period end with a reason survey, and switching between the four prices. Keep seat changes in the Masthead app so minimums, caps and the free-reviewer rule are enforced in one place.

### Webhooks

| Event | What it should change |
| --- | --- |
| `checkout.session.completed` | Link the Stripe customer and subscription ids to the workspace from `client_reference_id`. |
| `customer.subscription.created` | Store plan, seat count, status, trial end and period end. Turn on plan features. |
| `customer.subscription.updated` | Resync plan, seats, status and `cancel_at_period_end`. `past_due` shows the banner. `unpaid` or `canceled` starts the downgrade path. |
| `customer.subscription.deleted` | Move the workspace to Free and apply the downgrade rules. |
| `invoice.paid` | Mark active, clear dunning flags, store the invoice reference for export records. |
| `invoice.payment_failed` | Start the grace period and email the owner. Do not lock yet. |

Store each event id and skip duplicates. Events can arrive out of order, so refetch the subscription before writing.

### Stripe Tax

**Stripe Tax does not support businesses located in India.** It can calculate Indian IGST for foreign remote sellers only ([Stripe Tax: India](https://docs.stripe.com/tax/supported-countries/asia-pacific/india), [supported countries](https://docs.stripe.com/tax/supported-countries)). So Masthead cannot rely on it. Options: use manual tax rates for Indian customers and treat foreign sales as zero-rated exports, or use a merchant of record. This needs a chartered accountant's view, especially on foreign VAT and sales tax for any B2C sales. Selling only to businesses and collecting tax IDs keeps this simpler.

Stripe India fees: 3% on international Visa and Mastercard, 3.5% on Amex, 4.3% for non-INR presentment, plus 2% when conversion is needed. Billing adds 0.7% ([Stripe India pricing](https://stripe.com/in/pricing)). Budget roughly 5% to 7% of revenue for payments.

## 7. India-specific notes for a solo founder on Stripe

Everything in this section needs confirmation from a chartered accountant (CA) or Stripe.

- **Stripe India is invite-only.** New Indian businesses must request an invite ([Stripe docs](https://docs.stripe.com/india-accept-international-payments)). Apply early.
- **Entity.** The account must be a registered business: sole proprietorship, LLP or company. An individual cannot accept international payments. *Confirm with CA which entity to use.*
- **Export opt-in and purpose code.** Opt in to exports during onboarding and pick one RBI purpose code. Stripe lists codes such as P0807 (off-site software exports) and P0802 (software consultancy or implementation). Stripe will not advise which fits SaaS. *Confirm with CA.*
- **IEC.** Optional for services, but required to accept Amex from international customers.
- **Required data.** Name, billing address with ISO country code, and a description for every international charge. Missing data fails the payment.
- **Payouts.** Stripe pays out in INR. Standard Chartered sends payment advice for export payouts. *Ask CA whether this suffices as proof of foreign exchange receipt.*
- **GST on exports.** SaaS sold abroad can be a zero-rated export of services if all IGST s.2(6) conditions hold, including payment in convertible foreign exchange. Filing a Letter of Undertaking (LUT) avoids paying IGST up front ([Tally](https://tallysolutions.com/gst/gst-software-saas-exports-international-clients/), [Razorpay](https://razorpay.com/blog/gst-export-services-india-guide/)). These are commercial guides, not primary law. *Confirm with CA.*
- **GST registration threshold.** Notification 10/2017 exempts small inter-state service providers under ₹20 lakh. Whether an export-only business can rely on it is unclear in what I found. *Confirm with CA.*
- **Indian customers.** Domestic sales carry GST. Recurring charges on India-issued cards fall under RBI e-mandate rules: pre-debit notice, a 26-hour wait, and extra authentication above ₹15,000 ([Stripe docs](https://docs.stripe.com/india-recurring-payments)).
- **Realisation timeline.** Tally says export proceeds must be realised within 15 months. Cashfree says the limit was 9 months and moved to 15 under new FEMA rules from 1 October 2026 ([Cashfree](https://www.cashfree.com/blog/how-indian-businesses-and-freelancers-can-receive-international-payments/)). Stripe pays out quickly, so this is unlikely to bite. *Confirm with CA.*
- **GST on Stripe fees** may apply and may be claimable as input credit. *Confirm with CA.*

## 8. Metrics and experiments

| Metric | Definition |
| --- | --- |
| Activation | Key connected, repo connected and first pull request opened within 7 days of signup |
| Time to first PR | Signup to first pull request |
| Trial conversion | Team trials that become paid |
| Free to paid | Free workspaces that upgrade within 90 days |
| Seat expansion | Net seat change per paid workspace per month |
| Churn | Monthly logo churn and revenue churn, with cancel reasons |
| Reviewer pull-through | Free reviewers who later take a paid seat |

Volumes will be small at first, so run experiments as sequential cohorts, not statistical A/B tests. Give each at least 8 weeks.

1. **Team at $25 vs $19** for new signups. Watch trial conversion and seats per workspace. Competitors charge $29 to $69 per seat.
2. **Trial with card vs without.** Card-required trials usually convert better but start fewer. Measure paid workspaces per 100 signups.
3. **Annual as the default toggle** on the pricing page. Measure the share of annual plans and first-year churn.

## 9. Open decisions for the founder

1. Which legal entity will hold the Stripe account, and has the invite request gone in?
2. Sell to businesses only, or also to individuals? This decides how much foreign tax work there is.
3. Stripe direct with manual tax handling, or a merchant of record, given Stripe Tax does not cover India-based sellers?
4. Serve Indian customers at launch, with GST and e-mandates, or later?
5. Are reviewers free as proposed, or does every sign-off person pay?
6. What support response can you actually promise on Business?
7. Is there a sales-led Enterprise tier with invoices and contracts, or not yet?
8. Regional pricing for lower-income markets, or one USD price everywhere?

## Sources

- https://www.jasper.ai/pricing
- https://writer.com/plans
- https://www.copy.ai/prices
- https://www.gitbook.com/pricing
- https://www.mintlify.com/pricing
- https://hashnode.com/pro
- https://us.fitgap.com/products/hashnode
- https://ghost.org/pricing/
- https://ghost.org/faq/views-and-staff-users
- https://www.novelcrafter.com/pricing
- https://docs.typingmind.com/general-faqs
- https://docs.stripe.com/india-accept-international-payments
- https://support.stripe.com/questions/requirements-for-india-export-charges
- https://docs.stripe.com/india-recurring-payments
- https://docs.stripe.com/tax/supported-countries
- https://docs.stripe.com/tax/supported-countries/asia-pacific/india
- https://stripe.com/in/pricing
- https://tallysolutions.com/gst/gst-software-saas-exports-international-clients/
- https://razorpay.com/blog/gst-export-services-india-guide/
- https://www.cashfree.com/blog/how-indian-businesses-and-freelancers-can-receive-international-payments/
- https://taxheal.com/notification-no-102017-integrated-tax.html

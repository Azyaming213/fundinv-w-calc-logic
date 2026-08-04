# FundInv Final Presentation Runbook

**Audience:** OKC, assessors, and non-technical stakeholders  
**Recommended live-demo length:** 12-15 minutes  
**Live portal:** https://dxnh4gknox8f9.cloudfront.net

## The one-sentence story

FundInv gives investors a clear way to subscribe to and redeem from managed
funds while keeping user administration, fund valuation, and cash settlement
separated between Admin, Manager, and Operations.

## What the demonstration proves

By the end of the demonstration, the audience should have seen:

1. Admin invite or add a user.
2. An Investor select a fund and submit a fixed-amount demo PayNow subscription.
3. Operations verify the requested and received amounts and settle the request once.
4. The Manager preview and finalize daily fund P&L and NAV.
5. The Investor see updated units, value, allocated P&L, and portfolio analytics.
6. The Investor request a redemption and Operations settle it without allowing an excessive withdrawal.

## Before the presentation

### Ten-minute readiness check

- Open the CloudFront portal and confirm the login page loads.
- Keep four separate browser profiles or private windows ready so role sessions do not overwrite each other.
- Confirm the demo accounts can sign in.
- Confirm at least one established fund has opening assets and units. Use QQQ or VOO for daily valuation.
- Use an unfinalized valuation date. Never try to demonstrate a date already shown in Finalized valuation history.
- Use `paynow_demo`; do not use real money.
- Choose small, memorable amounts such as a $500 subscription and a $100 redemption.
- Keep this runbook open on a second screen.
- Do not change AWS, email, Alpaca, or Stripe configuration during the live presentation.

### Demo accounts

| Role | Email | Password | Main purpose |
|---|---|---|---|
| Admin | admin@fundinv.com | admin123 | User invitation and oversight |
| Manager | manager@fundinv.com | admin123 | Fund management and daily valuation |
| Operations | operations@fundinv.com | admin123 | Payment verification and settlement |
| Investor | investor@fundinv.com | investor123 | Subscription, redemption, and analytics |

## Role boundaries in plain English

**Admin controls access.** Admin invites users, manages account status, and
reviews audit information. Admin does not calculate fund performance or settle
investor money.

**Investor makes requests.** The Investor chooses a fund and an amount. The
Investor cannot issue their own units, alter NAV, or complete their own request.

**Manager values the fund.** The Manager determines the fund's investment gain
or loss for the day, previews the resulting NAV, and finalizes that valuation.
The Manager does not approve payment receipt.

**Operations settles money and units.** Operations verifies that the amount
requested matches the amount recorded as received, then completes the request
once. Operations does not alter P&L or NAV.

## Recommended live demonstration flow

### Step 1 - Opening statement (45 seconds)

**Say:**

> FundInv is a controlled fund-management portal. Investors can request a
> subscription or redemption, but separate staff roles control access, value
> the fund, and settle the request. This separation reduces mistakes and gives
> every important action an audit trail.

Briefly show the login page and name the four roles. Do not explain AWS or the
database yet; lead with the business workflow.

### Step 2 - Admin adds a user (1-2 minutes)

1. Sign in as Admin.
2. Open user or invitation management.
3. Create an invitation for a prepared demonstration email address.
4. Select the Investor role.
5. Send or create the invitation.
6. Show the invitation status and, if visible, the audit record.

**Say:**

> Admin controls who can enter the platform and which role they receive. The
> invitation is sent from the configured FundInv email account. Admin manages
> access but does not perform fund valuation or settlement.

**Point out:** role, invitation status, timestamp, and account activation state.

**Do not:** delete existing demonstration users or expose passwords, SMTP
credentials, API keys, or AWS secrets.

### Step 3 - Investor browses the fund catalogue (1 minute)

1. Sign in as Investor.
2. Open Funds.
3. Show the strategies, fund names, risk levels, and search/filter controls.
4. Select an established fund such as VOO or QQQ for the transaction demo.

**Say:**

> These are fund products available for subscription. Individual stocks are
> underlying instruments managed inside a fund and are not separate products
> sold directly to the Investor.

The approved suite contains 13 products: QQQ, VOO, VTI, SPY, BND, AGG, VYM,
SCHD, SOXL, TQQQ, TLT, SCHR, and VIG. High-risk products remain clearly
labelled.

### Step 4 - Investor submits a subscription (2 minutes)

1. Choose VOO or QQQ.
2. Select the Investor's account.
3. Enter `$500.00`.
4. Submit the request.
5. Show the clearly labelled demo PayNow QR and unique payment reference.
6. Use the portal's demo payment action to simulate scanning/paying the QR.
7. Show that the recorded amount remains exactly `$500.00`.

**Say:**

> The amount is locked by the server when the request is created. The demo QR
> carries that exact amount and reference, so the Investor cannot accidentally
> record a different payment. No fund units are issued merely because the
> request was submitted.

**Point out:** fund, requested amount, recorded paid amount, reference, and
current request status.

### Step 5 - Operations verifies and settles the subscription (1-2 minutes)

1. Sign in as Operations.
2. Open Fund Flows or pending fund requests.
3. Locate the `$500.00` request using its reference.
4. Compare requested amount and received amount.
5. Confirm the fund, investor, request type, and status.
6. Click **Verify & Complete** once.
7. Show the completed status and the issued-unit result.

**Say:**

> In demo PayNow mode, payment has already been simulated, so Operations uses
> one Verify & Complete action. The backend checks the amounts match and makes
> the action idempotent, meaning repeated clicks cannot issue units twice.

If the button is unavailable, read the status message. The likely blocker is
either missing payment confirmation or a required fund valuation. Do not keep
clicking.

### Step 6 - Manager performs daily fund valuation (3 minutes)

Use an established fund with opening assets and units, normally VOO or QQQ.
Do not use a brand-new empty fund for this demonstration.

1. Sign in as Manager.
2. Open **NAV Daily Valuation**.
3. Select the fund and an unfinalized date.
4. Click **Refresh calculation**.
5. If an automatic market suggestion appears, explain its source and use it.
6. If market data is unavailable, use a prepared, independently verified
   demonstration P&L and record its source in the audit note. Never guess live.
7. Click **Preview calculation**.
8. Review opening assets, daily P&L, closing assets before flows, opening units,
   NAV per unit, and investor allocation.
9. Only when those figures are correct, click **Finalize valuation** once.
10. Show the new record in Finalized valuation history.

**Plain-English explanation:**

> The Manager is valuing the whole fund, not typing profit into an Investor's
> account. Fund performance changes the value of each unit. It does not create
> extra units. Deposits and withdrawals are kept separate from investment P&L.

**Formula:**

```text
closing assets before flows = opening assets + daily fund P&L
NAV per unit                = closing assets before flows / opening units
investor allocated P&L      = fund P&L x opening ownership percentage
```

**Example already verified in the portal:**

```text
Opening assets:                  $5,105.00
Illustrative fund return:             +0.50%
Daily fund P&L:                    +$25.53
Closing assets before flows:     $5,130.53
Opening units:                   5,000.0000
Preview NAV per unit:           $1.02610600
```

An Investor holding 40% of the opening units receives 40% of the daily P&L,
or approximately `$10.21`. Their unit count does not change from performance.

**Important:** for SOXL, use SOXL's reported return as supplied. SOXL is already
leveraged; do not multiply its return by three again. An empty new fund cannot
be valued until its first settled subscription establishes assets and units.

### Step 7 - Investor checks the result and analytics (1-2 minutes)

1. Return to the Investor dashboard.
2. Refresh the page.
3. Show settled units and current NAV.
4. Show total fund value and allocated P&L.
5. Open portfolio analytics or the performance chart.
6. Open transaction/request history.
7. If useful, export the portfolio PDF.

**Say:**

> The Investor sees only their own units, value, allocated performance, and
> requests. A deposit changes invested capital; daily P&L represents investment
> performance. The system keeps those two causes separate.

Do not describe the Investor as directly owning QQQ or VOO shares. The Investor
owns internal FundInv units in the selected fund product.

### Step 8 - Investor requests a redemption (1-2 minutes)

1. Open the withdrawal/redemption action for an existing holding.
2. Enter `$100.00`, or another amount safely below the displayed redeemable value.
3. Review the estimated units to be redeemed and the remaining holding.
4. Submit the request.
5. Show its pending status in request history.

**Say:**

> The server prevents a redemption larger than the Investor's settled holding.
> The request does not remove units until Operations completes settlement.

### Step 9 - Operations settles the redemption (1 minute)

1. Return to Operations.
2. Locate the redemption request by its reference.
3. Confirm the Investor, fund, amount, applicable NAV, and available units.
4. Complete the payout/settlement step once.
5. Show the completed status.
6. Return to the Investor and refresh to show the reduced units and value.

**Say:**

> Redemption removes units at the applicable NAV and reduces cost basis
> proportionally. It cannot be completed twice, and it cannot exceed the
> Investor's settled position.

### Step 10 - Close with auditability and business value (45 seconds)

**Say:**

> This demonstration showed the complete controlled lifecycle: Admin granted
> access, the Investor requested a transaction, the Manager valued the fund,
> and Operations independently settled money and units. FundInv provides a
> usable investor experience while preserving role separation, consistent NAV
> calculations, duplicate-processing protection, and an audit trail.

Then invite questions. Keep technical architecture as a backup topic rather
than making it the conclusion.

## Fund catalogue clarification

The correct historical numbers are:

- The first repository seed contained **20 catalogue rows**, not 19.
- Seven of those rows were ordinary stocks: AMD, NVDA, TSLA, COIN, AAPL, MSFT,
  and AMZN.
- Those seven stocks were correctly removed from the Investor fund catalogue.
- The resulting legitimate demonstration suite contains **13 fund products**.
- The Manager's **Your Funds (3)** page lists only the funds owned by that
  Manager; it is not a count of every product in the database.
- Before final demonstration setup, the Investor owned only QQQ and VOO. That
  was a holdings count, not the size of the full catalogue.
- Demonstration setup uses the normal subscription, demo PayNow, and Operations
  settlement workflow to create actual Investor fund-unit holdings.

## Questions the audience may ask

### Does the QR transfer real money?

No. `paynow_demo` generates a clearly labelled dummy QR and simulates receipt
of the exact requested amount. It demonstrates the workflow without moving
real funds.

### Does Alpaca create Investor funds?

No. FundInv stores fund products, Investor units, NAV, P&L, and transaction
history in PostgreSQL. Alpaca is an optional external source for market data
and paper trading of underlying assets.

### Why are there separate Manager and Operations roles?

The Manager determines investment performance and NAV. Operations verifies
money movement and settles units. Separating these duties reduces the chance
that one person can value a fund and also approve the resulting transaction.

### Can several users use the portal at once?

Yes for a classroom-scale demonstration. The AWS deployment, database, and
load-balanced application are not dependent on the presenter's laptop. Large
production workloads would require further capacity testing and scaling work.

### Can completed records be changed?

Financial settlement and valuation records are designed to be append-only or
finalized once. Corrections should be made through controlled follow-up records,
not by silently rewriting history.

## Live-demo recovery plan

If something does not work, remain calm and explain the control that stopped it.

| Situation | Safe response |
|---|---|
| A date is already finalized | Select a genuinely unfinalized date; do not overwrite history. |
| Automatic market P&L is unavailable | Use a prepared verified figure with an audit note, or show Preview using a clearly labelled illustration. |
| Operations cannot complete | Read the status: confirm payment, valuation, fund, amount, and request state. Do not repeatedly click. |
| The Investor view looks stale | Refresh after Operations or Manager has completed the preceding step. |
| Email delivery is delayed | Show the invitation record and explain that email is an external notification, not the access-control source of truth. |
| A live workflow remains blocked | Move to existing completed history and explain the same lifecycle using recorded evidence. |

## Final presenter reminders

- Say **fund units**, not shares directly owned in QQQ or VOO.
- Say **subscription and redemption**, then translate them as deposit and withdrawal.
- Say **demo PayNow**, not real PayNow.
- Never guess P&L, expose credentials, or edit AWS configuration live.
- Preview before finalizing.
- Click settlement actions once.
- Keep fund performance separate from deposits and withdrawals.
- The accurate product-suite number is **13**, not 19.

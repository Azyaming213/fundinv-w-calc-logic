# Authoritative Fund Portal Workflow

This document defines the current product model. Investor-facing fund units are
authoritative; individual securities are underlying fund assets managed by the
Manager and are not separate Investor purchases.

## Role boundaries

| Role | Responsibilities |
|---|---|
| Investor | Select a fund, request a subscription or redemption, view units, NAV, value, allocated P&L, reports, articles, and own requests. |
| Operations | Review requests; compare requested and received amounts; verify and complete demo PayNow subscriptions once; independently verify manual settlement. |
| Manager | Create/manage funds, trade underlying securities, set fund strategy/weights, preview/finalize daily fund P&L and NAV, and review performance attribution. |
| Admin | Manage platform users and invitations and audit fund flows, valuations, transactions, and security events. Admin cannot impersonate an Investor portfolio. |

Only Manager has `executeTrades`. Investors cannot call direct security trading
endpoints. The Investor fund catalogue excludes products whose type is `stock`.

## Subscription

1. Investor selects an approved fund, account, and positive amount. The API
   enforces the configured subscription cap and rounds the request to cents.
2. In `paynow_demo` mode, the API creates an `awaiting_investor_payment` flow
   and immediately returns a clearly labelled dummy QR. Its payload contains
   the exact server-locked requested amount and a unique reference.
3. Simulating the QR scan records that exact amount as `paid_amount` and moves
   the flow to `pending_ops_team`; the client cannot submit a different paid amount.
4. Operations sees requested and received amounts side by side. **Verify &
   Complete** succeeds only when they match exactly and is idempotent. Manual
   mode instead retains separate approval, external verification, and completion;
   Stripe mode uses a correctly signed webhook.
5. No units, cost basis, fund value, or P&L changes before verified completion.
   Settlement then mints `subscription amount / current NAV per unit` units.
6. Position cost basis and account principal rise by the cash amount, and one
   immutable balance-ledger entry is written.

## Redemption

The first three steps match subscription. Completion verifies payout, then
redeems `redemption amount / current NAV per unit` units. Cost basis falls
proportionally:

`cost removed = old cost basis × units redeemed / units before redemption`

The ledger records a negative cash flow and unit movement exactly once. A
request cannot redeem more units than the account owns.

## Daily NAV and P&L order

Daily investment performance is applied before that day's external flows:

```text
closing assets before flows = opening assets + daily P&L
closing assets              = closing assets before flows + net external flow
NAV per unit                = closing assets / closing units outstanding
investor account value      = investor units × NAV per unit
investor daily P&L          = daily fund P&L × opening ownership share
```

Before finalization, FundInv calculates a reviewable daily P&L suggestion from
market data. A single-ticker fund uses that instrument's close-to-close return;
a managed fund uses the weighted returns of its configured components. The
suggestion pre-fills the Manager's P&L input. The Manager may accept it or enter
an approved accounting adjustment, with the source and audit note preserved.
If any required market price is unavailable, FundInv does not guess: it keeps
the field manual and explains which symbol is missing.

The Manager previews the resulting NAV and Investor allocation, then finalizes
it once. Finalization records the Manager, timestamp, calculation source, and
optional note. It changes NAV and account values but never creates or destroys
units. Operations can then settle subscriptions/redemptions at that finalized
NAV; each settlement appends assets and units at equal value while leaving the
finalized daily P&L unchanged. The Investor sees only their own allocation
ledger, while Admin receives a read-only valuation audit ledger.

Subscriptions and redemptions use the post-P&L NAV, preventing dilution.
External cash flows change units and assets in equal value and therefore do not
become investment P&L. Fund return compounds daily returns:

`cumulative return = product(1 + daily return) - 1`

## Provider configuration

`FUND_FLOW_PROVIDER=paynow_demo` is the default local demonstration and never
moves real money. Use `manual` for independently verified external transfers.
Set it to `stripe` only when valid test credentials and signed webhook
forwarding are configured. SMTP remains optional for core accounting tests.
Alpaca market-data credentials enable the automatic Manager P&L suggestion and
external paper orders; without market data, valuation remains available through
the explicit manual-entry fallback.

## Accounting sources of truth

- `fund_positions`: account/fund units and cost basis.
- `fund_valuations`: opening assets, daily P&L, flows, closing assets, units,
  NAV, and date.
- `fund_balance_entries`: immutable, idempotent settlement ledger.
- `manager_fund_balance`: compatibility cache rebuilt from positions, not an
  accounting source of truth.

Manager paper orders are persisted immediately after provider acceptance. Fill
quantity, price, allocation, and transaction accounting are applied only after
Alpaca confirms `filled`, with an idempotent one-minute reconciliation retry.

Current migration head: `v0.5.3_fund_catalog_cleanup`.

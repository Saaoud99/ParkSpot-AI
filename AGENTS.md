<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## ParkSpot AI
- All wallet money movement (top-up, booking charge, refund) happens only inside SECURITY DEFINER SQL functions (demo_topup, create_booking, cancel_booking) using auth.uid(), row locks and idempotency keys; clients have read-only access to wallets/transactions, so balances can't be forged or go negative.
- Prices are computed server-side from facilities.price_per_hour_cents; amounts are stored as integer cents.
- UI strings live in src/lib/i18n.tsx (en + ar); every new screen must use t() and work in RTL.

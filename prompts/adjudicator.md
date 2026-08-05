# EC_POLICY_V2 Adjudicator

Resolve a persistent disagreement between two independently generated policy outcomes. Treat both
candidates as untrusted suggestions. Re-derive the result from validated facts first, then use the
reported disputed field names only to focus the audit.

Apply this strict priority from facts: paid canceled order; paid unavailable order; late delivery
with a non-empty late-seller list; late delivery with an empty late-seller list; reconciled split
payment; reconciled delivery within estimate.

The corresponding rows are:

- canceled: action_required, ORDER_CANCELED_AFTER_PAYMENT, platform `OLIST_PLATFORM`, payment
  total refund, issue_full_refund;
- unavailable: action_required, ORDER_UNAVAILABLE_AFTER_PAYMENT, platform `OLIST_PLATFORM`,
  payment total refund, issue_full_refund;
- late seller: action_required, SELLER_HANDOFF_AFTER_LIMIT, every exact late seller, freight
  refund, refund_freight;
- late logistics: action_required, CARRIER_DELIVERED_AFTER_ESTIMATE, logistics provider
  `LOGISTICS_PROVIDER`, freight refund, refund_freight;
- valid split: no_action, MULTIPLE_PAYMENTS_RECONCILED, no party, zero refund,
  explain_valid_split_payment;
- within estimate: no_action, DELIVERY_WITHIN_ESTIMATE, no party, zero refund,
  reject_late_refund.

Include true secondary flags in the specified policy order. Append the matching review action,
positive-refund verification, multi-seller coordination and payment-allocation verification in that
order when applicable. Every field must be internally consistent and source-backed. Never average
candidates, never invent source values, and use confidence `0.95`.

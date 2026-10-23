# Replacement configuration policy — owner decision recorded 2026-10-23

Kyle approved option 2 below: **“Allow clearly labelled agent proposals, with every SKU, option and check
supported by fetched quotes.”** The [implementation and offline verification](../replacement-proposals-20261023/README.md)
record this decision separately from live acceptance. Original submissions still need their own explicit
selection. No existing candidate, blind label, checklist or release gate is approved by this policy decision.

The following question is the historical context before that decision.

The existing instruction stays binding: a blank catalog field or ordering example does not select the
submitted configuration. The original cases, checklists and unconfirmed options remain unchanged.

The open question concerns a **new replacement proposal**. Current discovery finds catalog families,
whose driver/DLC-dependent values cannot establish a complete replacement without a configuration.
The [actual LT result](diagnosis.json) passes L70, warranty and MacAdam; dimming, selected DLC and
availability remain unconfirmed. This is a source/selection gap, not a budget failure.

The two proposed product rules were:

1. **Submitted selection required for replacements too (previous behavior).** SpecCheck returns the
   candidate and missing proof. A contractor/user must supply the actual selected configuration before
   that candidate can pass. The agent continues looking for candidates with complete product-wide proof.
2. **Explicitly labelled replacement proposal.** SpecCheck may propose an exact configuration, clearly
   identifying itself as the author of that choice. The original submission still has no inferred
   selection. Every proposed SKU, applicable option, spec value, currency and availability statement must
   be verified against fetched source quotes; an invented order code, default driver or generic family
   listing cannot establish the proposal's validity. A checked proposal is not contractor acceptance or
   approval of the original package.

Neither rule supplies missing evidence. LT is **not** a passing replacement under this note. The policy
approval does not approve a SKU, change a score or accept a release. Actual source-backed proposal
validation remains pending behind the separate billing hold.

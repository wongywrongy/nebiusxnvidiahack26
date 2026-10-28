# Manual review timing sheet (Kyle)

Check each package the way a reviewer would: the spec section, the submittal PDF, and the
manufacturer's website. Start the timer when you open the PDF and stop it when you've written
your decision and one-line reason. Don't look at SpecCheck's answer first.

| Case | Spec section | Submittal |
|---|---|---|
| c02 | 07 84 00 Firestopping | 3M UL system C-AJ-2738: https://multimedia.3m.com/mws/media/1213657O/system-no-c-aj-2738.pdf |
| c03 | 07 84 00 Firestopping | 3M IC 15WB+ data sheet: https://www.cableorganizer.com/cdn/shop/files/IC_15WB_Data_Sheet.pdf |
| c07 | 26 51 00 Interior lighting | Lithonia 2TL4 spec sheet: https://cdn.shopify.com/s/files/1/0681/6625/4899/files/lithonia-2TL4-spec.pdf |

## What to check

**07 84 00 (c02, c03)**
- 2.02.B VOC ≤ 250 g/L
- 2.02.C ASTM G21 (mold) rating = 0
- 2.04.A.1 T rating equals F rating, for the assembly
- 2.04.A.1 Tested to ASTM E814, ASTM E119 or UL 1479
- Is this the manufacturer's current document? (Find the current sheet on 3m.com and compare.)
- Is the product still made?

**26 51 00 (c07)**
- 2.02.S.3 L70 ≥ 50,000 h
- 1.10.B.1 Warranty ≥ 5 years
- 2.02.H DLC Standard or Premium listed
- 2.02.S.6 MacAdam ≤ 3-step
- 2.05.C.1 Dims to ≤ 5 %
- Is the product still made? (Check acuitybrands.com.)
- Is this the current sheet?

## Record

| Case | Start | Stop | Minutes | Decision | Reason | Problems found |
|---|---|---|---|---|---|---|
| c02 | | | | | | |
| c03 | | | | | | |
| c07 | | | | | | |

SpecCheck, fresh local live run, Oct 28 2026 (deployed tuning, 2 items at a time): c07 81 s, c02 177 s,
c03 415 s. Don't use the recorded run's ~0.1 s per item: those are cache hits.

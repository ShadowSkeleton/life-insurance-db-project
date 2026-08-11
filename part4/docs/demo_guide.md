# Demo guide

The in-app guide and this document are generated from this shared source. The canonical source is `web/lib/demo-guide-content.json`.

1. Quote and bind a diabetic profile. I quote a disclosed-diabetes profile, note its premium and rate version, then bind the application. The bound policy receives that same version pin, establishing the policyholder’s historical price basis. This implements UC-1 and UC-2 · Mechanism 2.

2. Publish from the alternate mortality cohort. I select the other year-range mortality source and run the asynchronous local refresh. It records the selected cohort and loading in the run audit, supersedes the active version, and publishes the next rate book without writing to existing Contract rows. This implements UC-4 · Mechanism 1.

3. Quote the identical profile again. I submit the identical profile. The quote shows the current version beside the most recent prior quote, including the absolute and percentage premium change. The cohort-only change is under one percent by measurement; the loading control demonstrates a larger approved-assumption revision when needed. This implements UC-1 · Mechanism 2.

4. Verify the bound policy remains pinned. I open the bound policy in the wellness screen. Its IssuedRateVersionID is still the original version, while the current book is newer. Repricing changes RATE_VERSION and RATE, not an existing Contract. This implements UC-5 · Mechanism 2.

5. Enrol the bound policy. On the same bound policy, I select a published wellness program and record its enrollment before the next projected renewal. The policy now has an enrollment but a zero measured-improvement credit. This implements UC-3 · Mechanism 3.

6. Record activity without changing the credit. On that same enrolled policy, I add verified activity and observe the annual activity total change. The projected renewal credit stays at zero, because participation alone is not a measured mortality improvement. This implements UC-3 · Mechanism 3.

7. Record a biometric screening. On that same policy, I record a dated biometric screening after enrollment and before the projected renewal, with a baseline and current measurement. The system writes RISK_IMPROVEMENT, calculates the measured improvement, and the projected renewal premium visibly falls under the capped credit rule. This implements UC-3 and UC-5 · Mechanism 3.

Presenter note: The cohort-only rate revision moves premiums by under one percent because the two mortality cohorts differ little. That is a measured pricing-robustness finding. The wellness offset is the larger real effect; the loading control remains available when a larger approved-assumption revision is needed.

The wellness activity step refreshes the indexed-view count. Activity is evidence for the periodic measurement process. It does not itself create a `RISK_IMPROVEMENT` row or an immediate premium reduction.

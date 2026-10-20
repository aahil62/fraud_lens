/** Landing-page proof numbers. proof.test.ts checks the evaluation figures
 * against docs/verification/operations-evaluation.json so they cannot drift. */
export const PROOF = {
  channels: 4,
  /** Named scam typologies a visitor can launch from /attack (scenarios.py). */
  typologies: 4,
  protectionThreshold: 0.8,
  precision: 0.8462,
  recall: 0.8148,
  evaluationSamples: 376,
  /** Backend unittest count from the last full run (updated after the legacy removal). */
  backendTests: 232,
};

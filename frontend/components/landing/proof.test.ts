import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { PROOF } from "./proof";
const evaluation = JSON.parse(readFileSync(resolve(process.cwd(), "../docs/verification/operations-evaluation.json"), "utf8"));
it("quotes the automatic-protection precision and recall exactly as evaluated", () => {
  expect(PROOF.protectionThreshold).toBe(evaluation.overall.protection.threshold);
  expect(PROOF.precision).toBe(evaluation.overall.protection.precision);
  expect(PROOF.recall).toBe(evaluation.overall.protection.recall);
  expect(PROOF.evaluationSamples).toBe(evaluation.overall.protection.samples);
});
it("counts the four payment channels the evaluation covers", () => {
  expect(PROOF.channels).toBe(Object.keys(evaluation.channels).length);
});

import { expect, it } from "vitest";
import { config } from "../proxy";
import robots from "./robots";

it("serves a real robots file: public pages crawlable, console pages not", () => {
  const { rules } = robots();
  const rule = Array.isArray(rules) ? rules[0] : rules;
  expect(rule.userAgent).toBe("*");
  expect(rule.allow).toEqual(["/", "/attack"]);
  expect(rule.disallow).toContain("/dashboard");
  expect(rule.disallow).toContain("/case");
});

it("lets crawlers fetch /robots.txt without a session (the proxy skips it)", () => {
  const matcher = new RegExp(`^${config.matcher[0]}$`);
  expect(matcher.test("/robots.txt")).toBe(false);
});

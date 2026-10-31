import { describe, expect, it } from "vitest";
import { groundedReply, type AssistantFacility } from "@/lib/assistantCore";

const F: AssistantFacility[] = [
  { id: "1", name: "Casa Marina Parking", city: "Casablanca", address: "Bd Mohammed V", price_per_hour_cents: 2000, available: 14, capacity: 120, features: ["covered"], rating: 4.6 },
  { id: "2", name: "Maârif Open Lot", city: "Casablanca", address: "Rue Ibnou Mounir", price_per_hour_cents: 800, available: 22, capacity: 90, features: ["ev"], rating: 4.3 },
  { id: "3", name: "Full Park", city: "Casablanca", address: "X", price_per_hour_cents: 500, available: 0, capacity: 50, features: [], rating: 4.9 },
];

describe("groundedReply", () => {
  it("only lists real, available facilities", () => {
    const out = groundedReply(F, "parking in Casablanca");
    expect(out).toContain("Casa Marina");
    expect(out).not.toContain("Full Park"); // 0 available — never recommended
    expect(out).not.toMatch(/invented|made up/i);
  });

  it("cheapest sorts by real price and quotes server math", () => {
    const out = groundedReply(F, "cheapest parking in Casablanca for 3 hours");
    expect(out.indexOf("Maârif")).toBeLessThan(out.indexOf("Casa Marina"));
    expect(out).toContain("24.00 MAD"); // 8 MAD/h × 3
  });

  it("applies price ceilings and EV filter", () => {
    const out = groundedReply(F, "EV parking under 10 MAD");
    expect(out).toContain("Maârif");
    expect(out).not.toContain("Casa Marina");
  });

  it("never guesses a location", () => {
    expect(groundedReply(F, "parking near me")).toContain("Parking Near Me");
  });

  it("answers refunds from policy, with no facilities", () => {
    const out = groundedReply(F, "How do refunds work?");
    expect(out).toContain("50%");
    expect(out).not.toContain("Casa Marina");
  });

  it("is honest when nothing matches", () => {
    expect(groundedReply(F, "parking in Casablanca under 1 MAD")).toContain("no matching");
  });
});

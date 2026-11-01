import { describe, expect, it } from "vitest";
import { effectiveAvailable } from "@/lib/data";

// Phase 4 (Option A): displayed availability is clamped to the
// ParkSpot-authorized capacity. The authoritative ceiling is enforced in
// SQL create_booking (migration 0003); this is display truth only.
describe("effectiveAvailable", () => {
  it("passes normal values through unchanged", () => {
    expect(effectiveAvailable({ available: 14, capacity: 120, authorized_capacity: 100 })).toBe(14);
  });

  it("clamps a stale counter down to the authorized capacity", () => {
    expect(effectiveAvailable({ available: 50, capacity: 120, authorized_capacity: 10 })).toBe(10);
  });

  it("reports zero when authorized capacity is zero, whatever the counter says", () => {
    expect(effectiveAvailable({ available: 14, capacity: 120, authorized_capacity: 0 })).toBe(0);
  });

  it("falls back to legacy capacity on pre-0001 rows without authorized_capacity", () => {
    expect(effectiveAvailable({ available: 14, capacity: 120 })).toBe(14);
    expect(effectiveAvailable({ available: 500, capacity: 120, authorized_capacity: null })).toBe(
      120,
    );
  });

  it("never returns a negative figure", () => {
    expect(effectiveAvailable({ available: -3, capacity: 120, authorized_capacity: 10 })).toBe(0);
  });
});

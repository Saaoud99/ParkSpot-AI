import { describe, expect, it } from "vitest";
import { adminApi } from "@/lib/admin";

describe("adminApi structure and client calls", () => {
  it("defines all 12 operational domain endpoints", () => {
    expect(typeof adminApi.overview).toBe("function");
    expect(typeof adminApi.users).toBe("function");
    expect(typeof adminApi.userDetail).toBe("function");
    expect(typeof adminApi.suspendUser).toBe("function");
    expect(typeof adminApi.reactivateUser).toBe("function");
    expect(typeof adminApi.setRole).toBe("function");
    expect(typeof adminApi.facilities).toBe("function");
    expect(typeof adminApi.createFacility).toBe("function");
    expect(typeof adminApi.updateFacility).toBe("function");
    expect(typeof adminApi.pricing).toBe("function");
    expect(typeof adminApi.setPrice).toBe("function");
    expect(typeof adminApi.recomputePricing).toBe("function");
    expect(typeof adminApi.bookings).toBe("function");
    expect(typeof adminApi.cancelBooking).toBe("function");
    expect(typeof adminApi.aiStatus).toBe("function");
    expect(typeof adminApi.aiHealth).toBe("function");
    expect(typeof adminApi.aiToggle).toBe("function");
    expect(typeof adminApi.cameras).toBe("function");
    expect(typeof adminApi.createCamera).toBe("function");
    expect(typeof adminApi.updateCamera).toBe("function");
    expect(typeof adminApi.wallets).toBe("function");
    expect(typeof adminApi.walletTx).toBe("function");
    expect(typeof adminApi.adjustWallet).toBe("function");
    expect(typeof adminApi.reports).toBe("function");
    expect(typeof adminApi.incidents).toBe("function");
    expect(typeof adminApi.createIncident).toBe("function");
    expect(typeof adminApi.updateIncident).toBe("function");
    expect(typeof adminApi.audit).toBe("function");
    expect(typeof adminApi.settings).toBe("function");
    expect(typeof adminApi.updateSettings).toBe("function");
    expect(typeof adminApi.updateProfile).toBe("function");
    expect(typeof adminApi.database).toBe("function");
    expect(typeof adminApi.databaseRows).toBe("function");
    expect(typeof adminApi.createDatabaseRow).toBe("function");
    expect(typeof adminApi.updateDatabaseRow).toBe("function");
    expect(typeof adminApi.csvUrl).toBe("function");
    expect(typeof adminApi.auditCsvUrl).toBe("function");
  });

  it("produces correct export URLs", () => {
    expect(adminApi.csvUrl()).toContain("/api/v1/admin/reports/bookings.csv");
    expect(adminApi.auditCsvUrl()).toContain("/api/v1/admin/reports/audit.csv");
  });
});


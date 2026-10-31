import { describe, expect, it } from "vitest";
import type { User } from "@supabase/supabase-js";

import { authErrorKey, isExistingAccount } from "@/lib/auth";

describe("authErrorKey", () => {
  it("maps bad credentials without leaking which field was wrong", () => {
    expect(authErrorKey({ code: "invalid_credentials", message: "Invalid login credentials" })).toBe("invalidCredentials");
  });

  it("maps duplicate sign-ups", () => {
    expect(authErrorKey({ code: "user_already_exists", message: "User already registered" })).toBe("accountExists");
  });

  it("returns null for unknown errors so the raw message can be shown", () => {
    expect(authErrorKey(new Error("network unreachable"))).toBeNull();
    expect(authErrorKey(null)).toBeNull();
  });
});

describe("isExistingAccount", () => {
  it("detects Supabase's obfuscated duplicate-signup user (no identities)", () => {
    expect(isExistingAccount({ identities: [] } as unknown as User)).toBe(true);
  });

  it("accepts a genuinely new user", () => {
    expect(isExistingAccount({ identities: [{ id: "1" }] } as unknown as User)).toBe(false);
    expect(isExistingAccount(null)).toBe(false);
    expect(isExistingAccount(undefined)).toBe(false);
  });
});

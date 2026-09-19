import { describe, expect, it } from "vitest";
import { primaryRole, rolePath } from "./roles";

describe("role navigation", () => {
  it("selects the highest privileged assigned workspace", () => {
    expect(primaryRole(["CITIZEN", "ADMIN"])).toBe("ADMIN");
    expect(primaryRole(["CITIZEN", "RESPONDER"])).toBe("RESPONDER");
  });

  it("builds canonical role paths", () => {
    expect(rolePath("AUTHORITY")).toBe("/authority");
  });
});

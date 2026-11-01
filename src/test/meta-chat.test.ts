import { describe, expect, it } from "vitest";
import {
  buildChatBody,
  looksLikeNearMe,
  META_MAX_CONTENT_CHARS,
  META_MAX_MESSAGES,
  prepareChatMessages,
} from "@/lib/meta";

const convo = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    role: i % 2 ? "assistant" : "user",
    content: `message ${i}`,
  }));

describe("prepareChatMessages", () => {
  it("keeps only the most recent 12 messages, preserving order and roles", () => {
    const out = prepareChatMessages(convo(20));
    expect(out).toHaveLength(META_MAX_MESSAGES);
    expect(out[0]).toEqual({ role: "user", content: "message 8" });
    expect(out[out.length - 1]).toEqual({ role: "assistant", content: "message 19" });
    expect(out.every((m) => m.role === "user" || m.role === "assistant")).toBe(true);
  });

  it("passes short conversations through unchanged", () => {
    const short = convo(4);
    expect(prepareChatMessages(short)).toEqual(short);
  });

  it("throws message-too-long for an oversized current message instead of truncating it", () => {
    const msgs = [...convo(3), { role: "user", content: "x".repeat(META_MAX_CONTENT_CHARS + 1) }];
    expect(() => prepareChatMessages(msgs)).toThrow("message-too-long");
  });

  it("truncates oversized history but keeps the current message intact", () => {
    const msgs = [
      { role: "assistant", content: "y".repeat(META_MAX_CONTENT_CHARS + 500) },
      { role: "user", content: "parking in Casablanca?" },
    ];
    const out = prepareChatMessages(msgs);
    expect(out[0].content).toHaveLength(META_MAX_CONTENT_CHARS);
    expect(out[1]).toEqual({ role: "user", content: "parking in Casablanca?" });
  });

  it("always conforms to the backend limits", () => {
    const out = prepareChatMessages(convo(50));
    expect(out.length).toBeLessThanOrEqual(12);
    expect(out.every((m) => m.content.length <= 2000)).toBe(true);
  });
});

describe("looksLikeNearMe", () => {
  it("detects near-me intent in English, French, and Arabic", () => {
    expect(looksLikeNearMe("Find parking near me")).toBe(true);
    expect(looksLikeNearMe("What's the closest parking?")).toBe(true);
    expect(looksLikeNearMe("Un parking près de moi ?")).toBe(true);
    expect(looksLikeNearMe("أبغى موقف قريب مني")).toBe(true);
  });

  it("does not trigger location requests for ordinary questions", () => {
    expect(looksLikeNearMe("Cheapest parking in Casablanca?")).toBe(false);
    expect(looksLikeNearMe("How do refunds work?")).toBe(false);
    expect(looksLikeNearMe("hello")).toBe(false);
  });
});

describe("buildChatBody", () => {
  const msgs = [{ role: "user", content: "parking near me" }];

  it("includes valid shared coords so the backend can run nearby search", () => {
    const body = buildChatBody(msgs, "en", { lat: 33.5731, lng: -7.5898 });
    expect(body.coords).toEqual({ lat: 33.5731, lng: -7.5898 });
    expect(body.messages).toEqual(msgs);
  });

  it("omits coords when not shared or invalid — never invents a location", () => {
    expect(buildChatBody(msgs, "en", null).coords).toBeUndefined();
    expect(buildChatBody(msgs, "en").coords).toBeUndefined();
    expect(buildChatBody(msgs, "en", { lat: 999, lng: 0 }).coords).toBeUndefined();
    expect(buildChatBody(msgs, "en", { lat: Number.NaN, lng: 0 }).coords).toBeUndefined();
  });
});

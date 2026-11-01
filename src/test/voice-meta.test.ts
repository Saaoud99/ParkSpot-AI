import { describe, expect, it } from "vitest";
import { voiceMaxSeconds, voiceUploadFilename, type MetaStatus } from "@/lib/meta";

const status = (over: Partial<MetaStatus>): MetaStatus => ({
  assistant: "grounded_fallback",
  vision_sam: "unconfigured",
  voice: "disabled",
  ...over,
});

describe("voiceMaxSeconds", () => {
  it("defaults to a safe 30 s without backend config", () => {
    expect(voiceMaxSeconds(null)).toBe(30);
    expect(voiceMaxSeconds(undefined)).toBe(30);
    expect(voiceMaxSeconds(status({}))).toBe(30);
  });

  it("follows the backend-configured cap, clamped to sane bounds", () => {
    expect(voiceMaxSeconds(status({ voice_max_seconds: 45 }))).toBe(45);
    expect(voiceMaxSeconds(status({ voice_max_seconds: 9999 }))).toBe(600);
    expect(voiceMaxSeconds(status({ voice_max_seconds: 1 }))).toBe(5);
  });
});

describe("voiceUploadFilename", () => {
  it("matches the actual MediaRecorder Blob type", () => {
    expect(voiceUploadFilename(new Blob([], { type: "audio/webm;codecs=opus" }))).toBe(
      "voice.webm",
    );
    expect(voiceUploadFilename(new Blob([], { type: "audio/mp4" }))).toBe("voice.mp4");
    expect(voiceUploadFilename(new Blob([], { type: "audio/wav" }))).toBe("voice.wav");
    expect(voiceUploadFilename(new Blob([], { type: "audio/mpeg" }))).toBe("voice.mp3");
  });
});

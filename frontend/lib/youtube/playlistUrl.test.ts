import assert from "node:assert/strict";
import test from "node:test";
import { parseYouTubePlaylistUrl } from "./playlistUrl";

test("accepts common YouTube playlist URLs", () => {
  const urls = [
    "https://www.youtube.com/playlist?list=ABC123",
    "https://youtube.com/playlist?list=ABC123",
    "https://www.youtube.com/playlist/?list=ABC123",
    "https://www.youtube.com/watch?v=VIDEO123&list=ABC123",
    "https://www.youtube.com/playlist?list=ABC123&utm_source=test",
  ];

  for (const url of urls) {
    const result = parseYouTubePlaylistUrl(url);
    assert.equal(result.valid, true);
    if (result.valid) assert.equal(result.playlistId, "ABC123");
  }
});

test("normalizes the playlist URL and removes unrelated parameters", () => {
  const result = parseYouTubePlaylistUrl("https://youtube.com/playlist?list=ABC123&utm_source=test");

  assert.deepEqual(result, {
    valid: true,
    playlistId: "ABC123",
    normalizedUrl: "https://www.youtube.com/playlist?list=ABC123",
  });
});

test("rejects empty, malformed, unsupported, and incomplete URLs", () => {
  const urls = [
    "",
    "random text",
    "https://www.youtube.com/",
    "https://www.youtube.com/watch?v=VIDEO123",
    "https://example.com/playlist?list=ABC123",
    "https://www.youtube.com/playlist?list=",
    "https://www.youtube.com.evil.example/playlist?list=ABC123",
  ];

  for (const url of urls) assert.equal(parseYouTubePlaylistUrl(url).valid, false);
});
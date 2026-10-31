import { API_ROOT, UserFacingError, expireSession, refreshAccessToken, tokens } from "./client";
import type { SendMessageResponse } from "./types";

type StreamEvent =
  | { type: "delta"; text: string }
  | ({ type: "done" } & SendMessageResponse)
  | { type: "error"; detail: string };

const post = (url: string, body: unknown, signal?: AbortSignal) =>
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokens.access() ?? ""}` },
    body: JSON.stringify(body),
    signal,
  });

const errorFromResponse = async (res: Response): Promise<Error> => {
  if (res.status === 429) return new UserFacingError("You're going a little fast. Please wait a moment and try again.");
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return new UserFacingError(data.detail);
    const first = Object.values(data).flat()[0];
    if (typeof first === "string") return new UserFacingError(first);
  } catch {
    // non-JSON error body
  }
  return new UserFacingError("TherapyBot couldn't respond. Please try again.");
};

/**
 * Send a message and stream the reply. `onDelta` receives each new piece of text.
 * Resolves with the saved messages once the reply is complete.
 */
export async function streamMessage(
  conversationId: number,
  content: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<SendMessageResponse> {
  const url = `${API_ROOT}conversations/${conversationId}/messages/stream/`;
  let res = await post(url, { content }, signal);

  if (res.status === 401) {
    try {
      await refreshAccessToken();
    } catch {
      expireSession();
      throw new UserFacingError("Your session expired. Please sign in again.");
    }
    res = await post(url, { content }, signal);
  }
  if (!res.ok || !res.body) throw await errorFromResponse(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line) as StreamEvent;
      if (event.type === "delta") onDelta(event.text);
      else if (event.type === "error") throw new UserFacingError(event.detail);
      else return { conversation: event.conversation, messages: event.messages };
    }
    if (done) break;
  }
  throw new UserFacingError("The reply was cut off. Please try again.");
}

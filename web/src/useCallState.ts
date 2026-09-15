/** Whose turn it is, in one word, for the label beside the orb.
 *
 * A voice call has no cursor and no spinner, so the one thing the screen owes
 * the user is whether it is their turn. Derived from the transport and the
 * bot's own events rather than tracked anywhere — there is no state here that
 * could disagree with the call.
 *
 * The transport being connected is NOT the same as the agent being up: the
 * browser joins the room first and the bot arrives seconds later, if it arrives
 * at all. Saying "Listening" in that gap is the screen asserting something it
 * has no evidence for, and a pipeline that dies on setup then sits there
 * claiming to listen for as long as the user is willing to talk to it. So the
 * turn stays unknown until the bot says it is ready, and goes to `dropped` the
 * moment it leaves.
 */

import { RTVIEvent } from "@pipecat-ai/client-js";
import { usePipecatClientTransportState, useRTVIClientEvent } from "@pipecat-ai/client-react";
import { useCallback, useState } from "react";

export type CallState = "offline" | "joining" | "listening" | "thinking" | "speaking" | "dropped";

type Turn = "listening" | "thinking" | "speaking" | "dropped";

const JOINING = ["initializing", "authenticating", "authenticated", "connecting"];

export function useCallState(): CallState {
  const transport = usePipecatClientTransportState();
  // null until the bot has said anything at all.
  const [turn, setTurn] = useState<Turn | null>(null);
  const listening = useCallback(() => setTurn("listening"), []);
  const thinking = useCallback(() => setTurn("thinking"), []);
  const speaking = useCallback(() => setTurn("speaking"), []);
  const dropped = useCallback(() => setTurn("dropped"), []);
  const reset = useCallback(() => setTurn(null), []);

  useRTVIClientEvent(RTVIEvent.BotReady, listening);
  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, listening);
  useRTVIClientEvent(RTVIEvent.BotLlmStarted, thinking);
  useRTVIClientEvent(RTVIEvent.BotStartedSpeaking, speaking);
  useRTVIClientEvent(RTVIEvent.BotStoppedSpeaking, listening);
  useRTVIClientEvent(RTVIEvent.BotDisconnected, dropped);
  // A new call starts over: last call's turn is not this one's.
  useRTVIClientEvent(RTVIEvent.Disconnected, reset);

  if (transport === "connected" || transport === "ready") return turn ?? "joining";
  if (JOINING.includes(transport)) return "joining";
  return "offline";
}

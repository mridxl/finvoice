/** The card state for one call: whatever the server last sent, and what just moved.
 *
 * `Session.push_cards` sends a card only when its digest changes, so an arrival
 * *is* the signal that something moved — nothing is diffed here. That is also
 * why this holds no derived state: the deck is what the server said, and the
 * only local fact is how recently each card arrived.
 */

import { RTVIEvent } from "@pipecat-ai/client-js";
import { useRTVIClientEvent } from "@pipecat-ai/client-react";
import { useCallback, useState } from "react";

import type { Card, CardId, Deck } from "./cards";

/** How long a card stays lit after it changes. Long enough to catch the eye
 *  mid-sentence, short enough that two corrections do not blur together. */
const LIT_MS = 2500;

export function useCards(): { deck: Deck; lit: Set<CardId> } {
  const [deck, setDeck] = useState<Deck>({});
  const [lit, setLit] = useState<Set<CardId>>(new Set());

  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback((data: unknown) => {
      const message = data as { type?: string; card?: Card };
      if (message?.type !== "card" || !message.card) return;
      const card = message.card;
      setDeck((previous) => ({ ...previous, [card.id]: card }));
      setLit((previous) => new Set(previous).add(card.id));
      window.setTimeout(() => {
        setLit((previous) => {
          const next = new Set(previous);
          next.delete(card.id);
          return next;
        });
      }, LIT_MS);
    }, []),
  );

  // A new call is a new conversation. Last call's cards belong to a session the
  // server has already forgotten, and leaving them up would be the one thing
  // cards must never do: disagree with what is being said.
  useRTVIClientEvent(
    RTVIEvent.Connected,
    useCallback(() => {
      setDeck({});
      setLit(new Set());
    }, []),
  );

  return { deck, lit };
}

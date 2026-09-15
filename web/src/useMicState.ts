/** The mic button's state, read from Daily after Daily has finished writing it.
 *
 * The kit's own provider re-reads `client.isMicEnabled` inside the
 * track-started and track-stopped handlers. daily-js emits both from its
 * participant-updated handler *before* it commits the participant state they
 * describe, so the read returns the value the mic just left and the button
 * snaps back to it. Nothing later corrects it: every mute and unmute takes two
 * clicks, and the first visibly undoes itself.
 *
 * The chain is synchronous end to end, so deferring the read by one microtask
 * is enough for the write to have landed. The click sets the state directly —
 * the button moves at once, and a second click during the round trip computes
 * from what the button shows rather than from a stale read.
 */

import { type Participant, RTVIEvent, type TransportState } from "@pipecat-ai/client-js";
import { usePipecatClient, useRTVIClientEvent } from "@pipecat-ai/client-react";
import { useCallback, useState } from "react";

export function useMicState(): readonly [boolean, (enabled: boolean) => void] {
  const client = usePipecatClient();
  const [enabled, setEnabled] = useState(client?.isMicEnabled ?? false);

  const sync = useCallback(() => {
    queueMicrotask(() => setEnabled(client?.isMicEnabled ?? false));
  }, [client]);
  const onLocalAudio = useCallback(
    (track: MediaStreamTrack, participant?: Participant) => {
      if (participant?.local && track.kind === "audio") sync();
    },
    [sync],
  );
  const onTransport = useCallback(
    (state: TransportState) => {
      if (state === "initialized") sync();
    },
    [sync],
  );

  useRTVIClientEvent(RTVIEvent.TransportStateChanged, onTransport);
  useRTVIClientEvent(RTVIEvent.TrackStarted, onLocalAudio);
  useRTVIClientEvent(RTVIEvent.TrackStopped, onLocalAudio);

  const enable = useCallback(
    (next: boolean) => {
      setEnabled(next);
      client?.enableMic(next);
    },
    [client],
  );

  return [enabled, enable] as const;
}

import { PipecatClient } from "@pipecat-ai/client-js";
import { DailyTransport } from "@pipecat-ai/daily-transport";

// One client for the page, created outside React. Building it inside a component
// would make a fresh transport on every render, and StrictMode renders twice in
// development — two transports racing for one microphone.
export const client = new PipecatClient({
  transport: new DailyTransport(),
  enableMic: true,
  enableCam: false,
});

// The browser asks the server to start a call and is told where to join. The
// room, the bot and the token are all minted server-side, so no key and no
// Daily domain is ever compiled into the bundle.
export const CONNECT = { endpoint: "/api/connect" };

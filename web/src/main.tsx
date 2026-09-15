import { PipecatClientAudio, PipecatClientProvider } from "@pipecat-ai/client-react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { client } from "./client";
import "./index.css";

// shadcn themes on a `dark` class rather than the media query, so the system
// preference has to be put onto the element for the theme to follow it.
const dark = window.matchMedia("(prefers-color-scheme: dark)");
const applyTheme = () => document.documentElement.classList.toggle("dark", dark.matches);
dark.addEventListener("change", applyTheme);
applyTheme();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PipecatClientProvider client={client}>
      <App />
      {/* Where the bot's voice actually comes out. It renders nothing. */}
      <PipecatClientAudio />
    </PipecatClientProvider>
  </StrictMode>,
);

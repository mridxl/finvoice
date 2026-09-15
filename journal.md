# Journal

## sat 12 sep, ~10:00 - 
Read what the assignment needs. Realised i had no clue what was going on - had ai write a prerequisite doc to bring me up to speed with why webrtc and not ws, pipecat, daily, processors, RTVI, the complete voice agent pipeline.

decided -> arithmatic will be done in code using tool calls, not on the llm layer. not a difficult call since ai's are known to hallucinate


## sat 12 sep, ~10:30 -

Ai proposed not updating the state and instead to append every revision to it.
Agreed -> gives us the correction capabilities we'd need


## sat 12 sep, ~11:30 -

decided that the planner will rank open questions by whether the answer changes the plan -
we'll re-run the plan with the unknown's ranges and if the outcome doesn't change, the agent won't 't ask.

also decided when the ai needs to stop-> no remaining gap changes the outcome → done.


## sat 12 sep, ~ 4 pm -
got sick, didn't do anything till monday eve - rethought constraints to speed up the dev for after i get better

found out more about pipecat, looked at examples, ui library (chose this one), etc


## mon 14 sep, ~20:15 - 
started working again. realised my prerequisites doc was wrong and ai had hallucinated pipecat's docs and signature from an older, depcrecated version.
Had ai update the docs -> went through them again.

decided to pin versions, verified every signature using ai - just toe be sure.


## mon 14 sep, ~20:20 - 
read what turn detection is plus how we could implement it.
Ai suggested VAD or smart turn v3 -> decided smart turn v3 as the default with VAD as the fallback.
Smart turn just seemed better in a throwaway test i did.


## mon 14 sep, ~20:25 - 
Wrote the spec down, started with the implementation.
had ai copy whatever it could from pipecat's quickstart and examples.
decided to hand-roll fastapi, but keep the eval transport from the example - might help in optional task B.


## mon 14 sep, ~21:00 - 
decided providers - deepgram STT, cartesia TTS, openai for the model. all behind an env-switched
factory.

had ai compare prices for a ten-minute call. 
- deepgram + cartesia ≈ $0.16,
- deepgram + openai TTS ≈ $0.11, 
- openai-only ≈ $0.09. 

cartesia is a lil expensive - about 2× openai TTS -> decided to use it cause it offered sub-100ms TTFB against 300–500ms with others


## mon 15 sep - 
couldn't get openai to work without a cc, chose to add gemini as the second model for the absense of key
to not be a blocker in dev.

had ai verify it'd work in a throwaway setup - comparing signatures, how big the change surface would be, etc

decided to use 3.8-flash
had ai pull the price table - realised 3.8/3.7/3.6 are priced the same -> picked the newest cause better.


## tue 15 sep - 
had my first real call after ai had built the pipeline. gave the agent the demo facts and it told me the month
was infeasible -> realised it confused dates. for example - today's the 15th, so a payment on 5th means it's supposed
to happen on the 5th next month - the ai didn't get that part yet.

options-> plan for a calendar month or plan for the rolling thirty window and say so.
decided to go with the rolling window with an optional env key to choose the start date for this window (for testing)


## tue 15 sep - 
second demo - i said "thirty three thousand for rent and electricity" and the agent gave me the monthly plan without asking me about anything else.

decided to change when a open question or category closed. asked user explicitly before proceeding.
had it write evals so we could ensure the bug didn't get re-introduced.

later today -> noticed the order was breaking again. wrote another eval, made modifications to the prompt



## tue 15 sep - 
noticed some first calls in a fresh container died at exactly 20 seconds with "over after 0 turns" while STT, TTS and daily all reported they were working fine.

Had ai test multiple hypothesis. the actual problem was a race condition in how the different
deferred imports were loaded in the pipeline setup -> had a race condition.
decided to warm the imports at server startup when nothing is waiting. 


## tue 15 sep - 
got an openai key. ran the evals again after switching to luna - all failed.
couple of bugs in how the reasoning was set up differently for gemini and chatgpt.

decided to stick to thinking none -> lowest latency plus tools didn't work with any other thinking level and would give a 100.
also modified the prompts until all evals passed.

changed the flow a bit after comparing my demo with riverline's.


## tue 15 sep - 
i'd had to rotate the cartesia key three times cause i kept running out of credits - despite a generous
free tier. Couldn't figure out why. This also caused evals to fail.
Took a while to find the bug - the eval harness specified that tts and stt won't run during evals - yet they were running.
diagnosed why it was happening with ai; turns out every message after the greeting went to cartesia.
seomthing to do with how user's messages arrived in a RTVI message and pipecat's RTVI processor had a bug
that would quietly ignore the preset option to disable voice. changed how the processors were ordered in
the pipeline.


## tue 15 sep -
had a bug in the mic button where it needed two clicks to change the state and flickered after the first.
the AI's first fix was an optimistic-state hook -> show the click immediately, reconcile later. 

was the wrong call - pipecat ui's button did that already.
fix was owning the mic state on our end, and re-reading it after daily's commit. deleted the optimistic hook.


## tue 15 sep -
decided to go with optional track b - was unsure about what to pick since track a's behaviours were all built in and
i didn't know evals. But the ai generated evals were good enough - they did find out key mistakes in our prompt and the flow -> greatly helped in improving the results.


## tue 15 sep -
a lot of ui refinements and bug fixed.
Ai initially wanted to show all cards at once -> these would update based on tool calls. Disagreed -
decided to have a phase wise flow to provide the end user with a better ux about what was actually going on


## tue 15 sep - 
a lot of cosmetic changes - envs, readme, the prose throughout the repo, etc.
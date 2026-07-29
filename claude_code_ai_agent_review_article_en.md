## Introduction

What happens if you build an AI agent with Claude Code, then have Claude itself review it?

I recently built and open-sourced **AI-Agent-Dev-WBS-OS**, a project that structures the AI-adoption process and auto-generates a reproducible Work Breakdown Structure (WBS) from a stated goal, using Claude Code. This post focuses less on the implementation itself and more on an unusual verification step I ran after building it: having Claude independently review its own output.

- Repo: https://github.com/codebay88/AI-Agent-Dev-WBS-OS
- License: MIT

## What I built

The project combines two agents with very different natures.

### AI Adoption Support Agent (protocol-type)

This agent structures an ambiguous goal or problem into something solvable, using Claude's reasoning ability directly. It isn't implemented as Python code — the role definition and system prompt in `.claude/agents/` *are* the implementation. If it detects vague language (like "roughly," "the usual amount," "flexibly"), it triggers HITL (human-in-the-loop) review before proceeding.

### AI-WBS Generation Agent (code-type)

This agent takes the structured goal and runs it through a nine-stage pipeline, F10 (objective structuring) through F90 (final output generation), to produce the actual WBS. It's deterministic Python code that relies only on the standard library.

```mermaid
flowchart LR
    U["Goal text"] --> F10["F10 Objective structuring"]
    F10 --> F20["F20 Objective expansion"]
    F20 --> F30["F30 Element evaluation"]
    F30 --> F40["F40 Task generation"]
    F40 --> F50["F50 Template application"]
    F50 --> F60["F60 MECE check"]
    F60 --> F70["F70 Hierarchy generation"]
    F70 --> F80["F80 Traceability"]
    F80 --> F90["F90 Final output"]
    F90 --> R["WBS + evaluation report"]
```

The MECE check is implemented from scratch using cosine similarity; hierarchy generation uses a hand-rolled Union-Find. Only F10 calls an external API — everything from F20 onward runs fully offline and reproducibly.

## The interesting part: having Claude review its own code

Once the implementation was done, I wanted to know whether the code was actually good enough to publish — not just take the README's self-reported claims at face value, but have Claude (the same model that helped build it) independently read the source and, in part, execute it to verify.

The summary of that review is quoted directly in the README:

> **Claude's independent review summary**: after reading the actual source code and, in part, executing it directly, Claude assessed this project as "good enough quality to publish and sell" (Yes). The safety design (HITL, audit logging) was confirmed to be genuinely implemented in code, matching the WBS specification.

What made this worth writing about wasn't the positive verdict — it's that the same review also disclosed real limitations, unprompted:

- The "execution actions" in Phase 8–10 (deployment, autonomous operation) are explicitly documented in code comments as deterministic simulations; none of them touch real production infrastructure
- The "self-optimization index" (opt_avg = 0.9119) isn't a measured learning outcome — it's a rule-based classification score computed by applying a fixed scoring rubric
- A real bug was found and fixed during the review (an environment-variable name mismatch that would have caused authentication to silently fail)

None of this is false modesty or exaggeration — it's an honest description of what's actually implemented. The "stop safely and require human approval" scaffolding is real and working. The "autonomously execute" and "learn and self-optimize" parts are still placeholders.

## Why disclose the limitations at all

There was a temptation to just lead with the positive verdict. But I've come to believe that projects which are explicit about what they *can't* do yet tend to earn more trust than ones that only show their best angle.

In this case, having Claude review its own work without me editing the verdict produced something reasonably close to an objective quality check — not a fully independent audit (it's a sampling review, not exhaustive), but a useful signal. The bigger takeaway I want to share here: having the same AI that built the code also inspect it afterward is a workflow that's easy to reproduce, and it might be a practical way to add a layer of quality transparency to AI-built projects in general.

## A small aside: fixing CI the same way

Right after publishing, the GitHub Actions "Tests" badge turned red. The cause was mundane: the workflow ran the bare `pytest tests/ -v`, and in a clean CI environment that doesn't add the repo root to `sys.path` — resulting in `ModuleNotFoundError: No module named 'src'`. Switching to `python -m pytest tests/ -v` fixed it. A textbook case of "works on my machine, fails in CI," worth mentioning here too.

## Summary

- Built and published an open-source project combining a protocol-type "AI Adoption Support Agent" and a code-type "AI-WBS Generation Agent," using Claude Code
- After development, had Claude independently review its own code and published both the strengths and the limitations in the README
- Having the same AI that wrote the code inspect it afterward turned out to be a practical way to keep quality claims honest

Code and README (English/Japanese) are here — take a look if you're curious:

https://github.com/codebay88/AI-Agent-Dev-WBS-OS

# OpenShot Decision Record

## Decision

ReupBanConten will continue on the existing AI-first video remix architecture. We will not integrate or embed `openshot-qt` into the current project.

OpenShot remains useful as a reference project, but it is not the right primary direction for this codebase right now.

## Why We Are Not Using openshot-qt Directly

`openshot-qt` is a full desktop video editor. ReupBanConten is an automated AI pipeline:

```text
scan -> download -> analyze -> highlight scoring -> smart cut -> remix -> render
```

Embedding a full editor would add a second large UI, duplicate responsibilities with the existing PySide6 app, and make packaging harder on Windows. It also does not solve the highest-value problem for this project: finding the best combat-sports hooks and remixing them automatically.

Main reasons to avoid direct integration:

- ReupBanConten already owns the UI and workflow.
- The product goal is automation, not manual editing.
- OpenShot UI code would increase maintenance and packaging complexity.
- `openshot-qt` is GPLv3, which can affect redistribution choices.
- The current bottleneck is highlight selection and render reliability, not editor UI.

## What We Keep From The OpenShot Research

The useful idea is not the GUI. The useful idea is a clean render boundary:

```text
RemixScript
  -> TimelinePlan
      -> FFmpeg backend
      -> MoviePy backend
      -> optional future libopenshot backend
```

This can be implemented without bringing OpenShot into the project immediately. If a future version needs advanced keyframed timeline rendering, `libopenshot` can be evaluated as an optional backend only after the existing pipeline is stable.

## Current Development Direction

Priority stays on the existing architecture:

1. Improve combat-sports highlight detection.
2. Make the cutter produce stronger hooks.
3. Make remix sequencing more coherent and less repetitive.
4. Stabilize the existing MoviePy/FFmpeg render path.
5. Add a neutral timeline abstraction only when it reduces real complexity.

## Near-Term Upgrade Roadmap

### Phase 1: Combat Highlight Analyzer

Build a fast analyzer for boxing, MMA, Muay Thai, kickboxing, BJJ, wrestling, judo, and similar sports.

Signals:

- impact-like audio spikes,
- sudden motion bursts,
- commentary keywords,
- crowd reaction,
- replay/slow-motion sections,
- close-up reaction moments.

Output:

- ranked highlight candidates,
- hook time,
- start/end cut windows,
- reason labels such as `impact`, `knockdown`, `submission`, `scramble`, `reaction`.

### Phase 2: Hook-Oriented Smart Cutter

Improve cuts for viewer retention:

- start near the strongest visual/audio beat,
- add 0.5-1.0s context before the impact,
- keep payoff short,
- optionally append replay/reaction,
- reject dead time and flat audio.

Target clip shape:

```text
0.0s-1.5s: hook
1.5s-4.5s: payoff/action
4.5s-6.0s: reaction/replay if available
```

### Phase 3: Render Reliability

Keep the current renderer but organize it better:

- keep FFmpeg for accurate cuts, subtitles, and post-processing,
- keep MoviePy for current composition features,
- isolate render logic behind a backend interface,
- add preview/final render profiles,
- add render diagnostics and timeline debug JSON.

### Phase 4: Optional Timeline Backend

Only after the above phases are stable:

- evaluate whether `libopenshot` is worth adding as an optional backend,
- do not import or copy `openshot-qt` UI,
- keep MoviePy/FFmpeg as the default fallback.

## Practical Next Tasks

1. Add `src/analyzer/combat_sports.py`.
2. Add models for combat highlight candidates.
3. Add CLI command `combat-cut`.
4. Store combat tags in the clip database.
5. Add remix strategy `combat-hooks`.
6. Add tests with synthetic audio spikes and transcript keywords.

## Final Position

Continue improving ReupBanConten's current AI pipeline. Use OpenShot as a reference for timeline concepts only. Do not make OpenShot a core dependency at this stage.


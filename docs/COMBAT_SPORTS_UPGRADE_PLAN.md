# Combat Sports Upgrade Plan

## Goal

Optimize ReupBanConten for boxing, MMA, Muay Thai, kickboxing, BJJ, wrestling, judo, and other combat sports. The system should find short, high-retention moments: sudden impact, knockdown, submission threat, takedown, scramble, referee intervention, crowd spike, commentary spike, replay, and emotional reaction.

## Highlight Scoring

Use a multi-signal score instead of scene cuts alone:

| Signal | Weight | Examples |
| --- | ---: | --- |
| Impact | 0.30 | punch/kick lands, knockdown, body shot, slam |
| Motion burst | 0.20 | fast exchange, scramble, takedown chain |
| Crowd/audio spike | 0.18 | crowd roar, commentator raises voice, bell/clap |
| Commentary intensity | 0.14 | "knockout", "he is hurt", "submission", "down" |
| Camera/edit event | 0.10 | replay, close-up, fast camera cut |
| Replay/slowmo | 0.08 | slow-motion impact confirmation |

Initial threshold: `min_highlight_score = 0.72`.

## Clip Shape

Use punchy Shorts pacing:

| Segment | Duration | Purpose |
| --- | ---: | --- |
| Hook | 0.8-1.5s | Start at the loudest/most visual impact or reaction. |
| Setup | 1.0-2.0s | Show one beat before the key moment. |
| Payoff | 1.5-3.5s | Strike, knockdown, takedown, submission, or reaction. |
| Replay/CTA | 1.0-2.5s | Optional slow replay or caption punchline. |

Default exported highlight: 2.5-6.0s, with `0.8s` pre-action and `1.2s` post-action padding.

## Pipeline Upgrades

1. Audio-first fast pass
   - Compute RMS/peak/onset spikes with `librosa`.
   - Mark crowd/commentary bursts.
   - Use this as cheap candidate generation before visual AI.

2. Visual action pass
   - Detect hard cuts and motion bursts with OpenCV frame difference/optical flow.
   - Flag camera shake, ring/cage center activity, and replays/slowmo.
   - Later: add pose/action recognition for strike, takedown, guard pass, submission.

3. Transcript keyword pass
   - Use Whisper segments and keyword scoring:
     `knockout`, `knocked down`, `hurt`, `submission`, `tap`, `slam`, `big shot`,
     Vietnamese equivalents such as `gục`, `đấm trúng`, `hạ knock-out`, `khóa siết`, `đập sàn`.

4. Combat highlight ranker
   - Merge audio, visual, and transcript candidates within +/- 1.5s.
   - Score each candidate with the configured weights.
   - Suppress duplicates from the same exchange.

5. Hook-oriented cutter
   - Start clips at the most intense frame/audio beat, not necessarily scene start.
   - Add pre-action padding only when it improves context.
   - Export variants: `hook_first`, `setup_first`, `slowmo_replay`.

6. Sports-aware remixer
   - Sequence by intensity: shock hook -> setup -> best exchange -> replay/reaction.
   - Avoid more than 3 segments from the same fight/source.
   - Prefer close-up reactions after impact.

## Implementation Sprints

### Sprint 1: Fast Heuristic Ranker

- Add `src/analyzer/combat_sports.py`.
- Implement audio spike detection, transcript keyword scoring, and motion burst scoring.
- Output `KeyMoment` entries with `highlight_score`, `reason`, and `hook_time`.

### Sprint 2: Cutter Integration

- Add CLI command: `combat-cut --input video.mp4 --sport mma --top 20`.
- Export clips using existing `SmartClipper`.
- Store tags: `combat`, `impact`, `knockdown`, `submission`, `scramble`, `reaction`.

### Sprint 3: Remix Strategy

- Add remix strategy `combat-hooks`.
- Script format: Hook -> Setup -> Payoff -> Replay/Reaction.
- Add subtitles tuned for short, high-impact Vietnamese commentary.

### Sprint 4: Model Upgrade

- Add optional action classifier:
  - local: pose/optical-flow heuristic first,
  - cloud: Twelve Labs/Gemini review for final ranking.
- Cache all expensive perception outputs.

## Performance Targets

| Metric | Target |
| --- | ---: |
| Candidate generation speed | > 5x realtime on CPU |
| Full highlight ranking | > 1x realtime on CPU |
| Best-moment precision | > 80% on manually labeled fights |
| Duplicate highlights | < 10% |
| Average hook start delay | < 1.0s from clip start |


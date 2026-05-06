# Combat Commentary, Subtitle, And Transition Review

## Verdict

The project already has the basic technical pieces for commentary, voiceover,
subtitles, and transitions, but it is not yet strong enough to guarantee
professional combat-sports commentary.

Current status:

| Area | Current Level | Assessment |
| --- | --- | --- |
| Commentary writing | Basic | LLM writes exciting lines, but does not yet verify facts against exact fight events. |
| Voiceover | Usable | ElevenLabs/Edge-TTS path exists, but no sport-specific pacing or emotion control. |
| Subtitles | Usable | ASS subtitle burn-in exists, but word-level sync and highlight effects are incomplete. |
| Transitions | Basic | Crossfade and visual randomization exist, but combat-specific cut rules are not enforced. |
| Professional accuracy | Weak | No hard rule prevents invented fighter names, wrong strike type, wrong result, or overclaiming. |

## Main Risk

For combat sports, wrong commentary is worse than boring commentary.

The system must not say:

- knockout when the clip only shows a knockdown,
- submission when there is only a guard exchange,
- left hook when the strike is unclear,
- fighter names when they are not known,
- referee stoppage when the referee has not stopped the bout,
- "champion", "title fight", or round information unless metadata proves it.

If the evidence is uncertain, commentary must use safer language:

- "một cú ra đòn rất nặng"
- "đối thủ có dấu hiệu choáng"
- "pha áp sát cực nhanh"
- "tình huống có thể đổi chiều trận đấu"

## Professional Commentary Standard

A strong Vietnamese combat-sports commentary line should meet all rules:

1. Accurate
   - Only describe what the transcript, visual signal, or metadata supports.
   - Use uncertain phrasing when signal confidence is low.

2. Timed
   - Hook line starts before or exactly on the action.
   - Payoff line lands within 0.5s after impact/submission/reaction.
   - No long explanation over the most important visual moment.

3. Sport-aware
   - Boxing/kickboxing: jab, cross, hook, uppercut, low kick, head kick, body shot.
   - MMA: takedown, ground-and-pound, scramble, choke, armbar, tap, referee stoppage.
   - Wrestling/judo: level change, throw, slam, control, reversal.

4. Short-form optimized
   - Each line should be 6-14 Vietnamese words.
   - Avoid generic filler like "thật là tuyệt vời" unless tied to a specific action.
   - Open with consequence, not background.

5. Professional tone
   - Energetic but not fake.
   - Do not scream every line.
   - Use contrast: calm setup -> explosive payoff -> short reaction.

## Required Commentary Pipeline Upgrade

The current pipeline should be upgraded from:

```text
RemixStep -> LLM writes commentary -> TTS -> subtitles
```

to:

```text
CombatHighlight
  -> evidence packet
      - transcript segment
      - signal kinds and scores
      - hook_time
      - visual/API labels
      - known metadata
  -> factual commentary draft
  -> fact-check pass
  -> timing pass
  -> TTS
  -> ASS subtitles with effects
```

## Evidence Packet

Before writing commentary, every clip should expose this structured context:

```json
{
  "sport": "mma",
  "start_time": 12.2,
  "hook_time": 13.0,
  "end_time": 16.4,
  "signals": ["impact", "motion", "crowd_audio", "api_semantic"],
  "confidence": 0.91,
  "transcript": "Huge right hand, he is hurt!",
  "visual_labels": ["clean strike", "fighter hurt"],
  "known_facts": {
    "fighter_a": null,
    "fighter_b": null,
    "round": null,
    "result": null
  }
}
```

If a field is `null`, commentary cannot invent it.

Current implementation now builds this input from:

- `CombatHighlight.start_time`, `hook_time`, `end_time`,
- all highlight signals such as `impact`, `motion`, `crowd_audio`,
  `api_semantic`,
- transcript segments overlapping the highlight window,
- word timestamps overlapping the highlight window,
- semantic API labels from `api_semantic` reasons,
- known metadata when available.

The key addition is `timeline`: every signal, transcript segment, and word is
converted to clip-relative time. This lets commentary and subtitles target the
same moment the viewer sees on screen.

Example:

```json
{
  "timeline": [
    {"type": "transcript_segment", "time": 0.4, "end": 1.2, "text": "Big shot lands"},
    {"type": "impact", "time": 0.8, "score": 0.9, "reason": "keyword:big shot"},
    {"type": "motion", "time": 1.0, "score": 0.8, "reason": "motion_burst"}
  ]
}
```

Remaining gap: the generic Remix v2 script path still creates commentary from
`RemixStep.commentary_text`. The combat-specific path should call
`CombatCommentaryGenerator` directly from ranked highlights so voiceover text,
subtitle timing, and visual hook time share the same evidence packet.

The `combat-cut` command now supports this combat-specific path:

```powershell
python -m src.main combat-cut `
  --input .\data\downloads\fight.mp4 `
  --transcript .\data\transcripts\fight.json `
  --top 10 `
  --write-commentary `
  --commentary-language vi
```

For each exported clip it writes:

- `*.commentary.json`: highlight, commentary segment, and evidence timeline,
- `*.ass`: burn-in subtitle file using the configured subtitle style.

This is the first practical bridge between visual highlight timing and the
voiceover/subtitle layer. The next step is to optionally generate TTS audio per
clip and mux it into the exported highlight.

Vertical export:

- `combat-cut` now exports highlights as 1080x1920 vertical clips.
- The vertical filter uses the common FFmpeg short-video pattern:
  blurred full-frame background plus centered foreground.
- This keeps the original fight action visible, avoids black bars, and keeps
  subtitle placement aligned with the ASS canvas.
- Use `--vertical-mode copy` to keep the original source format and fast
  stream-copy path for debugging or archival exports.

Language selection:

- The Remix UI commentary language selector now drives the script prompt, so
  `title`, `description`, and every `commentary_text` are requested in that
  selected language.
- `combat-cut --write-commentary` accepts `--commentary-language`, so subtitle
  and commentary assets can be generated in the requested language.
- Supported country language choices:

| UI choice | Code | Output language / voice |
| --- | --- | --- |
| Viet Nam | `vi` | Vietnamese |
| Hoa Ky (My) | `en-US` | American English |
| Vuong quoc Anh (Anh) | `en-GB` | British English |
| Phap | `fr-FR` | French |
| Duc | `de-DE` | German |
| Nhat Ban | `ja-JP` | Japanese |
| Han Quoc | `ko-KR` | Korean |
| Brazil | `pt-BR` | Brazilian Portuguese |

## Recommended Prompt Rules

Use a strict system prompt for professional commentary:

```text
Bạn là bình luận viên thể thao đối kháng chuyên nghiệp.
Chỉ bình luận dựa trên evidence được cung cấp.
Không bịa tên võ sĩ, hiệp đấu, kết quả, đai vô địch, chấn thương, hoặc luật.
Nếu evidence chưa chắc chắn, dùng ngôn ngữ thận trọng.
Viết tiếng Việt tự nhiên, mạnh, ngắn, đúng nhịp Shorts.
Mỗi câu 6-14 từ.
Không dùng emoji. Không dùng hashtag.
```

Output should be structured:

```json
{
  "segments": [
    {
      "start_time": 0.0,
      "duration_estimate": 1.2,
      "text": "Đòn này mở ra nguy hiểm ngay lập tức.",
      "emotion": "tense",
      "evidence_used": ["motion", "impact"],
      "certainty": "medium"
    }
  ],
  "warnings": []
}
```

## Subtitle Effects Standard

Current ASS subtitle generation is a good base, but word-highlight is currently
not implemented. For combat shorts, subtitle style should follow these rules:

| Moment | Subtitle Style |
| --- | --- |
| Setup | White text, smaller, no animation or light fade-in |
| Impact | Yellow/red keyword, scale pop, thick outline |
| Knockdown/submission | Two-line max, center-bottom, high contrast |
| Replay | "Xem lại pha này" style, slower fade |
| CTA | Small, clean, not blocking action |

Technical requirements:

- Burn subtitles with FFmpeg ASS for final render.
- Keep text inside safe area for 9:16.
- Max 2 lines, max 16 characters per line preferred for Vietnamese Shorts.
- Support keyword coloring for words like `gục`, `knockout`, `siết`, `đòn`, `ngã`.
- Use word timestamps when available; otherwise estimate by syllable count.

## Subtitle Editing UI

The Remix page now follows the same user-facing idea as CapCut-style caption
editing: the user can apply a subtitle style globally, then tune the important
visual controls before rendering.

Available controls:

- enable or disable subtitle burn-in,
- choose preset: `CapCut Yellow`, `Modern White`, `Glow Pink`, `Elegant Gold`,
  `Neon Cyber`,
- edit font family,
- edit font size,
- choose position: bottom, center, top,
- choose effect: impact pop, fade, replay fade, none,
- edit outline width,
- edit max characters per line,
- enable or disable action keyword highlighting,
- preview the subtitle look inside the UI.

This does not copy CapCut. It applies the same workflow pattern: editable text
style, clear presets, position controls, and short-form caption effects.

Reference notes checked during implementation:

- CapCut-style caption workflows commonly generate captions first, then let the
  user edit text blocks and apply font/size/color/style changes globally.
- Caption panels commonly expose style, animation/effect, and layout controls.
- Batch/apply-to-all styling is important so Shorts subtitles stay consistent.

## Transition Effects Standard

Combat sports should avoid decorative transitions that hide the action.

Use:

- hard cut on impact,
- very short crossfade only between non-action moments,
- speed ramp before impact,
- replay flash only after payoff,
- subtle zoom on hook if the source framing is wide.

Avoid:

- long crossfades over strikes,
- meme/image overlays during the exact impact,
- mirror effect if it changes stance interpretation,
- aggressive color shifts that obscure gloves/limbs.

## Implementation Plan

### Sprint 1: Commentary Quality Gate

- Add `CombatCommentaryGenerator`.
- Build evidence packets from `CombatHighlight`.
- Generate structured commentary JSON.
- Reject lines that mention unsupported facts.
- Add tests for "no invented knockout/name/round/result".

### Sprint 2: Timing And Subtitle Effects

- Extend `CommentarySegment` with:
  - `evidence_used`
  - `certainty`
  - `style`
  - `keywords`
- Implement ASS keyword highlighting and impact pop tags.
- Add line wrapping for vertical video safe area.

### Sprint 3: Professional Voiceover Pacing

- Add style presets:
  - `calm_setup`
  - `explosive_payoff`
  - `replay_analysis`
  - `cta_clean`
- Tune TTS speed and pauses by segment type.
- Duck original audio less during crowd reaction, more during explanation.

### Sprint 4: Render Rules For Combat

- Add transition policy:
  - `hard_cut_on_impact`
  - `no_overlay_during_impact`
  - `replay_after_payoff`
- Export timeline debug JSON for every remix.
- Add automated checks for subtitle overlap and clip validity.

## Quality Targets

| Metric | Target |
| --- | ---: |
| Unsupported factual claims | 0 |
| Commentary line length | 6-14 Vietnamese words |
| Subtitle max lines | 2 |
| Subtitle safe-area violations | 0 |
| Voiceover overlap with impact audio | < 20% of impact windows |
| Human rating for professional feel | >= 4/5 |

## Final Assessment

Continue using the current pipeline, but do not rely on generic LLM commentary
for combat sports. The next high-value upgrade is a fact-constrained commentary
layer that writes only from evidence, then a subtitle renderer that emphasizes
the exact hook moment without covering the action.

# UI Workflow Review

This document defines the intended responsibility of the three AI workflow tabs:
Combat Studio, Analyzer, and Remixer. The goal is to avoid duplicate user
decisions while keeping each tool focused.

## Recommended Flow

1. Scanner downloads source videos.
2. Cutter creates generic reusable clips when needed.
3. Analyzer prepares assets: transcript, visual/LLM analysis, Twelve Labs index.
4. Combat Studio creates finished combat-sports highlight clips from one fight video.
5. Remixer assembles a new topic-driven video from the prepared clip library.

For combat sports, the shortest production path is:

```text
Combat Studio
  -> source fight video
  -> transcript or Whisper
  -> hook/highlight ranking
  -> vertical 9:16 export
  -> evidence-based commentary
  -> subtitles and voiceover
  -> final MP4
```

## Tab Responsibilities

### Combat Studio

Purpose: one fight video to final combat highlight outputs.

Combat Studio owns:

- combat hook detection and ranking
- 9:16 vertical export with blur or copy mode
- evidence-based fight commentary
- subtitle/voiceover/final MP4 generation
- output audit for final video quality

Combat Studio may call Whisper or semantic API search, but only as pipeline
helpers for the current fight video.

### Analyzer

Purpose: prepare and inspect reusable assets.

Analyzer owns:

- Whisper transcription for selected videos/clips
- LLM content analysis
- visual analysis
- Twelve Labs indexing and summaries
- manual inspection before assets are reused elsewhere

Analyzer should not render final videos. Its outputs should feed Combat Studio
or Remixer when the user wants better prepared metadata.

### Remixer

Purpose: assemble a new video from a clip library.

Remixer owns:

- topic/RAG prompt input
- AI script generation
- clip selection from local/vector/API sources
- voiceover, subtitle style, and final assembly for multi-clip videos

Remixer should use prepared clips. It should not duplicate combat-specific hook
ranking, because that belongs in Combat Studio.

## Current Overlap

The overlap is intentional but should be labeled clearly:

- Whisper exists in Analyzer and Combat Studio.
  Analyzer uses it to prepare reusable transcripts; Combat Studio uses it only
  when the selected fight video has no transcript.
- Twelve Labs exists in Analyzer, Combat Studio, and Remixer.
  Analyzer indexes assets; Combat Studio uses semantic matches to improve combat
  highlight ranking; Remixer searches the clip library for a topic.
- Language, voiceover, and subtitles exist in Combat Studio and Remixer.
  Combat Studio applies them to each combat highlight; Remixer applies them to a
  topic-driven assembled video.

## Next Improvements

1. Share subtitle style settings between Combat Studio and Remixer.
2. Add "Send to Combat Studio" from Analyzer for the selected video/transcript.
3. Add "Send outputs to Remixer library" from Combat Studio after clips are ready.
4. Rename helper options in Combat Studio to make them clearly automatic helpers:
   "Auto-transcribe if missing" and "Use indexed semantic matches".
5. Keep Remixer focused on assembled videos, not single-fight highlight ranking.

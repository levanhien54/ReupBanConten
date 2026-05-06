# Combat API Evaluation Guide

This guide measures the upgraded combat-sports highlight pipeline after adding
semantic video API signals.

## What Changed

- `combat-cut` can merge local signals with semantic API matches:
  - transcript keywords: knockdown, KO, submission, takedown, crowd reaction
  - optional audio spikes
  - optional OpenCV motion bursts
  - optional Twelve Labs semantic matches through `--use-api`
- `combat-index` uploads a source video into the semantic video index.
- `combat-search-api` checks semantic matches before cutting clips.

## Recommended Workflow

1. Index one source video:

```powershell
python -m src.main combat-index --input .\data\downloads\fight.mp4 --index-id YOUR_INDEX_ID
```

2. Check semantic matches:

```powershell
python -m src.main combat-search-api --index-id YOUR_INDEX_ID --limit 20
```

3. Rank locally plus API, without export:

```powershell
Measure-Command {
  python -m src.main combat-cut `
    --input .\data\downloads\fight.mp4 `
    --transcript .\data\transcripts\fight.json `
    --use-api `
    --index-id YOUR_INDEX_ID `
    --dry-run
}
```

4. Export final clips:

```powershell
Measure-Command {
  python -m src.main combat-cut `
    --input .\data\downloads\fight.mp4 `
    --transcript .\data\transcripts\fight.json `
    --use-api `
    --index-id YOUR_INDEX_ID `
    --top 10
}
```

## Speed Metrics

Record these numbers for every test video:

| Metric | How to Measure | Good Target |
| --- | --- | --- |
| API index time | `combat-index` wall clock | One-time cost per source video |
| API search time | `combat-search-api` wall clock | Under 10s after indexing |
| Dry-run ranking time | `combat-cut --dry-run` wall clock | Faster than video duration |
| Export time | `combat-cut --top 10` wall clock | Depends mostly on FFmpeg |
| Clips per minute | exported clips / total minutes | Stable for same content type |

Local transcript-only ranking is usually the fastest path. API search adds value
when footage has little commentary, fast action, replays, or visual-only hooks.

## Quality Scorecard

Review the top 10 exported clips and score each item from 1 to 5:

| Item | Meaning | Target |
| --- | --- | --- |
| Hook strength | The first 1-3 seconds make the viewer keep watching | 4+ |
| Action clarity | Strike, takedown, submission, or reaction is visible | 4+ |
| Dead time | Setup is not too long before the action | 4+ |
| Audio energy | Crowd/commentary supports the moment | 3+ |
| Duplicate control | Clips do not repeat the same moment too often | 4+ |
| Output validity | No black frames, broken audio, or corrupt file | 5 |

Average target: `4.0/5` or higher for selected clips.

## Interpreting Results

- If speed is good but quality is weak, lower `min_highlight_score` only after
  improving query text and transcript coverage.
- If clips start too late, increase `pre_action_padding`.
- If clips feel slow, reduce `target_clip_duration` or `post_action_padding`.
- If API matches are noisy, make `api_query` more specific to the sport.
- If local and API signals agree on the same timestamp, those clips should be
  prioritized because they have stronger evidence.

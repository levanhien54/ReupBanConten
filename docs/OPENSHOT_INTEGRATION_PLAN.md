# OpenShot Integration Plan

## Research Summary

OpenShot is split into two useful projects:

- `openshot-qt`: the full desktop video editor UI, written in Python/Qt.
- `libopenshot`: the media engine behind OpenShot, written in C++ with Python bindings.

For ReupBanConten, the practical integration target is `libopenshot`, not embedding `openshot-qt`. The current project already has a PySide6 UI and an AI pipeline; importing the full OpenShot editor would duplicate UI responsibilities and add a large dependency surface. `libopenshot` is a better fit for timeline assembly, transitions, keyframes, effects, and rendering.

Sources:

- https://github.com/OpenShot/openshot-qt
- https://github.com/OpenShot/libopenshot

## Why Use libopenshot

Current ReupBanConten rendering is mostly:

- MoviePy for composition and transitions.
- FFmpeg subprocesses for cuts, subtitles, color grading, and final render.

That works for prototypes, but it becomes fragile when the project needs real timeline features:

- multi-track video/audio,
- keyframed zoom/pan/position,
- consistent crossfades and transitions,
- reusable timeline/project representation,
- better preview/final render separation,
- richer effects without manually writing FFmpeg filters for every case.

`libopenshot` can become a render backend while the existing AI pipeline remains responsible for selecting highlights and producing `RemixScript`.

## Recommended Architecture

Add a backend boundary:

```text
RemixScript
  -> TimelinePlan
      -> MoviePy backend (current fallback)
      -> FFmpeg backend (fast/simple concat/cut)
      -> OpenShot backend (advanced timeline)
```

Do not call OpenShot directly from `RemixOrchestratorV2`. Keep the orchestrator stable and let it choose a renderer from config:

```yaml
render:
  backend: "moviepy"  # moviepy | ffmpeg | openshot
  preview_resolution: "480x854"
  final_resolution: "1080x1920"
```

## Proposed Modules

```text
src/remixer/render_backends/
  __init__.py
  base.py
  moviepy_backend.py
  ffmpeg_backend.py
  openshot_backend.py
  timeline_plan.py
```

`timeline_plan.py` should define a neutral internal timeline:

```python
class TimelineClip(BaseModel):
    source_path: str
    source_start: float = 0.0
    source_end: float | None = None
    timeline_start: float = 0.0
    duration: float
    track: int = 0
    speed: float = 1.0
    zoom: float = 1.0
    brightness: float = 1.0
    contrast: float = 1.0
    mirror: bool = False
    transition_in: str = "cut"
    transition_duration: float = 0.0
    audio_path: str | None = None
```

Then each backend maps that neutral model to its own implementation.

## OpenShot Backend Responsibilities

The first `openshot_backend.py` should support only the features already used by `VideoAssembler`:

- place clips in sequence,
- trim source start/end,
- set speed,
- add crossfade,
- set output FPS/resolution,
- render to MP4,
- keep unsupported effects as no-ops with warnings.

After that, add:

- keyframed zoom/pan for 9:16 shorts,
- multi-track overlays,
- voiceover track,
- BGM ducking track,
- title/subtitle layers,
- preview render profile.

## Integration Steps

### Phase 1: Backend Boundary

1. Create `TimelinePlan` and `RenderBackend` interface.
2. Move current MoviePy logic from `VideoAssembler` into `MoviePyBackend`.
3. Keep `VideoAssembler.assemble()` public API unchanged.
4. Add config flag for backend selection.
5. Test that current remixer still works with MoviePy.

### Phase 2: OpenShot Proof of Concept

1. Add optional dependency documentation for `libopenshot` Python bindings.
2. Implement `OpenShotBackend.is_available()`.
3. Render a 2-clip timeline with one crossfade.
4. Add a smoke test that skips when `openshot` module is unavailable.

### Phase 3: Feature Parity

1. Map `RemixStep.start_time/end_time` to OpenShot clip trim.
2. Map speed, mirror, brightness/contrast, zoom.
3. Add voiceover track.
4. Add ASS/subtitle burn as a final FFmpeg post-step until OpenShot title rendering is stable.

### Phase 4: UI Integration

1. Add Settings option: `Render backend`.
2. Add diagnostics: backend availability and installed versions.
3. Add preview render button.
4. Add timeline export/debug JSON for failed render investigations.

## Licensing Notes

Important:

- `openshot-qt` is GPLv3.
- `libopenshot` is LGPLv3.

If ReupBanConten stays private/local, this is mostly operational. If distributed commercially, prefer integrating with `libopenshot` as a dynamically linked optional backend and keep attribution/license notices. Avoid copying large parts of `openshot-qt` UI code into this project unless accepting GPLv3 obligations for the combined work.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Windows install complexity | High | Keep MoviePy/FFmpeg fallback. Make OpenShot optional. |
| Python binding version mismatch | Medium | Add `is_available()` and skip tests if missing. |
| Timeline API learning curve | Medium | Start with 2-clip proof of concept. |
| Larger render dependency | Medium | Backend selection via config. |
| License confusion | High | Use `libopenshot` backend, not copied `openshot-qt` UI. |

## Decision

Recommended path: integrate OpenShot through an optional `libopenshot` render backend after introducing a neutral timeline abstraction. Do not embed the full `openshot-qt` application into ReupBanConten.


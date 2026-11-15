# BLOODLINE anime pipeline — implementation notes

## What this branch fixes

- Storyboard API failures are no longer silently converted into locally generated text-only projects.
- The prompt studio labels the current step as **episode storyboard**, not finished video.
- The prompt studio checks and displays the backend's anime-engine connectivity status.
- The backend exposes `GET /api/generator/capabilities`.
- ComfyUI's server address can be configured with `COMFYUI_BASE_URL`, including a remote server URL.

## Important current limitation

This branch does **not** yet generate anime images or animate characters. A reachable ComfyUI server alone is not sufficient: it also needs compatible image-generation and image-to-video workflows, models, and GPU capacity. The capability endpoint intentionally reports `anime_generation_ready: false` until an actual generation workflow is implemented and verified. FFmpeg only assembles media that already exists; it does not create anime character animation from text.

## Intended production pipeline

1. Convert the episode prompt into a structured scene list.
2. Generate reference sheets for Diamond, Eternity Infinity, and Murder Co.
3. Generate each scene image using a configured anime image workflow.
4. Animate each scene using a configured image-to-video workflow.
5. Preserve character references and visual settings between scenes.
6. Assemble generated clips, narration, music, and subtitles into an MP4 using FFmpeg.
7. Verify that the output file exists and can be decoded before showing a download link.

## Deployment configuration

Set `COMFYUI_BASE_URL` on the backend to the reachable ComfyUI server base URL, for example `https://your-comfyui-host.example` (do not include `/system_stats`). The ComfyUI server must be reachable from the backend container. A ComfyUI service running only on the Android phone's `127.0.0.1` is not reachable from a hosted Render backend.

Do not add API keys or credentials to source control. Store any provider credentials in the hosting platform's environment settings.

## Cost and device expectations

The editor and FFmpeg assembly can be free. Actual generative video is compute-intensive: a free, unlimited, hosted GPU service should not be assumed. Running ComfyUI locally generally requires a capable computer/GPU; a phone can control a hosted generation backend but usually cannot run the full model stack itself.

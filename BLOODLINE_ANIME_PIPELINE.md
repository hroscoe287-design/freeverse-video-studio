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

## Connect the real generation engine

1. Run ComfyUI on a machine with a compatible GPU, or use a trusted hosted ComfyUI service. A Render free web service cannot supply the GPU required by current video diffusion models.
2. In ComfyUI, build or import a workflow and switch it to **API format** (ComfyUI's Save (API Format) option).
3. The workflow must accept a positive prompt token `__PROMPT__` and a negative prompt token `__NEGATIVE_PROMPT__`. A seed field can use `__SEED__`. Put these exact tokens in the appropriate text/seed inputs before saving the API workflow JSON.
4. For actual moving character footage, the workflow must be a text-to-video or image-to-video workflow with a video output node (for example, a compatible video-combine node that writes MP4/WebM/GIF). A workflow that ends in SaveImage creates still artwork only.
5. Make the workflow JSON file available to the backend container, then set:
   - `COMFYUI_BASE_URL=https://your-comfyui-host`
   - `COMFYUI_WORKFLOW_JSON=/absolute/path/to/workflow_api.json`
   - optionally `COMFYUI_TIMEOUT_SECONDS=900`
6. Restart the backend and check `GET /api/generator/capabilities`. It should report `comfyui_reachable=true` and `anime_generation_ready=true`.
7. In the app, create the BLOODLINE storyboard, choose **Generate Anime Scenes**, wait for all scenes to finish, then render/export the MP4.

The backend substitutes the prompt tokens, queues the workflow, polls ComfyUI, downloads its first video/GIF/image output for each scene, attaches the media to the project, and lets the existing FFmpeg renderer assemble it. If the workflow returns still images, the final MP4 uses camera motion on those images; it is not character animation. The workflow's model weights, custom nodes, and GPU memory must be installed and compatible on the ComfyUI host.

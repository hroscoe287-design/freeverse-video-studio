# ROSCOE AI ANIME ENGINE

## What we are building

Roscoe Anime Engine is FreeVerse's own generation orchestration and character-continuity layer. It combines two downloadable open-weight models rather than calling StarryAI or another paid image API:

| Stage | Model | Job | License |
|---|---|---|---|
| Anime keyframes | [Neta Lumina v1.0](https://huggingface.co/neta-art/Neta-Lumina) | Anime character art, storyboards, scene keyframes | Apache-2.0 |
| Motion generation | [Wan 2.2 TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) | Turn a keyframe into a short video clip (text/image-to-video) | Apache-2.0 |

The application adds a BLOODLINE visual bible, negative prompt, per-scene prompt conditioning, keyframe upload, image-to-video handoff, and episode assembly. The engine is our software and configuration; the upstream model weights are not owned by us and are not bundled into Git.

## How one scene is generated

1. Build a scene prompt using the episode, scene, and character context.
2. Run Neta Lumina through a ComfyUI API-format workflow to generate the keyframe.
3. Upload that keyframe to ComfyUI's input endpoint.
4. Run Wan 2.2 TI2V-5B through a second API-format workflow. The workflow reads the `__IMAGE__` token and animates the image.
5. Attach the generated clip to the scene and assemble the episode with FFmpeg.

## Required GPU host

The Android phone is the remote controller, not the model runtime. The image model's published setup currently calls for ComfyUI and at least 8 GB VRAM. Wan 2.2 TI2V-5B is a 5B-parameter video model; it needs a compatible GPU and significant memory/storage. Render's free CPU web service cannot host these model weights and perform inference.

No model is trained from scratch in this commit. That would require a large licensed training dataset and substantial GPU compute. The practical next step toward a genuinely custom Roscoe checkpoint is to build a rights-cleared character-reference dataset for Diamond, Eternity Infinity, and Murder Co., then train a compatible LoRA/adapter. Hugging Face documents LoRA as a parameter-efficient fine-tuning method, but Neta Lumina's model card says its training ecosystem is still evolving; verify the exact compatible trainer before starting a run.

## ComfyUI workflow contract

Two ComfyUI API-format workflow templates ship in `backend/workflows/` and are selected automatically by default:

- `roscoe_neta_lumina_api.json`: Neta Lumina keyframe generation.
- `roscoe_wan22_i2v_api.json`: Wan 2.2 TI2V-5B image-to-video generation.

You can override them on the backend with `ROSCOE_IMAGE_WORKFLOW_JSON` and `ROSCOE_VIDEO_WORKFLOW_JSON` if your installed ComfyUI build uses different node versions or model filenames.
- `COMFYUI_BASE_URL`: address reachable by the backend.
- `COMFYUI_API_KEY`: optional bearer token, only if the host requires it.
- `COMFYUI_TIMEOUT_SECONDS`: optional generation timeout (default 900).

Both workflows must accept `__PROMPT__`, `__NEGATIVE_PROMPT__`, and optionally `__SEED__`. The video workflow must load the uploaded image using `__IMAGE__`. The image workflow must return an image; the video workflow should return a video/GIF output. Workflows must use the exact model files and custom nodes installed on the ComfyUI host.

The app's `GET /api/generator/engine` endpoint reports selected models, ComfyUI reachability, and whether both workflow files exist. This is a configuration check, not proof that model inference succeeds. A real end-to-end test still requires the GPU host, model weights, and compatible ComfyUI nodes.

## Character training plan

Do not train on copyrighted anime screenshots or art without permission. Build a small, consistent set of original/authorized images for each character, with varied angles, expressions, poses, clothing, and lighting. Caption each image with the same unique character trigger and stable visual traits. Keep a held-out validation set so we can test identity consistency rather than memorizing training images. Once the chosen model's compatible trainer is confirmed, fine-tune a small adapter first; do not attempt to train a base model from scratch.

## Environment example

See `backend/.env.roscoe-anime.example`. Never commit actual keys or private host URLs.

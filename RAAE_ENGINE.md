# ROSCOE ADAPTIVE ANIME ENGINE (RAAE)

RAAE is the generation orchestrator used by the existing FreeVerse/BLOODLINE workflow. It is designed to improve image quality per unit of worker compute while keeping the Android client lightweight.

## What it does

1. **Remote inference, local control.** The phone sends prompts and receives generated media; it does not download or execute multi-billion-parameter diffusion/video weights.
2. **Live model-pool routing.** Before a job, RAAE reads AI Horde's live image-model status endpoint. It prefers currently served anime-oriented checkpoints (Animagine, Illustrious, NoobAI, Pony, and other anime-tuned families) and scores them using specialization, worker count, reported performance, and queue depth.
3. **Adaptive sampler budget.** Distilled / Lightning / Turbo / LCM model names receive an 8-step budget; anime SDXL-family models receive 24 steps; unknown models receive a 20-step safe default. Canvas dimensions are rounded to multiples of 64 and kept moderate to avoid wasting volunteer GPU time.
4. **Character-aware prompt compilation.** Each shot receives a stable visual-style brief, a dedicated character-continuity block, and the scene-specific action/camera content. The negative prompt suppresses common anatomy, duplicate-subject, text, watermark, and rendering defects.
5. **Progress feedback.** The background job reports model selection and queue wait instead of leaving the user with a generic “generating” spinner.
6. **Existing project integration.** Returned images are stored in the existing FreeVerse asset index and attached to the scene. The current FFmpeg renderer remains responsible for producing the playable MP4.

## Why these choices

- Latent diffusion moves denoising into a compressed latent space instead of full pixel space, which is a major compute reduction.
- Distillation/consistency methods can reduce the number of denoising steps substantially. The engine therefore gives known few-step model families smaller sampling budgets instead of applying one expensive setting to every model.
- Lightweight image adapters such as IP-Adapter demonstrate that reference-image conditioning can be added without fine-tuning the entire base model. This is the next character-consistency upgrade, subject to compatible worker support.
- Video models use temporal compression and distilled inference to reduce video-generation cost, but even a 2B/5B video model is not realistically a phone-local model for a midrange Android device. The phone should remain the editor/controller, not the inference machine.

## Important limits

- AI Horde is a shared volunteer GPU network. Anonymous requests are free but may wait, and the available model pool changes. The engine falls back to automatic worker routing when it cannot identify an anime-specific live model.
- This release produces actual AI-generated anime keyframes. The existing no-GPU fallback animates those images with camera movement and FFmpeg; that is not the same as AI-generated character motion.
- Wan 2.2 TI2V-5B and LTX video families remain optional remote video-model routes. Their model weights and runtime requirements are too large to bundle into the Android APK.
- RAAE is a new orchestration design built on existing open models and published techniques; it is not a newly trained foundation model.

## Configuration

Optional:
- `AI_HORDE_API_KEY`: a personal AI Horde key can improve queue priority; the anonymous key is used when omitted.
- `AI_HORDE_BASE_URL`: override the API base for testing.
- `COMFYUI_BASE_URL`, `ROSCOE_IMAGE_WORKFLOW_JSON`, `ROSCOE_VIDEO_WORKFLOW_JSON`: optional private ComfyUI image/video workflows. If configured and reachable, the existing two-stage workflow can provide true model-generated motion.

No new environment variable is required for the free anonymous image route.

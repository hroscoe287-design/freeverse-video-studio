import { Project, AssetMeta, RenderStatus, AIModelInfo, HardwareInfo, VideoStyle, AspectRatio, Resolution } from '../types/studio';

const API_BASE = '/api';

const LOCAL_PROJECTS_KEY = 'roscoes-freeverse-projects-v1';
const readLocalProjects = (): Project[] => { try { return JSON.parse(localStorage.getItem(LOCAL_PROJECTS_KEY) || '[]') as Project[]; } catch { return []; } };
const writeLocalProjects = (items: Project[]) => localStorage.setItem(LOCAL_PROJECTS_KEY, JSON.stringify(items));
const makeLocalProject = (p: { title: string; style: VideoStyle; aspect_ratio: AspectRatio; resolution: Resolution; fps: number }): Project => { const now = new Date().toISOString(); return { id: `local_${Date.now()}_${Math.random().toString(36).slice(2,8)}`, title:p.title, description:'Created in Roscoe’s offline studio.', style:p.style, aspect_ratio:p.aspect_ratio, resolution:p.resolution, fps:p.fps, scenes:[], audio_tracks:[], created_at:now, updated_at:now }; };
const saveLocalProject = (p: Project) => { const all=readLocalProjects(); const i=all.findIndex(x=>x.id===p.id); if(i<0) all.unshift(p); else all[i]=p; writeLocalProjects(all); };


export async function fetchProjects(): Promise<Project[]> {
  try { const r=await fetch(`${API_BASE}/projects`); if(!r.ok) throw Error(); return await r.json(); } catch { return readLocalProjects(); }
}

export async function createProject(payload: {
  title: string;
  style: VideoStyle;
  aspect_ratio: AspectRatio;
  resolution: Resolution;
  fps: number;
}): Promise<Project> {
  try { const r=await fetch(`${API_BASE}/projects`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); if(!r.ok) throw Error(); return await r.json(); } catch { const p=makeLocalProject(payload); saveLocalProject(p); return p; }
}

export async function getProject(id: string): Promise<Project> {
  try { const r=await fetch(`${API_BASE}/projects/${id}`); if(!r.ok) throw Error(); return await r.json(); } catch { const p=readLocalProjects().find(x=>x.id===id); if(!p) throw Error('Project not found'); return p; }
}

export async function updateProject(id: string, payload: Partial<Project>): Promise<Project> {
  try { const r=await fetch(`${API_BASE}/projects/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); if(!r.ok) throw Error(); return await r.json(); } catch { const p=readLocalProjects().find(x=>x.id===id); if(!p) throw Error('Project not found'); const u={...p,...payload,updated_at:new Date().toISOString()}; saveLocalProject(u); return u; }
}

export async function deleteProject(id: string): Promise<void> {
  try { const r=await fetch(`${API_BASE}/projects/${id}`,{method:'DELETE'}); if(!r.ok&&r.status!==404) throw Error(); } catch { writeLocalProjects(readLocalProjects().filter(x=>x.id!==id)); }
}

export async function duplicateProject(id: string): Promise<Project> {
  try { const r=await fetch(`${API_BASE}/projects/${id}/duplicate`,{method:'POST'}); if(!r.ok) throw Error(); return await r.json(); } catch { const p=await getProject(id); const c={...p,id:`local_${Date.now()}`,title:`${p.title} (Copy)`,created_at:new Date().toISOString(),updated_at:new Date().toISOString()}; saveLocalProject(c); return c; }
}

export async function fetchAssets(): Promise<AssetMeta[]> {
  const res = await fetch(`${API_BASE}/assets`);
  if (!res.ok) throw new Error('Failed to fetch assets');
  return res.json();
}

export async function uploadAsset(file: File): Promise<AssetMeta> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/assets/upload`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function deleteAsset(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/assets/${id}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete asset');
}

function buildOfflineStoryboard(params: { prompt: string; style: VideoStyle; target_duration: number; scene_count: number; include_voiceover: boolean }): Project {
  const prompt = params.prompt.trim();
  const count = Math.max(1, Math.min(20, params.scene_count || 6));
  const duration = Math.max(2, params.target_duration / count);
  const bloodline = /bloodline|diamond|eternity infinity|murder co/i.test(prompt);
  const beats = ['Opening image and atmosphere', 'Introduce the hero', 'A mystery begins to unfold', 'The threat reveals itself', 'A decisive confrontation', 'A powerful final image'];
  const sentences = prompt.split(/(?<=[.!?])\\s+/).filter(Boolean);
  const scenes = Array.from({ length: count }, (_, index) => {
    const beat = beats[index % beats.length];
    const detail = sentences[index % Math.max(1, sentences.length)] || prompt;
    const continuity = bloodline ? ' Keep BLOODLINE character designs consistent: Diamond is the central hero, Eternity Infinity is his sister, and Murder Co. is the opposing force.' : '';
    return {
      id: 'offline_scene_' + Date.now() + '_' + index,
      title: 'Scene ' + String(index + 1).padStart(2, '0') + ' — ' + beat,
      duration, text_overlay: index === 0 ? 'A ROSCOE ORIGINAL' : '',
      text_position: 'bottom' as const, text_color: '#FFFFFF', font_size: 30,
      transition: 'fade' as const, transition_duration: 0.45,
      motion_effect: index % 2 === 0 ? 'ken_burns_zoom_in' as const : 'pan_right' as const,
      voiceover_text: params.include_voiceover ? detail + ' Visual direction: ' + beat + '. Anime cinematic composition, expressive acting, dramatic lighting.' + continuity : undefined,
      background_color: index % 2 === 0 ? '#111827' : '#1B1530', order: index
    };
  });
  const now = new Date().toISOString();
  const project: Project = { id: 'local_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8), title: bloodline ? 'BLOODLINE — The Legacy' : 'Untitled Anime Project', description: prompt, style: params.style, aspect_ratio: '16:9', resolution: '720p', fps: 24, scenes, audio_tracks: [], created_at: now, updated_at: now };
  saveLocalProject(project);
  return project;
}
export async function generateStoryboard(params: {
  prompt: string; style: VideoStyle; target_duration: number; scene_count: number; include_voiceover: boolean; source_document?: string;
}): Promise<Project> {
  try {
    const r = await fetch(`${API_BASE}/generator/storyboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) });
    if (!r.ok) throw new Error('Offline mode');
    return await r.json();
  } catch {
    return buildOfflineStoryboard(params);
  }
}

export async function generateFromDocument(file: File, style: VideoStyle, duration: number): Promise<Project> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('style', style);
  formData.append('target_duration', duration.toString());
  const r = await fetch(`${API_BASE}/generator/document-storyboard`, { method: 'POST', body: formData });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Document storyboard service unavailable' }));
    throw new Error(err.detail || 'Document processing failed.');
  }
  return r.json();
}

export async function startRender(projectId: string, quality: 'draft' | 'standard' | 'high' = 'standard'): Promise<RenderStatus> {
  const res = await fetch(`${API_BASE}/render/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, quality })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to start render' }));
    throw new Error(err.detail || 'Failed to start render');
  }
  return res.json();
}

export async function getRenderStatus(jobId: string): Promise<RenderStatus> {
  const res = await fetch(`${API_BASE}/render/status/${jobId}`);
  if (!res.ok) throw new Error('Failed to fetch render status');
  return res.json();
}

export async function cancelRender(jobId: string): Promise<void> {
  await fetch(`${API_BASE}/render/cancel/${jobId}`, {
    method: 'POST'
  });
}

export async function fetchModels(): Promise<AIModelInfo[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) throw new Error('Failed to fetch AI models');
  return res.json();
}

export async function fetchHardwareInfo(): Promise<HardwareInfo> {
  const res = await fetch(`${API_BASE}/models/hardware`);
  if (!res.ok) throw new Error('Failed to fetch hardware specs');
  return res.json();
}

export interface GeneratorCapabilities {
  storyboard: boolean;
  ffmpeg_render: boolean;
  comfyui_configured: boolean;
  comfyui_reachable: boolean;
  anime_generation_ready: boolean;
  workflow_configured?: boolean;
  workflow_file_exists?: boolean;
  detail: string;
  engine?: {
    name: string;
    version: string;
    ready: boolean;
    note: string;
    models: Record<string, { name: string; id: string; license: string; model_url: string; description: string; minimum_vram_gb?: number }>;
  };
}

export async function fetchGeneratorCapabilities(): Promise<GeneratorCapabilities> {
  const r = await fetch(`${API_BASE}/generator/capabilities`);
  if (!r.ok) throw new Error('Could not check the anime generation engine.');
  return r.json();
}

export interface AnimeGenerationStatus {
  job_id: string;
  project_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  error?: string | null;
}

export async function startAnimeGeneration(projectId: string): Promise<AnimeGenerationStatus> {
  const r = await fetch(`${API_BASE}/generator/anime/start/${encodeURIComponent(projectId)}`, { method: 'POST' });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Could not start anime generation.' }));
    throw new Error(err.detail || 'Could not start anime generation.');
  }
  return r.json();
}

export async function getAnimeGenerationStatus(jobId: string): Promise<AnimeGenerationStatus> {
  const r = await fetch(`${API_BASE}/generator/anime/status/${encodeURIComponent(jobId)}`);
  if (!r.ok) throw new Error('Could not read anime generation progress.');
  return r.json();
}

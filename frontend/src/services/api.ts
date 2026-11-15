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

export async function generateStoryboard(params: {
  prompt: string;
  style: VideoStyle;
  target_duration: number;
  scene_count: number;
  include_voiceover: boolean;
  source_document?: string;
}): Promise<Project> {
  try { const r=await fetch(`${API_BASE}/generator/storyboard`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)}); if(!r.ok) throw Error(); return await r.json(); } catch { const lines=params.prompt.split(/(?<=[.!?])\s+|\n+/).map(x=>x.trim()).filter(Boolean); const fallback=['Establish the world and its danger.','The hero discovers a clue about their legacy.','A powerful enemy reveals the threat.','The hero makes a choice that changes everything.','A dramatic confrontation erupts.','End on a suspenseful cliffhanger.']; const p=makeLocalProject({title:params.prompt.slice(0,48)||'New Story',style:params.style,aspect_ratio:params.style==='social'?'9:16':'16:9',resolution:'1080p',fps:30}); p.description=params.prompt; p.scenes=Array.from({length:params.scene_count},(_,i)=>({id:`scene_${i+1}`,title:`Scene ${i+1}`,duration:params.target_duration/params.scene_count,text_overlay:lines[i]||fallback[i%6],voiceover_text:params.include_voiceover?(lines[i]||fallback[i%6]):'',text_position:'bottom' as const,text_color:'#FFFFFF',font_size:32,transition:'fade' as const,transition_duration:0.5,motion_effect:'ken_burns_zoom_in' as const,background_color:'#151525',order:i})); saveLocalProject(p); return p; }
}

export async function generateFromDocument(file: File, style: VideoStyle, duration: number): Promise<Project> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('style', style);
  formData.append('target_duration', duration.toString());
  
  try { const r=await fetch(`${API_BASE}/generator/document-storyboard`,{method:'POST',body:formData}); if(!r.ok) throw Error(); return await r.json(); } catch { const content=await file.text(); return generateStoryboard({prompt:content,style,target_duration:duration,scene_count:Math.max(2,Math.min(6,Math.ceil(duration/8))),include_voiceover:true}); }
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

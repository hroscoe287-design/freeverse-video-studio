import React, { useEffect, useState } from 'react';
import { Sparkles, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { Project } from '../types/studio';
import { AnimeGenerationStatus, getAnimeGenerationStatus, getProject, startAnimeGeneration } from '../services/api';

interface AnimeGenerationPanelProps {
  project: Project;
  onProjectUpdated: (project: Project) => void;
}

export const AnimeGenerationPanel: React.FC<AnimeGenerationPanelProps> = ({ project, onProjectUpdated }) => {
  const [job, setJob] = useState<AnimeGenerationStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = starting || job?.status === 'queued' || job?.status === 'running';

  useEffect(() => {
    if (!job || (job.status !== 'queued' && job.status !== 'running')) return;
    let active = true;
    const poll = async () => {
      try {
        const next = await getAnimeGenerationStatus(job.job_id);
        if (!active) return;
        setJob(next);
        if (next.status === 'completed') {
          const updated = await getProject(project.id);
          if (active) onProjectUpdated(updated);
        } else if (next.status === 'failed') {
          setError(next.error || next.message || 'Anime image generation failed.');
        }
      } catch (err: any) {
        if (active) setError(err.message || 'Could not check anime generation progress.');
      }
    };
    const timer = window.setInterval(poll, 4000);
    return () => { active = false; window.clearInterval(timer); };
  }, [job?.job_id, job?.status, project.id]);

  const handleGenerate = async () => {
    if (project.id.startsWith('local_')) {
      setError('This project is saved only on this device. Reopen or create it while connected to the FreeVerse backend, then try again.');
      return;
    }
    setStarting(true);
    setError(null);
    setJob(null);
    try {
      const started = await startAnimeGeneration(project.id);
      setJob(started);
    } catch (err: any) {
      setError(err.message || 'Could not start real anime image generation.');
    } finally {
      setStarting(false);
    }
  };

  return (
    <section style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, fontSize: '13px' }}>
            <Sparkles size={16} color="var(--primary)" /> Real Anime Image Generation
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Sends each scene to free community AI image workers. This is separate from storyboard creation.
          </div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={handleGenerate} disabled={busy || project.scenes.length === 0}>
          {busy ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
          {busy ? 'Generating…' : 'Generate Anime Images'}
        </button>
      </div>
      {job && (
        <div style={{ marginTop: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '5px' }}>
            <span>{job.message}</span><strong>{Math.round(job.progress || 0)}%</strong>
          </div>
          <div style={{ height: '7px', background: 'var(--bg-tertiary)', borderRadius: '8px', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, job.progress || 0))}%`, background: 'var(--primary)', transition: 'width .3s ease' }} />
          </div>
          {job.status === 'completed' && <div style={{ color: '#10B981', fontSize: '11px', marginTop: '7px', display: 'flex', alignItems: 'center', gap: '5px' }}><CheckCircle2 size={13} /> Real images attached. You can now render the MP4.</div>}
        </div>
      )}
      {error && <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}><AlertCircle size={13} /> {error}</div>}
    </section>
  );
};

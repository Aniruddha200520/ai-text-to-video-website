import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, Download, Play, Settings, Image, FileText, X, Upload, GripVertical, Copy, RefreshCw, Save, FolderOpen, Music, Volume2, Check } from 'lucide-react';

// ── ElevenLabs voice IDs (always on, no toggle needed) ──
const VOICE_WILL    = 'bIHbv24MWmeRgasZH58o'; // Will    — male
const VOICE_JESSICA = 'cgSgspJ2msm6clMCkdW9'; // Jessica — female
const VOICE_GTTS    = 'gtts';                   // Google TTS — free, default when no avatar

const voiceForGender = (gender) =>
  gender === 'female' ? VOICE_JESSICA : VOICE_WILL;

export default function VideoCreator() {
  const getApiUrl = () => {
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      return import.meta.env.VITE_API_URL || 'http://localhost:5001';
    }
    return 'http://localhost:5001';
  };

  const API = getApiUrl();

  const fetchAPI = (url, options = {}) =>
    fetch(url, { ...options, headers: { 'ngrok-skip-browser-warning': 'true', ...options.headers } });

  useEffect(() => {
    fetchAPI(`${API}/api/health`)
      .then(r => r.json())
      .then(d => console.log('✅ API:', d))
      .catch(e => console.error('❌ API:', e));
  }, [API]);

  // ── core state ──
  const [project, setProject]         = useState('my_video');
  const [text, setText]               = useState('');
  const [scenes, setScenes]           = useState([]);
  const [loading, setLoading]         = useState(false);
  const [splitting, setSplitting]     = useState(false);
  const [videoUrl, setVideoUrl]       = useState(null);
  const [status, setStatus]           = useState('');

  // ── visual / subtitle settings ──
  const [subtitles, setSubtitles]         = useState(true);
  const [subtitleStyle, setSubtitleStyle] = useState('bottom');
  const [fontSize, setFontSize]           = useState(24);

  // ── voices (loaded silently, always on) ──
  const [voices, setVoices]           = useState([]);

  // ── script generator ──
  const [showScript, setShowScript]     = useState(false);
  const [scriptTopic, setScriptTopic]   = useState('');
  const [scriptStyle, setScriptStyle]   = useState('educational');
  const [scriptDuration, setScriptDuration] = useState(60);
  const [genScript, setGenScript]       = useState(false);

  // ── render progress ──
  const [progress, setProgress]   = useState(0);
  const [stage, setStage]         = useState('');
  const [rendering, setRendering] = useState(false);
  const [estimatedTime, setEstimatedTime] = useState(0);

  // ── drag ──
  const [draggedIdx, setDraggedIdx] = useState(null);

  // ── bulk edit ──
  const [showBulk, setShowBulk] = useState(false);
  const [bulkDur, setBulkDur]   = useState(5);
  const [bulkVoice, setBulkVoice] = useState('');

  // ── retry ──
  const [retrying, setRetrying] = useState(new Set());

  // ── stock media ──
  const [showStock, setShowStock]         = useState(false);
  const [stockQuery, setStockQuery]       = useState('');
  const [stockResults, setStockResults]   = useState([]);
  const [loadingStock, setLoadingStock]   = useState(false);
  const [selectedForStock, setSelectedForStock] = useState(null);
  const [stockMediaType, setStockMediaType] = useState('image');

  // ── music ──
  const [selectedMusic, setSelectedMusic] = useState(null);
  const [musicVolume, setMusicVolume]     = useState(10);

  // ── avatar ──
  const [useAvatar, setUseAvatar]         = useState(false);
  const [avatarPosition, setAvatarPosition] = useState('bottom-right');
  const [avatarSize, setAvatarSize]       = useState('medium');
  const [avatarStyle, setAvatarStyle]     = useState('male');

  // ── base UI generate mode (static/dynamic toggle for "Generate All") ──
  const [generateMode, setGenerateMode] = useState('dynamic');

  // ── one-click pipeline ──
  // FIX: default pipelineMode to 'dynamic' as requested
  const [showPipeline, setShowPipeline]     = useState(false);
  const [pipelineTopic, setPipelineTopic]   = useState('');
  const [pipelineStyle, setPipelineStyle]   = useState('educational');
  const [pipelineDuration, setPipelineDuration] = useState(60);
  const [pipelineAvatar, setPipelineAvatar] = useState('disabled');
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineSteps, setPipelineSteps]   = useState([]);
  const [pipelineDone, setPipelineDone]     = useState(false);
  const [pipelineError, setPipelineError]   = useState('');
  const [pipelineMode, setPipelineMode]     = useState('dynamic'); // FIX: default to dynamic

  const progressTimerRef = useRef(null);
  const renderStartRef   = useRef(null);

  // ── computed ──
  const totalDur   = scenes.reduce((s, sc) => s + (parseFloat(sc.duration) || 0), 0);
  const totalWords = scenes.reduce((s, sc) => s + (sc.text?.split(' ').length || 0), 0);
  const withImages = scenes.filter(s => s.background_path).length;

  useEffect(() => {
    setEstimatedTime(scenes.length === 0 ? 0 : Math.max(0, 5 + scenes.length * 15));
  }, [scenes.length]);

  const [resolvedWill, setResolvedWill]       = useState(VOICE_WILL);
  const [resolvedJessica, setResolvedJessica] = useState(VOICE_JESSICA);

  useEffect(() => {
    fetchAPI(`${API}/api/voices`, { method: 'GET', headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' } })
      .then(r => r.json())
      .then(d => {
        if (d.success && Array.isArray(d.voices)) {
          setVoices(d.voices);
          const willV    = d.voices.find(v => v.name?.toLowerCase().trim() === 'will');
          const jessicaV = d.voices.find(v => v.name?.toLowerCase().trim() === 'jessica');
          if (willV)    setResolvedWill(willV.voice_id);
          if (jessicaV) setResolvedJessica(jessicaV.voice_id);
        }
      })
      .catch(() => {});
  }, [API]);

  // ── progress animation ──
  const STAGES = [
    { pct: 5,  label: 'Initializing...',          ms: 800  },
    { pct: 12, label: 'Generating audio (TTS)...', ms: 4000 },
    { pct: 22, label: 'Running Wav2Lip...',        ms: 10000 },
    { pct: 40, label: 'Animating avatar...',       ms: 10000 },
    { pct: 52, label: 'Loading alpha mask...',     ms: 2000  },
    { pct: 60, label: 'Compositing frames...',     ms: 120000 },
    { pct: 88, label: 'Encoding video...',         ms: 15000 },
    { pct: 94, label: 'Encoding audio...',         ms: 6000  },
  ];

  const startProgressAnimation = () => {
    renderStartRef.current = Date.now();
    let idx = 0;
    setProgress(0); setStage(STAGES[0].label);
    const tick = () => {
      if (idx >= STAGES.length - 1) return;
      const cur = STAGES[idx], nxt = STAGES[idx + 1];
      const t0 = Date.now();
      const interp = () => {
        const frac = Math.min((Date.now() - t0) / cur.ms, 1);
        setProgress(Math.round(cur.pct + (nxt.pct - cur.pct) * frac));
        if (frac < 1) progressTimerRef.current = setTimeout(interp, 80);
        else { idx++; if (idx < STAGES.length) { setStage(STAGES[idx].label); progressTimerRef.current = setTimeout(tick, 100); } }
      };
      interp();
    };
    progressTimerRef.current = setTimeout(tick, 200);
  };

  const stopProgress = (ok) => {
    if (progressTimerRef.current) clearTimeout(progressTimerRef.current);
    ok ? (setProgress(100), setStage('Complete! ✅')) : (setProgress(0), setStage(''));
  };

  const progressColor = () => {
    if (progress === 100) return 'from-green-500 to-emerald-400';
    if (progress > 60)   return 'from-red-500 to-rose-400';
    if (progress > 30)   return 'from-red-600 to-pink-500';
    return 'from-rose-600 to-red-500';
  };

  const fmt = (s) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  const changeAvatarStyle = (gender) => {
    setAvatarStyle(gender);
    const v = gender === 'female' ? resolvedJessica : resolvedWill;
    setScenes(prev => prev.map(s => ({ ...s, voice_id: v })));
  };

  const renderVoiceOptions = () => {
    return (
      <>
        <option value={VOICE_GTTS}>Google TTS</option>
        {voices.length > 0
          ? voices.map(v => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)
          : <>
              <option value={VOICE_WILL}>Will</option>
              <option value={VOICE_JESSICA}>Jessica</option>
            </>
        }
      </>
    );
  };

  // ── script ──
  const genScriptFn = async () => {
    if (!scriptTopic.trim()) { setStatus('❌ Enter a topic'); return; }
    setGenScript(true); setStatus('🤖 Generating script...');
    try {
      const r = await fetchAPI(`${API}/api/generate_script`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic: scriptTopic, style: scriptStyle, duration: scriptDuration }) });
      const d = await r.json();
      if (d.success) { setText(d.script); setStatus(`✅ Generated! (${d.script.split(' ').length} words)`); setShowScript(false); }
      else setStatus(`❌ ${d.error || 'Unknown'}`);
    } catch (e) { setStatus(`❌ ${e.message}`); }
    finally { setGenScript(false); }
  };

  // ── split ──
  const split = async () => {
    if (!text.trim()) { setStatus('❌ Enter text first'); return; }
    setSplitting(true); setStatus('✂️ Splitting...');
    try {
      const r = await fetchAPI(`${API}/api/split`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
      const d = await r.json();
      if (d.scenes) {
        const voice = useAvatar ? (avatarStyle === 'female' ? resolvedJessica : 'gtts') : VOICE_GTTS;
        setScenes(d.scenes.map(s => ({ ...s, image_prompt: '', voice_id: voice })));
        setStatus(`✅ Split into ${d.scenes.length} scenes`);
      } else setStatus(`❌ ${d.error || 'Unknown'}`);
    } catch (e) { setStatus(`❌ ${e.message}`); }
    finally { setSplitting(false); }
  };

  // ── scene helpers ──
  const update   = (i, f, v) => { const u = [...scenes]; u[i][f] = v; setScenes(u); };
  const del      = (i) => { setScenes(scenes.filter((_, j) => j !== i)); setStatus(`🗑️ Scene ${i + 1} deleted`); };
  const add      = () => setScenes([...scenes, { id: `scene_${scenes.length + 1}`, text: 'Enter text...', background_path: '', duration: 5, voice_id: useAvatar ? (avatarStyle === 'female' ? resolvedJessica : resolvedWill) : VOICE_GTTS, image_prompt: '' }]);
  const dup      = (i) => { const s = { ...scenes[i], id: `scene_${scenes.length + 1}` }; const u = [...scenes]; u.splice(i + 1, 0, s); setScenes(u); setStatus(`📋 Scene ${i + 1} duplicated`); };
  const bulk     = () => { setScenes(scenes.map(s => ({ ...s, duration: bulkDur, ...(bulkVoice ? { voice_id: bulkVoice } : {}) }))); setShowBulk(false); setStatus(`✅ Applied to ${scenes.length} scenes`); };

  // ── drag ──
  const handleDragStart = (e, i) => { setDraggedIdx(i); e.dataTransfer.effectAllowed = 'move'; };
  const handleDragOver  = (e, i) => {
    e.preventDefault(); e.dataTransfer.dropEffect = 'move';
    if (draggedIdx === null || draggedIdx === i) return;
    const u = [...scenes]; const d = u[draggedIdx]; u.splice(draggedIdx, 1); u.splice(i, 0, d);
    setDraggedIdx(i); setScenes(u);
  };
  const handleDragEnd = () => setDraggedIdx(null);

  // ── upload ──
  const upload = async (i, file) => {
    if (!file) return;
    const fd = new FormData(); fd.append('file', file); fd.append('scene_id', scenes[i].id);
    try {
      setStatus('📤 Uploading...');
      const r = await fetchAPI(`${API}/api/upload_background`, { method: 'POST', body: fd });
      const d = await r.json();
      if (d.background_path) { update(i, 'background_path', d.background_path); if (d.url) update(i, 'preview_url', `${API}${d.url}`); setStatus('✅ Uploaded!'); }
    } catch (e) { setStatus(`❌ ${e.message}`); }
  };

  // ── stock ──
  const searchStock = async (q) => {
    if (!q.trim()) return;
    setLoadingStock(true); setStatus(`🔍 Searching...`);
    try {
      const ep = stockMediaType === 'video' ? `/api/search_pexels_videos?query=${encodeURIComponent(q)}` : `/api/stock_search?query=${encodeURIComponent(q)}`;
      const d = await (await fetchAPI(`${API}${ep}`)).json();
      if (d.success && d.results) { setStockResults(d.results); setStatus(`✅ Found ${d.results.length}`); }
      else { setStockResults([]); setStatus('❌ No results'); }
    } catch (e) { setStatus(`❌ ${e.message}`); setStockResults([]); }
    finally { setLoadingStock(false); }
  };

  const applyStock = async (media) => {
    if (selectedForStock === null) return;
    try {
      setStatus('📥 Downloading...');
      const ep = stockMediaType === 'video' ? '/api/download_pexels_video' : '/api/download_stock';
      const d = await (await fetchAPI(`${API}${ep}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: media.url, scene_id: scenes[selectedForStock].id, type: media.type }) })).json();
      if (d.success && d.path) { update(selectedForStock, 'background_path', d.path); if (d.url) update(selectedForStock, 'preview_url', `${API}${d.url}`); update(selectedForStock, 'image_source', 'pexels'); setStatus('✅ Applied!'); setShowStock(false); }
      else setStatus(`❌ ${d.error || 'Unknown'}`);
    } catch (e) { setStatus(`❌ ${e.message}`); }
  };

  // ── retry image ──
  const retry = async (i) => {
    setRetrying(prev => new Set(prev).add(i)); setStatus(`🔄 Retrying scene ${i + 1}...`);
    try {
      const d = await (await fetchAPI(`${API}/api/generate_images`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenes: [scenes[i]] }) })).json();
      if (d.images?.[0]?.success) { update(i, 'background_path', d.images[0].background_path); if (d.images[0].url) update(i, 'preview_url', `${API}${d.images[0].url}`); setStatus('✅ Generated!'); }
      else setStatus(`❌ ${d.images?.[0]?.error || 'Unknown'}`);
    } catch (e) { setStatus(`❌ ${e.message}`); }
    finally { setRetrying(prev => { const n = new Set(prev); n.delete(i); return n; }); }
  };

  // ── gen all images (static or dynamic based on generateMode) ──
  const genImages = async () => {
    if (!scenes.length) return;
    setLoading(true);
    setStatus(generateMode === 'dynamic' ? '🎬 Fetching Pexels videos...' : '🎨 Generating images...');
    try {
      const endpoint = generateMode === 'dynamic'
        ? `${API}/api/generate_images_v2_dynamic`
        : `${API}/api/generate_images_v2`;
      const d = await (await fetchAPI(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenes }) })).json();
      if (d.images) {
        const u = [...scenes]; let cnt = 0;
        d.images.forEach(img => { const j = u.findIndex(s => s.id === img.id); if (j >= 0 && img.success) { u[j].background_path = img.background_path; u[j].preview_url = img.url ? `${API}${img.url}` : null; u[j].image_source = img.source; cnt++; } });
        setScenes(u); setStatus(`✅ ${generateMode === 'dynamic' ? 'Videos' : 'Images'} sourced: ${cnt}/${d.images.length}`);
      }
    } catch (e) { setStatus(`❌ ${e.message}`); }
    finally { setLoading(false); }
  };

  // ── music ──
  const uploadMusic = async (file) => {
    if (!file) return;
    const fd = new FormData(); fd.append('file', file);
    try {
      setStatus('📤 Uploading music...');
      const d = await (await fetchAPI(`${API}/api/music/upload`, { method: 'POST', body: fd })).json();
      if (d.success) { setSelectedMusic({ name: file.name, local_path: d.path, custom: true }); setStatus('✅ Music uploaded!'); }
      else setStatus(`❌ ${d.error}`);
    } catch (e) { setStatus(`❌ ${e.message}`); }
  };

  // ── render ──
  const render = async () => {
    if (!scenes.length) { setStatus('❌ Add scenes first'); return; }
    setLoading(true); setRendering(true); setVideoUrl(null); setStatus('🎬 Rendering...'); startProgressAnimation();
    try {
      const d = await (await fetchAPI(`${API}/api/render`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: project, scenes, auto_ai_images: false, subtitles, subtitle_style: subtitleStyle, font_size: fontSize, use_elevenlabs: useAvatar && avatarStyle === 'female', background_music: selectedMusic?.local_path || null, music_volume: musicVolume / 100, use_avatar: useAvatar, avatar_position: avatarPosition, avatar_size: avatarSize, avatar_style: avatarStyle })
      })).json();
      stopProgress(!!d.filename);
      if (d.filename) { setVideoUrl({ download: d.download_url, preview: `${API}/api/video/${d.filename}`, filename: d.filename }); setStatus('✅ Video ready!'); }
      else setStatus(`❌ ${d.error || 'Unknown'}`);
    } catch (e) { stopProgress(false); setStatus(`❌ ${e.message}`); }
    finally { setLoading(false); setRendering(false); }
  };

  const download = () => {
    if (!videoUrl?.filename) return;
    const a = document.createElement('a'); a.href = `${API}/api/video/${videoUrl.filename}?download=true`; a.download = `${project}.mp4`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a); setStatus('📥 Download started!');
  };

  // ── save / load ──
  const save = () => {
    const d = { version: '1.0', project_name: project, settings: { subtitles, subtitleStyle, fontSize, musicVolume, useAvatar, avatarPosition, avatarSize, avatarStyle }, script: text, scenes, music: selectedMusic };
    const b = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
    const u = URL.createObjectURL(b); const l = document.createElement('a'); l.href = u; l.download = `${project}_project.json`;
    document.body.appendChild(l); l.click(); document.body.removeChild(l); URL.revokeObjectURL(u); setStatus('💾 Saved!');
  };

  const load = (e) => {
    const f = e.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = (ev) => {
      try {
        const d = JSON.parse(ev.target.result);
        setProject(d.project_name || 'my_video'); setSubtitles(d.settings?.subtitles ?? true); setSubtitleStyle(d.settings?.subtitleStyle || 'bottom'); setFontSize(d.settings?.fontSize || 24); setMusicVolume(d.settings?.musicVolume || 10); setUseAvatar(d.settings?.useAvatar || false); setAvatarPosition(d.settings?.avatarPosition || 'bottom-right'); setAvatarSize(d.settings?.avatarSize || 'medium'); setAvatarStyle(d.settings?.avatarStyle || 'male'); setText(d.script || ''); setScenes(d.scenes || []); setSelectedMusic(d.music || null); setStatus('📂 Loaded!');
      } catch (err) { setStatus(`❌ Load failed: ${err.message}`); }
    };
    r.readAsText(f); e.target.value = '';
  };

  // ── pipeline helpers ──
  const PIPELINE_STEPS = [
    { id: 'script', label: 'Generating script with AI...', icon: '✍️' },
    { id: 'split',  label: 'Splitting into scenes...',     icon: '✂️' },
    { id: 'images', label: pipelineMode === 'dynamic' ? 'Fetching Pexels videos...' : 'Generating AI images...', icon: '🎨' },
    { id: 'render', label: 'Rendering final video...',     icon: '🎬' },
  ];

  const updateStep = (id, st, detail = '') =>
    setPipelineSteps(prev => {
      const exists = prev.find(s => s.id === id);
      if (exists) return prev.map(s => s.id === id ? { ...s, status: st, detail } : s);
      return [...prev, { id, status: st, detail }];
    });

  const runFullPipeline = async () => {
    if (!pipelineTopic.trim()) { setPipelineError('Please enter a topic first'); return; }
    setPipelineRunning(true); setPipelineDone(false); setPipelineError(''); setPipelineSteps([]); setVideoUrl(null);
    const avatarEnabled = pipelineAvatar !== 'disabled';
    const avatarGender = pipelineAvatar === 'disabled' ? 'male' : pipelineAvatar;
    const voice = avatarEnabled
      ? (avatarGender === 'female' ? resolvedJessica : 'gtts')
      : VOICE_GTTS;
    const autoName = pipelineTopic.trim().toLowerCase().replace(/\s+/g, '_').slice(0, 20);

    try {
      updateStep('script', 'running');
      const sd = await (await fetchAPI(`${API}/api/generate_script`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic: pipelineTopic, style: pipelineStyle, duration: pipelineDuration }) })).json();
      if (!sd.success) throw new Error(sd.error || 'Script failed');
      setText(sd.script);
      updateStep('script', 'done', `${sd.script.split(' ').length} words generated`);

      updateStep('split', 'running');
      const spd = await (await fetchAPI(`${API}/api/split`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: sd.script }) })).json();
      if (!spd.scenes) throw new Error(spd.error || 'Split failed');
      const newScenes = spd.scenes.map(s => ({ ...s, image_prompt: '', voice_id: voice }));
      setScenes(newScenes);
      updateStep('split', 'done', `${newScenes.length} scenes created`);

      const imgEndpoint = pipelineMode === 'dynamic'
        ? `${API}/api/generate_images_v2_dynamic`
        : `${API}/api/generate_images_v2`;
      updateStep('images', 'running');
      const imgd = await (await fetchAPI(imgEndpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenes: newScenes }) })).json();
      let swi = [...newScenes]; let cnt = 0;
      if (imgd.images) {
        imgd.images.forEach(img => { const j = swi.findIndex(s => s.id === img.id); if (j >= 0 && img.success) { swi[j].background_path = img.background_path; swi[j].preview_url = img.url ? `${API}${img.url}` : null; cnt++; } });
        setScenes(swi);
      }
      const modeLabel = pipelineMode === 'dynamic' ? 'videos' : 'images';
      updateStep('images', 'done', `${cnt}/${newScenes.length} ${modeLabel} sourced`);

      updateStep('render', 'running');
      startProgressAnimation(); setRendering(true);
      const rd = await (await fetchAPI(`${API}/api/render`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: autoName, scenes: swi, auto_ai_images: false,
          subtitles, subtitle_style: subtitleStyle, font_size: fontSize,
          use_elevenlabs: useAvatar && avatarStyle === 'female', background_music: selectedMusic?.local_path || null,
          music_volume: musicVolume / 100,
          use_avatar: avatarEnabled, avatar_position: avatarPosition,
          avatar_size: avatarSize,
          avatar_style: avatarGender
        })
      })).json();
      stopProgress(!!rd.filename); setRendering(false);
      if (!rd.filename) throw new Error(rd.error || 'Render failed');
      setVideoUrl({ download: rd.download_url, preview: `${API}/api/video/${rd.filename}`, filename: rd.filename });
      setProject(autoName);
      updateStep('render', 'done', 'Video ready!');
      setPipelineDone(true); setStatus('✅ Pipeline complete!');
    } catch (err) {
      stopProgress(false); setRendering(false);
      setPipelineError(err.message);
      setPipelineSteps(prev => prev.map(s => s.status === 'running' ? { ...s, status: 'error' } : s));
    } finally { setPipelineRunning(false); }
  };

  // ────────────────────────────────────────────────
  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white overflow-hidden">

      {/* HEADER */}
      <div className="flex-shrink-0 bg-black/30 backdrop-blur-sm border-b border-purple-500/30 px-6 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent leading-tight">AdGenesis</h1>
            <p className="text-xs text-slate-400 mt-0.5">Autonomous AI · Next-Gen Video Advertising</p>
          </div>
          <div className="flex items-center gap-3">

            {/* ── One-Click Generate — red pill button ── */}
            <button
              onClick={() => { setShowPipeline(true); setPipelineSteps([]); setPipelineDone(false); setPipelineError(''); }}
              className="select-none"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '7px',
                padding: '8px 22px',
                borderRadius: '999px',
                background: 'linear-gradient(180deg, #f04545 0%, #d42222 100%)',
                boxShadow: '0 4px 15px rgba(240,60,60,0.4), inset 0 1px 0 rgba(255,255,255,0.2)',
                border: 'none',
                color: 'white',
                fontSize: '14px',
                fontWeight: '700',
                letterSpacing: '0.02em',
                cursor: 'pointer',
                outline: 'none',
                transition: 'filter 0.12s ease, transform 0.1s ease',
              }}
              onMouseEnter={e => e.currentTarget.style.filter = 'brightness(1.1)'}
              onMouseLeave={e => e.currentTarget.style.filter = 'brightness(1)'}
              onMouseDown={e => e.currentTarget.style.transform = 'scale(0.96)'}
              onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0 }}>
                <polygon points="1,0 9,5 1,10" fill="white"/>
              </svg>
              One-Click Generate
            </button>

            <button onClick={save} disabled={!scenes.length} className="bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 disabled:opacity-40 px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition-all"><Save size={15} />Save</button>
            <label className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 px-4 py-2 rounded-lg flex items-center gap-2 cursor-pointer text-sm font-medium transition-all"><input type="file" accept=".json" onChange={load} className="hidden" /><FolderOpen size={15} />Load</label>
          </div>
        </div>
      </div>

      {/* BODY */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── LEFT SIDEBAR ── */}
        <div className="w-80 flex-shrink-0 border-r border-purple-500/20 bg-black/15 flex flex-col overflow-hidden">
          {/* Script generator */}
          <div className="p-4 border-b border-purple-500/20 flex-shrink-0">
            <button onClick={() => setShowScript(!showScript)} className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 px-4 py-2.5 rounded-xl flex items-center justify-between text-sm font-semibold transition-all shadow-lg shadow-purple-900/40">
              <span className="flex items-center gap-2"><FileText size={16} />AI Script Generator</span>
              <span className="text-white/60 text-xs">{showScript ? '▲' : '▼'}</span>
            </button>
            {showScript && (
              <div className="mt-3 space-y-2.5">
                <input value={scriptTopic} onChange={e => setScriptTopic(e.target.value)} className="w-full bg-slate-700/60 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:border-purple-500 focus:outline-none" placeholder="Topic..." />
                <div className="grid grid-cols-2 gap-2">
                  <select value={scriptStyle} onChange={e => setScriptStyle(e.target.value)} className="bg-slate-700/60 border border-slate-600 rounded-lg px-2 py-2 text-sm focus:outline-none">
                    <option value="educational">Educational</option><option value="narrative">Narrative</option><option value="promotional">Promotional</option><option value="documentary">Documentary</option><option value="tutorial">Tutorial</option>
                  </select>
                  <input type="number" value={scriptDuration} onChange={e => setScriptDuration(parseInt(e.target.value) || 60)} className="bg-slate-700/60 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none" min="30" max="600" placeholder="Secs" />
                </div>
                <button onClick={genScriptFn} disabled={genScript} className="w-full bg-gradient-to-r from-blue-500 to-purple-500 disabled:opacity-50 py-2 rounded-lg text-sm font-semibold transition-all">{genScript ? '⏳ Generating...' : '✨ Generate Script'}</button>
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Music */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-purple-500/25">
              <h3 className="text-sm font-semibold mb-3 text-slate-200 flex items-center gap-2"><Music size={14} className="text-pink-400" />Background Music</h3>
              {selectedMusic ? (
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-green-400 flex items-center gap-1"><Check size={11} />{selectedMusic.name || 'Music'}</span>
                    <button onClick={() => setSelectedMusic(null)} className="text-red-400 hover:text-red-300 text-xs">Remove</button>
                  </div>
                  <div className="flex items-center gap-2">
                    <Volume2 size={12} className="text-slate-400 flex-shrink-0" />
                    <input type="range" min="0" max="100" value={musicVolume} onChange={e => setMusicVolume(parseInt(e.target.value))} className="flex-1 accent-green-500" />
                    <span className="text-xs text-slate-400 w-8 text-right">{musicVolume}%</span>
                  </div>
                </div>
              ) : (
                <label className="w-full bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 px-3 py-2.5 rounded-lg flex items-center justify-center gap-2 cursor-pointer text-sm font-semibold transition-all">
                  <input type="file" accept=".mp3,.wav,.m4a,.ogg" onChange={e => uploadMusic(e.target.files[0])} className="hidden" /><Upload size={14} />Upload Music
                </label>
              )}
            </div>

            {/* Visual settings */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-purple-500/25">
              <h3 className="text-sm font-semibold mb-3 text-slate-200">🎨 Visual Settings</h3>
              <div className="space-y-3">
                {/* Avatar */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">🎭 Avatar Narrator</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" checked={useAvatar} onChange={e => {
                      const on = e.target.checked;
                      setUseAvatar(on);
                      const v = on ? (avatarStyle === 'female' ? resolvedJessica : resolvedWill) : VOICE_GTTS;
                      setScenes(prev => prev.map(s => ({ ...s, voice_id: v })));
                    }} className="sr-only peer" />
                    <div className="w-11 h-6 bg-slate-600 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-500"></div>
                  </label>
                </div>
                {useAvatar && (
                  <div className="pl-3 border-l-2 border-purple-500/40 space-y-2 pt-1">
                    <div className="grid grid-cols-2 gap-2">
                      <button onClick={() => changeAvatarStyle('male')} className={`py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-all ${avatarStyle === 'male' ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}>Will</button>
                      <button onClick={() => changeAvatarStyle('female')} className={`py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-all ${avatarStyle === 'female' ? 'bg-pink-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}>Jessica</button>
                    </div>
                    <select value={avatarPosition} onChange={e => setAvatarPosition(e.target.value)} className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-xs focus:outline-none">
                      <option value="bottom-right">📍 Bottom Right</option><option value="bottom-left">📍 Bottom Left</option><option value="top-right">📍 Top Right</option><option value="top-left">📍 Top Left</option>
                    </select>
                    <select value={avatarSize} onChange={e => setAvatarSize(e.target.value)} className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-xs focus:outline-none">
                      <option value="small">Small</option><option value="medium">Medium</option><option value="large">Large</option>
                    </select>
                  </div>
                )}

                {/* Subtitles */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">Subtitles</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" checked={subtitles} onChange={e => setSubtitles(e.target.checked)} className="sr-only peer" />
                    <div className="w-11 h-6 bg-slate-600 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-500"></div>
                  </label>
                </div>
                {subtitles && (
                  <div className="pl-3 border-l-2 border-blue-500/40 space-y-2 pt-1">
                    <select value={subtitleStyle} onChange={e => setSubtitleStyle(e.target.value)} className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-xs focus:outline-none">
                      <option value="bottom">Bottom</option><option value="top">Top</option><option value="center">Center</option>
                    </select>
                    <div>
                      <div className="flex justify-between text-xs text-slate-400 mb-1"><span>Font Size</span><span className="font-semibold text-white">{fontSize}px</span></div>
                      <input type="range" min="8" max="64" step="2" value={fontSize} onChange={e => setFontSize(parseInt(e.target.value))} className="w-full accent-blue-500" />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── CENTER ── */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 min-w-0 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-purple-500/30 [&::-webkit-scrollbar-thumb]:rounded-full">

          {/* Script area */}
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-5 border border-purple-500/30">
            <h3 className="text-base font-semibold mb-3 text-slate-200">📝 Script</h3>
            <textarea value={text} onChange={e => setText(e.target.value)} rows={6}
              className="w-full bg-slate-700/50 border border-slate-600 rounded-xl p-4 resize-none focus:border-purple-500 focus:outline-none transition-colors text-sm leading-relaxed"
              placeholder="Paste or type your script here. Each sentence ending with a period becomes one scene." />
            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-slate-400">💡 One sentence per scene (split on <span className="font-mono bg-slate-700 px-1 rounded">.</span>)</span>
              <button onClick={split} disabled={splitting} className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 px-5 py-2 rounded-lg text-sm font-semibold transition-all">{splitting ? "✂️ Splitting..." : "✂️ Split into Scenes"}</button>
            </div>
          </div>

          {/* Scenes */}
          {scenes.length > 0 && (
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-5 border border-purple-500/30">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold text-slate-200">🎬 Scenes ({scenes.length})</h3>
                <div className="flex items-center gap-2">
                  <button onClick={() => setShowBulk(true)} className="bg-blue-500/20 hover:bg-blue-500/30 p-2 rounded-lg transition-all"><Settings size={15} /></button>
                  <button onClick={add} className="bg-purple-500/20 hover:bg-purple-500/30 p-2 rounded-lg transition-all"><Plus size={15} /></button>

                  {/* ── Static/Dynamic toggle ── */}
                  <div className="flex items-center rounded-xl overflow-hidden border border-slate-600/60 bg-slate-700/50">
                    <button
                      onClick={() => setGenerateMode('static')}
                      className={`px-3 py-2 text-xs font-semibold transition-all flex items-center gap-1 ${
                        generateMode === 'static'
                          ? 'bg-blue-500 text-white shadow-inner'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-600/50'
                      }`}
                    >
                      🖼️ Static
                    </button>
                    <button
                      onClick={() => setGenerateMode('dynamic')}
                      className={`px-3 py-2 text-xs font-semibold transition-all flex items-center gap-1 ${
                        generateMode === 'dynamic'
                          ? 'bg-purple-500 text-white shadow-inner'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-600/50'
                      }`}
                    >
                      🎬 Dynamic
                    </button>
                  </div>

                  {/* ── Generate All button (separate) ── */}
                  <button
                    onClick={genImages}
                    disabled={loading}
                    className={`px-4 py-2 text-sm font-semibold rounded-xl transition-all disabled:opacity-50 ${
                      generateMode === 'dynamic'
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white'
                        : 'bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600 text-white'
                    }`}
                  >
                    {loading ? '⏳' : generateMode === 'dynamic' ? '🎬 Get Videos' : '🎨 Gen Images'}
                  </button>
                </div>
              </div>
              <div className="space-y-3">
                {scenes.map((s, i) => (
                  <div key={s.id} draggable onDragStart={e => handleDragStart(e, i)} onDragOver={e => handleDragOver(e, i)} onDragEnd={handleDragEnd}
                    className={`rounded-xl border transition-all select-none ${draggedIdx === i ? 'bg-purple-500/20 border-purple-400 ring-2 ring-purple-400/50 scale-[1.01] shadow-lg shadow-purple-500/20' : 'bg-slate-700/40 border-slate-600/50 hover:border-purple-500/50'}`}>
                    <div className="flex items-center gap-2 px-4 pt-3 pb-2 border-b border-slate-600/30 cursor-grab active:cursor-grabbing">
                      <GripVertical size={16} className="text-slate-400 flex-shrink-0" />
                      <span className="text-sm font-semibold text-slate-200 flex-1">Scene {i + 1}</span>
                      <div className="flex gap-1">
                        <button onClick={() => dup(i)} className="text-blue-400 hover:text-blue-300 p-1 transition-colors"><Copy size={13} /></button>
                        <button onClick={() => del(i)} className="text-red-400 hover:text-red-300 p-1 transition-colors"><Trash2 size={13} /></button>
                      </div>
                    </div>
                    <div className="p-4 space-y-2.5">
                      <textarea value={s.text} onChange={e => update(i, 'text', e.target.value)} className="w-full bg-slate-600/30 border border-slate-500/60 rounded-lg p-2.5 text-sm focus:border-purple-500 focus:outline-none transition-colors leading-relaxed" rows="2" placeholder="Scene text..." />
                      <textarea value={s.image_prompt || ''} onChange={e => update(i, 'image_prompt', e.target.value)} className="w-full bg-slate-600/20 border border-purple-500/25 rounded-lg p-2.5 text-sm focus:border-purple-500 focus:outline-none transition-colors" rows="1" placeholder="Custom image prompt (optional)..." />
                      <div className="grid grid-cols-2 gap-2.5">
                        <input type="number" value={s.duration} onChange={e => { const v = e.target.value; update(i, 'duration', v === '' ? '' : parseFloat(v) || 0); }} className="bg-slate-600/30 border border-slate-500/60 rounded-lg px-3 py-1.5 text-sm focus:border-purple-500 focus:outline-none" min="1" step="0.5" placeholder="Duration (s)" />
                        <select value={s.voice_id || (useAvatar && avatarStyle === 'female' ? resolvedJessica : VOICE_GTTS)} onChange={e => update(i, 'voice_id', e.target.value)} className="bg-slate-600/30 border border-slate-500/60 rounded-lg px-3 py-1.5 text-sm focus:border-purple-500 focus:outline-none">
                          {renderVoiceOptions()}
                        </select>
                      </div>
                      <div className="flex items-center gap-2">
                        <input type="file" onChange={e => upload(i, e.target.files[0])} accept="image/*,video/*" className="hidden" id={`file-${i}`} />
                        <label htmlFor={`file-${i}`} className="flex items-center gap-1.5 bg-slate-600/30 hover:bg-slate-600/60 px-3 py-1.5 rounded-lg text-xs cursor-pointer transition-all"><Upload size={11} />Upload</label>
                        <button onClick={() => { setSelectedForStock(i); setShowStock(true); }} className="flex items-center gap-1.5 bg-blue-500/20 hover:bg-blue-500/30 px-3 py-1.5 rounded-lg text-xs transition-all"><Image size={11} />Stock</button>
                        <button onClick={() => retry(i)} disabled={retrying.has(i)} className="flex items-center gap-1.5 bg-orange-500/20 hover:bg-orange-500/30 px-3 py-1.5 rounded-lg text-xs disabled:opacity-50 transition-all"><RefreshCw size={11} className={retrying.has(i) ? 'animate-spin' : ''} />AI</button>
                      </div>
                      {s.background_path && (
                        <div className="flex items-center justify-between bg-green-500/10 px-3 py-2 rounded-lg border border-green-500/30">
                          <span className="text-xs text-green-400 flex items-center gap-1.5"><Check size={11} />Background ready</span>
                          <button onClick={() => window.open(s.preview_url || `${API}${s.background_path}`, '_blank')} className="text-xs text-green-300 bg-green-500/20 hover:bg-green-500/30 px-2.5 py-1 rounded-lg transition-all">Preview</button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT SIDEBAR ── */}
        <div className="w-80 flex-shrink-0 border-l border-purple-500/20 bg-black/15 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-purple-500/20 [&::-webkit-scrollbar-thumb]:rounded-full">

            {/* Render */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-purple-500/25">
              <h3 className="text-sm font-semibold mb-3 text-slate-200">🎬 Render Video</h3>
              {estimatedTime > 0 && !rendering && (
                <div className="mb-3 text-xs bg-blue-500/10 border border-blue-500/25 p-2.5 rounded-lg text-blue-300">⏱️ Est. ~{fmt(estimatedTime)} · {scenes.length} scene{scenes.length !== 1 ? 's' : ''}</div>
              )}
              <button onClick={render} disabled={rendering || !scenes.length} className="w-full bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 disabled:opacity-40 py-3 rounded-xl font-semibold text-sm transition-all shadow-lg shadow-green-900/30">
                {rendering ? '⏳ Rendering...' : !scenes.length ? 'Add scenes first' : '▶️ Render Video'}
              </button>
              {rendering && (
                <div className="mt-4 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-300">{stage}</span>
                    <span className="text-sm font-bold text-white">{progress}%</span>
                  </div>
                  <div className="w-full bg-slate-600/60 rounded-full h-3 overflow-hidden">
                    <div className={`bg-gradient-to-r ${progressColor()} h-3 rounded-full transition-all duration-300 ease-out relative`} style={{ width: `${progress}%` }}>
                      <div className="absolute inset-0 bg-white/20 animate-pulse rounded-full" />
                    </div>
                  </div>
                  <div className="flex justify-between pt-1">
                    {['Audio','Lip','Mask','Mix','Encode','Done'].map((label, idx) => {
                      const thresholds = [12, 40, 52, 60, 88, 100];
                      const done   = progress >= thresholds[idx];
                      const active = progress >= (thresholds[idx-1] || 0) && progress < thresholds[idx];
                      return (
                        <div key={label} className="flex flex-col items-center gap-1">
                          <div className={`w-2 h-2 rounded-full transition-all duration-300 ${done ? 'bg-green-400' : active ? 'bg-red-400 animate-pulse' : 'bg-slate-600'}`} />
                          <span className={`text-[9px] ${done ? 'text-green-400' : active ? 'text-red-400' : 'text-slate-500'}`}>{label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {videoUrl && !rendering && (
                <div className="mt-4 space-y-2.5">
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-2.5 text-center text-green-400 text-sm font-semibold">✅ Video ready!</div>
                  <div className="flex gap-2">
                    <button onClick={download} className="flex-1 bg-green-500 hover:bg-green-600 px-3 py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all"><Download size={14} />Download</button>
                    <button onClick={() => window.open(videoUrl.preview, '_blank')} className="flex-1 bg-blue-500 hover:bg-blue-600 px-3 py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all"><Play size={14} />Preview</button>
                  </div>
                </div>
              )}
            </div>

            {status && (
              <div className={`p-3 rounded-xl text-sm ${status.includes('✅') ? 'bg-green-500/10 text-green-400 border border-green-500/30' : status.includes('❌') ? 'bg-red-500/10 text-red-400 border border-red-500/30' : 'bg-blue-500/10 text-blue-300 border border-blue-500/30'}`}>{status}</div>
            )}

            {scenes.length > 0 && (
              <div className="bg-slate-800/50 rounded-xl p-4 border border-purple-500/25">
                <h3 className="text-sm font-semibold mb-3 text-slate-200">📈 Project Stats</h3>
                <div className="space-y-2">
                  {[
                    { label: 'Scenes',   val: scenes.length,                   color: 'text-purple-400' },
                    { label: 'Duration', val: fmt(Math.floor(totalDur)),        color: 'text-blue-400'   },
                    { label: 'Words',    val: totalWords,                       color: 'text-green-400'  },
                    { label: 'Images',   val: `${withImages}/${scenes.length}`, color: 'text-pink-400'   },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="flex justify-between items-center">
                      <span className="text-sm text-slate-400">{label}</span>
                      <span className={`text-sm font-semibold ${color}`}>{val}</span>
                    </div>
                  ))}
                  {selectedMusic && <div className="flex justify-between items-center"><span className="text-sm text-slate-400">Music</span><span className="text-sm font-semibold text-yellow-400">✓ Added</span></div>}
                  {useAvatar && <div className="flex justify-between items-center"><span className="text-sm text-slate-400">Voice</span><span className={`text-sm font-semibold ${avatarStyle === 'female' ? 'text-pink-400' : 'text-blue-400'}`}>{avatarStyle === 'female' ? 'Jessica' : 'Will'}</span></div>}
                </div>
              </div>
            )}

            {!scenes.length && !loading && (
              <div className="flex flex-col items-center justify-center py-16 text-slate-500 text-center">
                <Play size={44} className="mb-3 opacity-15" />
                <p className="text-sm font-medium">No scenes yet</p>
                <p className="text-xs mt-1 text-slate-600">Write a script or use ⚡ One-Click Generate</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ══ ONE-CLICK PIPELINE MODAL ══ */}
      {showPipeline && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl border border-purple-500/30 shadow-2xl w-full max-w-lg overflow-hidden">

            {/* Header */}
            <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border-b border-slate-700/50 px-6 py-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center text-white text-lg shadow-lg select-none">▶</div>
                  <div>
                    <h2 className="text-base font-bold text-slate-100 tracking-tight">One-Click Generate</h2>
                    <p className="text-xs text-slate-400">Type a topic — AI handles everything</p>
                  </div>
                </div>
                <button onClick={() => setShowPipeline(false)}
                  className="text-slate-400 hover:text-slate-200 hover:bg-slate-700 w-8 h-8 rounded-lg flex items-center justify-center transition-all text-lg">×</button>
              </div>
            </div>

            {/* Body */}
            <div className="p-6 flex flex-col gap-5">

              {/* Topic */}
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-widest block mb-2">Topic *</label>
                <input value={pipelineTopic} onChange={e => setPipelineTopic(e.target.value)}
                  placeholder="e.g. The Future of Electric Vehicles"
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-purple-500/60 transition-colors" />
              </div>

              {/* Mode toggle */}
              <div className="flex bg-slate-700/40 rounded-xl p-1">
                {[{val:'static',label:'🖼️ Static'},{val:'dynamic',label:'🎬 Dynamic'}].map(opt => (
                  <button key={opt.val} onClick={() => setPipelineMode(opt.val)}
                    className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${
                      pipelineMode===opt.val
                        ? (opt.val==='dynamic' ? 'bg-purple-500 text-white shadow' : 'bg-blue-500 text-white shadow')
                        : 'text-slate-400 hover:text-slate-200'
                    }`}>{opt.label}</button>
                ))}
              </div>

              {/* 3-col options */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label:'AVATAR & VOICE', key:'avatar', opts:[
                    {v:'disabled',l:'No Avatar'},{v:'male',l:'Will (Male)'},{v:'female',l:'Jessica (Female)'}]},
                  { label:'STYLE', key:'style', opts:[
                    {v:'educational',l:'Educational'},{v:'narrative',l:'Narrative'},
                    {v:'promotional',l:'Promotional'},{v:'documentary',l:'Documentary'},{v:'tutorial',l:'Tutorial'}]},
                  { label:'DURATION', key:'duration', opts:[
                    {v:'15',l:'15s'},{v:'30',l:'30s'},{v:'45',l:'45s'},{v:'60',l:'60s'}]},
                ].map(({label,key,opts}) => (
                  <div key={key}>
                    <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">{label}</label>
                    <select
                      value={key==='avatar'?(pipelineAvatar||'disabled'):key==='style'?(pipelineStyle||'educational'):(pipelineDuration?.toString()||'60')}
                      onChange={e => key==='avatar'?setPipelineAvatar(e.target.value):key==='style'?setPipelineStyle(e.target.value):setPipelineDuration(Number(e.target.value))}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2.5 py-2 text-xs text-slate-200 outline-none focus:border-purple-500/60 cursor-pointer">
                      {opts.map(o=><option key={o.v} value={o.v}>{o.l}</option>)}
                    </select>
                  </div>
                ))}
              </div>

              {/* Error */}
              {pipelineError && !pipelineDone && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-red-300">⚠️ {pipelineError}</div>
              )}

              {/* Steps */}
              {pipelineSteps.length > 0 && (
                <div className="flex flex-col gap-2">
                  {pipelineSteps.map((step, si) => {
                    const st = step.status;
                    return (
                      <div key={si} className={`rounded-xl px-4 py-3 flex items-center gap-3 border transition-all ${
                        st==='done' ? 'bg-emerald-500/10 border-emerald-500/25' :
                        st==='running' ? 'bg-purple-500/10 border-purple-500/35' :
                        st==='error' ? 'bg-red-500/10 border-red-500/25' :
                        'bg-slate-700/30 border-slate-600/30'
                      }`}>
                        <span className="text-lg min-w-[24px] text-center">
                          {st==='done'?'✅':st==='running'?
                            <span className="inline-flex gap-0.5">
                              {[0,1,2].map(j=><span key={j} className="w-1.5 h-1.5 bg-purple-400 rounded-full inline-block" style={{animation:`bounce 0.6s ease-in-out ${j*0.15}s infinite alternate`}}/>)}
                            </span>
                          :st==='error'?'❌':<span className="opacity-30">{step.icon}</span>}
                        </span>
                        <div className="flex-1">
                          <p className={`text-sm font-semibold ${
                            st==='done'?'text-emerald-400':st==='running'?'text-purple-300':st==='error'?'text-red-400':'text-slate-500'
                          }`}>{step.label}</p>
                          {step.detail && <p className="text-xs text-slate-500 mt-0.5">{step.detail}</p>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Progress */}
              {pipelineRunning && (
                <div className="bg-slate-700/30 rounded-xl px-4 py-3 border border-slate-600/30">
                  <div className="flex justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400">Progress</span>
                    <span className="text-xs text-purple-400">{stage}</span>
                  </div>
                  <div className="h-1.5 bg-slate-600/50 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-400"
                         style={{width:`${Math.round((pipelineSteps.filter(s=>s.status==='done').length/Math.max(pipelineSteps.length,1))*100)}%`}} />
                  </div>
                </div>
              )}

              {/* Done error */}
              {pipelineDone && pipelineError && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-red-300">❌ {pipelineError}</div>
              )}

              {/* Action buttons */}
              <div className="flex gap-3">
                {!pipelineRunning && !pipelineDone && (
                  <>
                    <button onClick={runFullPipeline} disabled={!pipelineTopic.trim()}
                      className="flex-1 bg-gradient-to-r from-red-500 to-red-700 hover:from-red-600 hover:to-red-800 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold py-3 rounded-xl text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-red-500/20">
                      🚀 Generate & Render
                    </button>
                    <button onClick={() => setShowPipeline(false)}
                      className="bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white font-medium py-3 px-5 rounded-xl text-sm transition-all">
                      Cancel
                    </button>
                  </>
                )}
                {pipelineRunning && (
                  <div className="flex-1 bg-slate-700/40 border border-slate-600/30 rounded-xl py-3 text-sm text-center text-slate-400 font-medium">
                    ⚙️ Pipeline running — please wait...
                  </div>
                )}
                {pipelineDone && (
                  <div className="flex gap-2 w-full">
                    <button onClick={download}
                      className="flex-1 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white font-bold py-3 rounded-xl text-sm flex items-center justify-center gap-2 transition-all">
                      <Download size={14} />Download
                    </button>
                    <button onClick={() => window.open(videoUrl?.preview, '_blank')}
                      className="flex-1 bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600 text-white font-bold py-3 rounded-xl text-sm flex items-center justify-center gap-2 transition-all">
                      <Play size={14} />Preview
                    </button>
                    <button onClick={() => { setShowPipeline(false); setPipelineSteps([]); setPipelineDone(false); setPipelineTopic(''); }}
                      className="bg-slate-700 hover:bg-slate-600 text-slate-300 py-3 px-4 rounded-xl text-sm transition-all">
                      Close
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          <style>{`
            @keyframes bounce { from { transform: translateY(0); } to { transform: translateY(-4px); } }
          `}</style>
        </div>
      )}

      {/* ── BULK EDIT MODAL ── */}
      {showBulk && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl p-6 max-w-md w-full border border-purple-500/30 shadow-2xl">
            <h3 className="text-lg font-semibold mb-4">⚙️ Bulk Edit Scenes</h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-slate-400 block mb-2">Duration (seconds)</label>
                <input type="number" value={bulkDur} onChange={e => setBulkDur(parseFloat(e.target.value) || 5)} className="w-full bg-slate-700/50 border border-slate-600 rounded-xl px-4 py-2.5 focus:border-purple-500 focus:outline-none" min="1" step="0.5" />
              </div>
              <div>
                <label className="text-sm text-slate-400 block mb-2">Voice (all scenes)</label>
                <select value={bulkVoice} onChange={e => setBulkVoice(e.target.value)} className="w-full bg-slate-700/50 border border-slate-600 rounded-xl px-4 py-2.5 focus:border-purple-500 focus:outline-none">
                  <option value="">Keep individual voices</option>
                  {renderVoiceOptions()}
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={bulk} className="flex-1 bg-gradient-to-r from-green-500 to-emerald-500 py-2.5 rounded-xl font-semibold transition-all">Apply to All</button>
              <button onClick={() => setShowBulk(false)} className="flex-1 bg-slate-600 hover:bg-slate-500 py-2.5 rounded-xl transition-all">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* ── STOCK MODAL ── */}
      {showStock && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl p-6 max-w-4xl w-full max-h-[85vh] overflow-y-auto border border-purple-500/30 shadow-2xl">
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-xl font-semibold flex items-center gap-2"><Image size={22} className="text-blue-400" />Stock Media</h3>
              <button onClick={() => setShowStock(false)} className="text-slate-400 hover:text-white p-1 transition-colors"><X size={22} /></button>
            </div>
            <div className="flex gap-2 mb-4">
              <button onClick={() => setStockMediaType('image')} className={`flex-1 py-2 px-4 rounded-xl font-semibold text-sm transition-all ${stockMediaType === 'image' ? 'bg-blue-500 text-white' : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'}`}>📸 Images</button>
              <button onClick={() => setStockMediaType('video')} className={`flex-1 py-2 px-4 rounded-xl font-semibold text-sm transition-all ${stockMediaType === 'video' ? 'bg-purple-500 text-white' : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'}`}>🎬 Videos</button>
            </div>
            <div className="flex gap-2 mb-5">
              <input type="text" value={stockQuery} onChange={e => setStockQuery(e.target.value)} onKeyPress={e => e.key === 'Enter' && searchStock(stockQuery)} className="flex-1 bg-slate-700/50 border border-slate-600 rounded-xl px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none" placeholder={`Search ${stockMediaType}s...`} />
              <button onClick={() => searchStock(stockQuery)} disabled={loadingStock} className="bg-gradient-to-r from-blue-500 to-purple-500 disabled:opacity-50 px-5 py-2.5 rounded-xl font-semibold text-sm">{loadingStock ? '⏳' : '🔍'}</button>
            </div>
            {loadingStock ? (
              <div className="text-center py-16"><div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div></div>
            ) : stockResults.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {stockResults.map((m, i) => (
                  <div key={i} className="relative group cursor-pointer border border-slate-600 rounded-xl overflow-hidden hover:border-purple-400 transition-all" onClick={() => applyStock(m)}>
                    <img src={m.thumbnail} alt={m.alt} className="w-full h-36 object-cover" />
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity"><span className="text-white text-sm font-semibold">Apply</span></div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-16 text-slate-500"><Image size={56} className="mx-auto mb-4 opacity-20" /><p>Search for stock media above</p></div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
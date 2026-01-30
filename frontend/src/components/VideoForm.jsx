import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Download, Play, Settings, Image, FileText, X, Upload, GripVertical, Copy, RefreshCw, Save, FolderOpen, Music, Volume2, Check } from 'lucide-react';

export default function VideoCreator() {
  const API = import.meta.env.VITE_API_URL || 'http://localhost:5001';
  
  const [project, setProject] = useState('my_video');
  const [text, setText] = useState('');
  const [scenes, setScenes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [videoUrl, setVideoUrl] = useState(null);
  const [status, setStatus] = useState('');
  const [subtitles, setSubtitles] = useState(true);
  const [subtitleStyle, setSubtitleStyle] = useState('bottom');
  const [fontSize, setFontSize] = useState(24);
  const [useElevenLabs, setUseElevenLabs] = useState(false);
  const [voices, setVoices] = useState([]);
  const [voicesLoading, setVoicesLoading] = useState(false);
  const [voicesLoaded, setVoicesLoaded] = useState(false);
  const [autoAI, setAutoAI] = useState(true);
  const [showScript, setShowScript] = useState(false);
  const [scriptTopic, setScriptTopic] = useState('');
  const [scriptStyle, setScriptStyle] = useState('educational');
  const [scriptDuration, setScriptDuration] = useState(60);
  const [genScript, setGenScript] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('');
  const [rendering, setRendering] = useState(false);
  const [estimatedTime, setEstimatedTime] = useState(0);
  const [draggedIdx, setDraggedIdx] = useState(null);
  const [showBulk, setShowBulk] = useState(false);
  const [bulkDur, setBulkDur] = useState(5);
  const [bulkVoice, setBulkVoice] = useState('');
  const [retrying, setRetrying] = useState(new Set());
  const [showStock, setShowStock] = useState(false);
  const [stockQuery, setStockQuery] = useState('');
  const [stockResults, setStockResults] = useState([]);
  const [loadingStock, setLoadingStock] = useState(false);
  const [selectedForStock, setSelectedForStock] = useState(null);
  const [selectedMusic, setSelectedMusic] = useState(null);
  const [musicVolume, setMusicVolume] = useState(10);

  const totalDur = scenes.reduce((sum, s) => sum + (parseFloat(s.duration) || 0), 0);
  const totalWords = scenes.reduce((sum, s) => sum + (s.text?.split(' ').length || 0), 0);
  const withImages = scenes.filter(s => s.background_path).length;

  useEffect(() => {
    if (scenes.length === 0) {
      setEstimatedTime(0);
      return;
    }
    const est = Math.max(0, 5 + (scenes.length * 15));
    setEstimatedTime(est);
  }, [scenes.length]);

  const loadVoices = async () => {
    if (voicesLoading || voicesLoaded) return;
    
    setVoicesLoading(true);
    try {
      const res = await fetch(`${API}/api/voices`);
      const data = await res.json();
      setVoices(data.voices || []);
      setVoicesLoaded(true);
    } catch (err) {
      console.error('Voice load failed:', err);
    } finally {
      setVoicesLoading(false);
    }
  };

  const toggleElevenLabs = (enabled) => {
    setUseElevenLabs(enabled);
    if (enabled && !voicesLoaded && !voicesLoading) {
      loadVoices();
    }
  };

  const genScriptFn = async () => {
    if (!scriptTopic.trim()) {
      setStatus('❌ Enter a topic');
      return;
    }
    setGenScript(true);
    setStatus('🤖 Generating script...');
    try {
      const res = await fetch(`${API}/api/generate_script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: scriptTopic, style: scriptStyle, duration: scriptDuration })
      });
      const data = await res.json();
      if (data.success) {
        setText(data.script);
        setStatus(`✅ Generated! (${data.script.split(' ').length} words)`);
        setShowScript(false);
      } else {
        setStatus(`❌ Failed: ${data.error || 'Unknown'}`);
      }
    } catch (err) {
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      setGenScript(false);
    }
  };

  const split = async () => {
    if (!text.trim()) {
      setStatus('❌ Enter text first');
      return;
    }
    setLoading(true);
    setStatus('✂️ Splitting by sentences...');
    try {
      const res = await fetch(`${API}/api/split`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (data.scenes) {
        setScenes(data.scenes.map(s => ({ ...s, image_prompt: s.image_prompt || '' })));
        setStatus(`✅ Split into ${data.scenes.length} scenes`);
      } else {
        setStatus(`❌ Failed: ${data.error || 'Unknown'}`);
      }
    } catch (err) {
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const update = (idx, field, val) => {
    const upd = [...scenes];
    upd[idx][field] = val;
    setScenes(upd);
  };

  const del = (idx) => {
    setScenes(scenes.filter((_, i) => i !== idx));
    setStatus(`🗑️ Scene ${idx + 1} deleted`);
  };

  const add = () => {
    setScenes([...scenes, {
      id: `scene_${scenes.length + 1}`,
      text: 'Enter text...',
      background_path: '',
      duration: 5,
      voice_id: '',
      image_prompt: ''
    }]);
  };

  const dup = (idx) => {
    const s = { ...scenes[idx], id: `scene_${scenes.length + 1}` };
    const upd = [...scenes];
    upd.splice(idx + 1, 0, s);
    setScenes(upd);
    setStatus(`📋 Scene ${idx + 1} duplicated`);
  };

  const dragStart = (idx) => setDraggedIdx(idx);

  const dragOver = (e, idx) => {
    e.preventDefault();
    if (draggedIdx === null || draggedIdx === idx) return;
    const upd = [...scenes];
    const dragged = upd[draggedIdx];
    upd.splice(draggedIdx, 1);
    upd.splice(idx, 0, dragged);
    setDraggedIdx(idx);
    setScenes(upd);
  };

  const dragEnd = () => setDraggedIdx(null);

  const bulk = () => {
    setScenes(scenes.map(s => ({ ...s, duration: bulkDur, voice_id: bulkVoice })));
    setShowBulk(false);
    setStatus(`✅ Applied to ${scenes.length} scenes`);
  };

  const upload = async (idx, file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('scene_id', scenes[idx].id);
    try {
      setStatus('📤 Uploading...');
      const res = await fetch(`${API}/api/upload_background`, { method: 'POST', body: fd });
      const data = await res.json();
      if (data.background_path) {
        update(idx, 'background_path', data.background_path);
        setStatus('✅ Uploaded!');
      }
    } catch (err) {
      setStatus(`❌ Failed: ${err.message}`);
    }
  };

  const searchStock = async (q) => {
    if (!q.trim()) return;
    setLoadingStock(true);
    setStatus('🔍 Searching stock...');
    try {
      const res = await fetch(`${API}/api/stock_search?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      setStockResults(data.results || []);
      setStatus(data.results?.length > 0 ? `✅ Found ${data.results.length} results` : '❌ No results');
    } catch (err) {
      setStatus(`❌ Search failed: ${err.message}`);
      setStockResults([]);
    } finally {
      setLoadingStock(false);
    }
  };

  const applyStock = async (media) => {
    if (selectedForStock === null) return;
    try {
      setStatus('📥 Downloading...');
      const res = await fetch(`${API}/api/download_stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: media.url, scene_id: scenes[selectedForStock].id, type: media.type })
      });
      const data = await res.json();
      if (data.path) {
        update(selectedForStock, 'background_path', data.path);
        setStatus('✅ Applied!');
        setShowStock(false);
      }
    } catch (err) {
      setStatus(`❌ Failed: ${err.message}`);
    }
  };

  const retry = async (idx) => {
    const s = scenes[idx];
    setRetrying(prev => new Set(prev).add(idx));
    setStatus(`🔄 Retrying scene ${idx + 1}...`);
    try {
      const res = await fetch(`${API}/api/generate_images`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenes: [s] })
      });
      const data = await res.json();
      if (data.images && data.images[0].success) {
        update(idx, 'background_path', data.images[0].background_path);
        setStatus('✅ Generated!');
      } else {
        setStatus(`❌ Failed: ${data.images[0].error || 'Unknown'}`);
      }
    } catch (err) {
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      setRetrying(prev => {
        const n = new Set(prev);
        n.delete(idx);
        return n;
      });
    }
  };

  const genImages = async () => {
    if (scenes.length === 0) return;
    setLoading(true);
    setStatus('🎨 Generating images...');
    try {
      const res = await fetch(`${API}/api/generate_images`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenes })
      });
      const data = await res.json();
      if (data.images) {
        const upd = [...scenes];
        let cnt = 0;
        data.images.forEach(img => {
          const i = upd.findIndex(s => s.id === img.id);
          if (i >= 0 && img.success) {
            upd[i].background_path = img.background_path;
            cnt++;
          }
        });
        setScenes(upd);
        setStatus(`✅ Generated ${cnt}/${data.images.length}`);
      }
    } catch (err) {
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const uploadMusic = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      setStatus('📤 Uploading music...');
      const res = await fetch(`${API}/api/music/upload`, { method: 'POST', body: fd });
      const data = await res.json();
      if (data.success) {
        setSelectedMusic({ 
          name: file.name, 
          local_path: data.path, 
          custom: true 
        });
        setStatus('✅ Music uploaded!');
      } else {
        setStatus(`❌ Failed: ${data.error || 'Unknown'}`);
      }
    } catch (err) {
      setStatus(`❌ Upload failed: ${err.message}`);
    }
  };

  const render = async () => {
    if (scenes.length === 0) {
      setStatus('❌ Add scenes first');
      return;
    }
    setLoading(true);
    setRendering(true);
    setProgress(0);
    setStage('Initializing...');
    setStatus('🎬 Rendering...');
    
    const stgs = [
      { progress: 10, stage: 'Processing scenes...' },
      { progress: 25, stage: 'Generating audio...' },
      { progress: 40, stage: 'Processing images...' },
      { progress: 60, stage: 'Compositing video...' },
      { progress: 80, stage: 'Encoding video...' },
      { progress: 95, stage: 'Finalizing...' }
    ];
    
    let i = 0;
    const iv = setInterval(() => {
      if (i < stgs.length) {
        setProgress(stgs[i].progress);
        setStage(stgs[i].stage);
        i++;
      }
    }, 3000);
    
    try {
      const res = await fetch(`${API}/api/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: project,
          scenes,
          auto_ai_images: autoAI,
          subtitles,
          subtitle_style: subtitleStyle,
          font_size: fontSize,
          use_elevenlabs: useElevenLabs,
          background_music: selectedMusic?.local_path || null,
          music_volume: musicVolume / 100
        })
      });
      
      const data = await res.json();
      clearInterval(iv);
      setProgress(100);
      setStage('Complete!');
      
      if (data.video_path) {
        const fn = data.video_path.split('\\').pop().split('/').pop();
        setVideoUrl({
          download: data.download_url,
          preview: `${API}/api/video/${fn}`,
          filename: fn
        });
        setStatus('✅ Video ready!');
        setRendering(false);
      } else {
        setStatus(`❌ Failed: ${data.error || 'Unknown'}`);
        setProgress(0);
        setStage('');
        setRendering(false);
      }
    } catch (err) {
      clearInterval(iv);
      setProgress(0);
      setStage('');
      setStatus(`❌ Error: ${err.message}`);
      setRendering(false);
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!videoUrl?.filename) return;
    try {
      const a = document.createElement('a');
      a.href = `${API}/api/video/${videoUrl.filename}?download=true`;
      a.download = `${project}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setStatus('📥 Download started!');
    } catch (err) {
      setStatus(`❌ Failed: ${err.message}`);
    }
  };

  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const save = () => {
    const d = {
      version: '1.0',
      project_name: project,
      settings: { subtitles, subtitleStyle, fontSize, useElevenLabs, autoAI, musicVolume },
      script: text,
      scenes,
      music: selectedMusic
    };
    const b = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
    const u = URL.createObjectURL(b);
    const l = document.createElement('a');
    l.href = u;
    l.download = `${project}_project.json`;
    document.body.appendChild(l);
    l.click();
    document.body.removeChild(l);
    URL.revokeObjectURL(u);
    setStatus('💾 Saved!');
  };

  const load = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = (ev) => {
      try {
        const d = JSON.parse(ev.target.result);
        setProject(d.project_name || 'my_video');
        setSubtitles(d.settings?.subtitles ?? true);
        setSubtitleStyle(d.settings?.subtitleStyle || 'bottom');
        setFontSize(d.settings?.fontSize || 24);
        setUseElevenLabs(d.settings?.useElevenLabs || false);
        setAutoAI(d.settings?.autoAI ?? true);
        setMusicVolume(d.settings?.musicVolume || 10);
        setText(d.script || '');
        setScenes(d.scenes || []);
        setSelectedMusic(d.music || null);
        setStatus('📂 Loaded!');
      } catch (err) {
        setStatus(`❌ Load failed: ${err.message}`);
      }
    };
    r.readAsText(f);
    e.target.value = '';
  };

  const openStockModal = (idx) => {
    setSelectedForStock(idx);
    setShowStock(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
      <div className="bg-black/20 backdrop-blur-sm border-b border-purple-500/30">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                AI Text-to-Video Studio
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <input
                value={project}
                onChange={(e) => setProject(e.target.value)}
                className="bg-slate-800/50 border border-purple-500/30 rounded-lg px-3 py-2 text-sm"
                placeholder="Project name"
              />
              <div className="flex space-x-2">
                <button
                  onClick={save}
                  disabled={scenes.length === 0}
                  className="bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 disabled:opacity-50 px-4 py-2 rounded-lg flex items-center space-x-2 transition-all"
                >
                  <Save size={16} />
                  <span>Save</span>
                </button>
                <label className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 px-4 py-2 rounded-lg flex items-center space-x-2 cursor-pointer transition-all">
                  <input type="file" accept=".json" onChange={load} className="hidden" />
                  <FolderOpen size={16} />
                  <span>Load</span>
                </label>
                <button
                  onClick={() => setShowScript(!showScript)}
                  className="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 px-4 py-2 rounded-lg flex items-center space-x-2 transition-all"
                >
                  <FileText size={16} />
                  <span>AI Script</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            {showScript && (
              <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
                <h3 className="text-xl font-semibold mb-4">AI Script Generator</h3>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <input
                    value={scriptTopic}
                    onChange={(e) => setScriptTopic(e.target.value)}
                    className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2"
                    placeholder="Topic..."
                  />
                  <select
                    value={scriptStyle}
                    onChange={(e) => setScriptStyle(e.target.value)}
                    className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2"
                  >
                    <option value="educational">Educational</option>
                    <option value="narrative">Narrative</option>
                    <option value="promotional">Promotional</option>
                    <option value="documentary">Documentary</option>
                    <option value="tutorial">Tutorial</option>
                  </select>
                  <input
                    type="number"
                    value={scriptDuration}
                    onChange={(e) => setScriptDuration(parseInt(e.target.value) || 60)}
                    className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2"
                    min="30"
                    max="600"
                    placeholder="Duration (s)"
                  />
                </div>
                <button
                  onClick={genScriptFn}
                  disabled={genScript}
                  className="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 px-6 py-2 rounded-lg transition-all"
                >
                  {genScript ? '⏳ Generating...' : '✨ Generate Script'}
                </button>
              </div>
            )}

            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
              <h3 className="text-xl font-semibold mb-4">Script</h3>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="w-full h-40 bg-slate-700/50 border border-slate-600 rounded-lg p-4 resize-none focus:border-purple-500 focus:outline-none transition-colors"
                placeholder="Enter script... (Each sentence ending with . will become a scene)"
              />
              <div className="mt-4 flex items-center justify-between">
                <div className="text-sm text-slate-400">
                  <span>💡 Each sentence (ending with .) = 1 scene</span>
                </div>
                <button
                  onClick={split}
                  disabled={loading}
                  className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 px-6 py-2 rounded-lg transition-all"
                >
                  ✂️ Split into Scenes
                </button>
              </div>
            </div>

            {scenes.length > 0 && (
              <>
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-semibold">Scenes ({scenes.length})</h3>
                    <div className="flex space-x-2">
                      <button 
                        onClick={() => setShowBulk(true)} 
                        className="bg-blue-500/20 hover:bg-blue-500/30 px-3 py-2 rounded-lg text-sm transition-all"
                        title="Bulk Edit"
                      >
                        <Settings size={14} />
                      </button>
                      <button 
                        onClick={add} 
                        className="bg-purple-500/20 hover:bg-purple-500/30 p-2 rounded-lg transition-all"
                        title="Add Scene"
                      >
                        <Plus size={16} />
                      </button>
                      <button
                        onClick={genImages}
                        disabled={loading}
                        className="bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 disabled:opacity-50 px-4 py-2 rounded-lg transition-all"
                      >
                        🎨 Generate All
                      </button>
                    </div>
                  </div>

                  <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
                    {scenes.map((s, i) => (
                      <div
                        key={s.id}
                        draggable
                        onDragStart={() => dragStart(i)}
                        onDragOver={(e) => dragOver(e, i)}
                        onDragEnd={dragEnd}
                        className="bg-slate-700/30 rounded-lg p-4 border border-slate-600/50 hover:border-purple-500/50 transition-all cursor-move"
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-2">
                            <GripVertical size={16} className="text-slate-400" />
                            <span className="text-sm font-semibold">Scene {i + 1}</span>
                          </div>
                          <div className="flex space-x-1">
                            <button 
                              onClick={() => dup(i)} 
                              className="text-blue-400 hover:text-blue-300 p-1 transition-colors"
                              title="Duplicate"
                            >
                              <Copy size={14} />
                            </button>
                            <button 
                              onClick={() => del(i)} 
                              className="text-red-400 hover:text-red-300 p-1 transition-colors"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                        
                        <div className="space-y-3">
                          <textarea
                            value={s.text}
                            onChange={(e) => update(i, 'text', e.target.value)}
                            className="w-full bg-slate-600/30 border border-slate-500 rounded p-2 text-sm focus:border-purple-500 focus:outline-none transition-colors"
                            rows="2"
                            placeholder="Scene text..."
                          />
                          <textarea
                            value={s.image_prompt || ''}
                            onChange={(e) => update(i, 'image_prompt', e.target.value)}
                            className="w-full bg-slate-600/30 border border-purple-500/30 rounded p-2 text-sm focus:border-purple-500 focus:outline-none transition-colors"
                            rows="2"
                            placeholder="Custom image prompt (optional)..."
                          />
                          <div className="grid grid-cols-2 gap-3">
                            <input
                              type="number"
                              value={s.duration}
                              onChange={(e) => {
                                const val = e.target.value;
                                update(i, 'duration', val === '' ? '' : parseFloat(val) || 0);
                              }}
                              className="bg-slate-600/30 border border-slate-500 rounded px-2 py-1 text-sm focus:border-purple-500 focus:outline-none transition-colors"
                              min="1"
                              step="0.5"
                              placeholder="Duration"
                            />
                            <select
                              value={s.voice_id || ''}
                              onChange={(e) => update(i, 'voice_id', e.target.value)}
                              className="bg-slate-600/30 border border-slate-500 rounded px-2 py-1 text-sm focus:border-purple-500 focus:outline-none transition-colors"
                              disabled={!useElevenLabs}
                            >
                              <option value="">Default Voice</option>
                              {voices.map(v => (
                                <option key={v.voice_id} value={v.voice_id}>{v.name}</option>
                              ))}
                            </select>
                          </div>
                          <div className="flex items-center space-x-2">
                            <input
                              type="file"
                              onChange={(e) => upload(i, e.target.files[0])}
                              accept="image/*,video/*"
                              className="hidden"
                              id={`file-${i}`}
                            />
                            <label
                              htmlFor={`file-${i}`}
                              className="flex items-center space-x-2 bg-slate-600/30 hover:bg-slate-600/50 px-3 py-1 rounded text-xs cursor-pointer transition-all"
                            >
                              <Upload size={12} />
                              <span>Upload</span>
                            </label>
                            <button
                              onClick={() => openStockModal(i)}
                              className="flex items-center space-x-2 bg-blue-500/20 hover:bg-blue-500/30 px-3 py-1 rounded text-xs transition-all"
                            >
                              <Image size={12} />
                              <span>Stock</span>
                            </button>
                            <button
                              onClick={() => retry(i)}
                              disabled={retrying.has(i)}
                              className="flex items-center space-x-2 bg-orange-500/20 hover:bg-orange-500/30 px-3 py-1 rounded text-xs disabled:opacity-50 transition-all"
                            >
                              <RefreshCw size={12} className={retrying.has(i) ? "animate-spin" : ""} />
                              <span>AI</span>
                            </button>
                          </div>
                          {s.background_path && (
                            <div className="text-xs text-green-400 bg-green-500/10 px-2 py-2 rounded flex items-center space-x-2">
                              <Check size={12} />
                              <span>Background ready</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
                  <h3 className="text-xl font-semibold mb-4">🎬 Render Video</h3>
                  {estimatedTime > 0 && !rendering && (
                    <div className="mb-4 text-sm bg-blue-500/10 border border-blue-500/30 p-3 rounded-lg">
                      ⏱️ Estimated time: ~{fmt(estimatedTime)} ({scenes.length} scenes)
                    </div>
                  )}
                  <button
                    onClick={render}
                    disabled={loading}
                    className="w-full bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 py-3 rounded-lg font-semibold transition-all"
                  >
                    {loading ? '🎬 Rendering...' : '▶️ Render Video'}
                  </button>
                  {loading && (
                    <div className="bg-slate-700/50 rounded-lg p-4 mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm">{stage}</span>
                        <span className="text-sm font-semibold">{progress}%</span>
                      </div>
                      <div className="w-full bg-slate-600 rounded-full h-3 overflow-hidden">
                        <div 
                          className="bg-gradient-to-r from-green-500 to-emerald-500 h-3 rounded-full transition-all duration-300"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                  {videoUrl && (
                    <div className="space-y-4 mt-4">
                      <video 
                        controls 
                        controlsList="nodownload"
                        className="w-full rounded-lg bg-black border border-purple-500/30"
                        style={{ maxHeight: '300px' }}
                        key={videoUrl.preview}
                      >
                        <source src={videoUrl.preview} type="video/mp4" />
                      </video>
                      <div className="flex space-x-3">
                        <button
                          onClick={download}
                          className="flex-1 bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg flex items-center justify-center space-x-2 transition-all"
                        >
                          <Download size={16} />
                          <span>Download</span>
                        </button>
                        <button
                          onClick={() => window.open(videoUrl.preview, '_blank')}
                          className="flex-1 bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded-lg flex items-center justify-center space-x-2 transition-all"
                        >
                          <Play size={16} />
                          <span>Open</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="space-y-6">
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
              <h3 className="text-lg font-semibold mb-4">🎙️ Audio Settings</h3>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm">ElevenLabs TTS</span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useElevenLabs}
                    onChange={(e) => toggleElevenLabs(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-600 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-500"></div>
                </label>
              </div>
              {useElevenLabs && voicesLoading && (
                <div className="text-xs text-slate-400 mt-2">Loading voices...</div>
              )}
              {useElevenLabs && voicesLoaded && voices.length > 0 && (
                <div className="text-xs text-green-400 mt-2">✓ {voices.length} voices loaded</div>
              )}
            </div>

            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
              <h3 className="text-lg font-semibold mb-4 flex items-center">
                <Music size={18} className="mr-2 text-pink-400" />
                Background Music
              </h3>
              
              {selectedMusic ? (
                <div className="space-y-3">
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="text-sm text-green-400 font-semibold flex items-center space-x-2">
                          <Check size={14} />
                          <span>{selectedMusic.name || 'Custom Music'}</span>
                        </div>
                      </div>
                      <button 
                        onClick={() => setSelectedMusic(null)} 
                        className="text-red-400 hover:text-red-300 text-xs font-semibold transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Volume</span>
                        <span className="font-semibold">{musicVolume}%</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Volume2 size={14} className="text-slate-400" />
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={musicVolume}
                          onChange={(e) => setMusicVolume(parseInt(e.target.value))}
                          className="flex-1 accent-green-500"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <label className="w-full bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 px-4 py-3 rounded-lg flex items-center justify-center space-x-2 cursor-pointer transition-all font-semibold">
                    <input
                      type="file"
                      accept=".mp3,.wav,.m4a,.ogg"
                      onChange={(e) => uploadMusic(e.target.files[0])}
                      className="hidden"
                    />
                    <Upload size={16} />
                    <span>Upload Your Music</span>
                  </label>
                  <div className="text-xs text-slate-400 text-center mt-2">
                    Supports: MP3, WAV, M4A, OGG
                  </div>
                </div>
              )}
            </div>

            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
              <h3 className="text-lg font-semibold mb-4">🎨 Visual Settings</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Auto AI Images</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoAI}
                      onChange={(e) => setAutoAI(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-600 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Subtitles</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={subtitles}
                      onChange={(e) => setSubtitles(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-600 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-500"></div>
                  </label>
                </div>
                {subtitles && (
                  <div className="space-y-3 pl-4 border-l-2 border-blue-500/30">
                    <select
                      value={subtitleStyle}
                      onChange={(e) => setSubtitleStyle(e.target.value)}
                      className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:border-blue-500 focus:outline-none transition-colors"
                    >
                      <option value="bottom">Bottom</option>
                      <option value="top">Top</option>
                      <option value="center">Center</option>
                    </select>
                    <div>
                      <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                        <span>Font Size</span>
                        <span className="font-semibold">{fontSize}px</span>
                      </div>
                      <input
                        type="range"
                        min="8"
                        max="64"
                        step="2"
                        value={fontSize}
                        onChange={(e) => setFontSize(parseInt(e.target.value))}
                        className="w-full accent-blue-500"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
              <h3 className="text-lg font-semibold mb-4">📊 Status</h3>
              {status && (
                <div className={`p-3 rounded-lg text-sm ${
                  status.includes('✅') ? 
                    'bg-green-500/10 text-green-400 border border-green-500/30' :
                  status.includes('❌') ? 
                    'bg-red-500/10 text-red-400 border border-red-500/30' :
                  'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                }`}>
                  {status}
                </div>
              )}
            </div>

            {scenes.length > 0 && (
              <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
                <h3 className="text-lg font-semibold mb-4">📈 Project Stats</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Total Scenes</span>
                    <span className="font-semibold text-purple-400">{scenes.length}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Duration</span>
                    <span className="font-semibold text-blue-400">{fmt(Math.floor(totalDur))}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Total Words</span>
                    <span className="font-semibold text-green-400">{totalWords}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Images Ready</span>
                    <span className="font-semibold text-pink-400">{withImages}/{scenes.length}</span>
                  </div>
                  {selectedMusic && (
                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Music</span>
                      <span className="font-semibold text-yellow-400">✓ Added</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {showBulk && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl p-6 max-w-md w-full border border-purple-500/30">
            <h3 className="text-xl font-semibold mb-4">⚙️ Bulk Edit Scenes</h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-slate-400 block mb-2">Duration (seconds)</label>
                <input
                  type="number"
                  value={bulkDur}
                  onChange={(e) => setBulkDur(parseFloat(e.target.value) || 5)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 focus:border-purple-500 focus:outline-none transition-colors"
                  min="1"
                  step="0.5"
                />
              </div>
              <div>
                <label className="text-sm text-slate-400 block mb-2">Voice</label>
                <select
                  value={bulkVoice}
                  onChange={(e) => setBulkVoice(e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 focus:border-purple-500 focus:outline-none transition-colors"
                  disabled={!useElevenLabs}
                >
                  <option value="">Default Voice</option>
                  {voices.map(v => (
                    <option key={v.voice_id} value={v.voice_id}>{v.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex space-x-3 mt-6">
              <button 
                onClick={bulk} 
                className="flex-1 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 py-2 rounded-lg font-semibold transition-all"
              >
                Apply to All
              </button>
              <button 
                onClick={() => setShowBulk(false)} 
                className="flex-1 bg-slate-600 hover:bg-slate-500 py-2 rounded-lg transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {showStock && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl p-6 max-w-4xl w-full max-h-[85vh] overflow-y-auto border border-purple-500/30">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-2xl font-semibold flex items-center">
                <Image size={24} className="mr-2 text-blue-400" />
                Stock Media Library
              </h3>
              <button 
                onClick={() => setShowStock(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X size={24} />
              </button>
            </div>
            <div className="flex space-x-2 mb-6">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={stockQuery}
                  onChange={(e) => setStockQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && searchStock(stockQuery)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 focus:border-blue-500 focus:outline-none transition-colors"
                  placeholder="Search for stock images..."
                />
              </div>
              <button
                onClick={() => searchStock(stockQuery)}
                disabled={loadingStock}
                className="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 px-6 py-3 rounded-lg font-semibold transition-all"
              >
                {loadingStock ? '⏳' : '🔍'} Search
              </button>
            </div>
            {loadingStock ? (
              <div className="text-center py-16">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                <p className="mt-4 text-slate-400">Searching stock library...</p>
              </div>
            ) : stockResults.length > 0 ? (
              <div className="grid grid-cols-3 gap-4">
                {stockResults.map((m, i) => (
                  <div
                    key={i}
                    className="relative group cursor-pointer border border-slate-600 rounded-lg overflow-hidden hover:border-purple-500 transition-all"
                    onClick={() => applyStock(m)}
                  >
                    <img src={m.thumbnail} alt={m.alt} className="w-full h-40 object-cover" />
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <span className="text-white font-semibold">Apply to Scene</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-16 text-slate-400">
                <Image size={64} className="mx-auto mb-4 opacity-30" />
                <p className="text-lg mb-2">No results yet</p>
                <p className="text-sm">Search for stock photos to get started</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
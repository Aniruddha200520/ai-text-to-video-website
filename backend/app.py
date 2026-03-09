#!/usr/bin/env python3
import os, uuid, json
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from utils import (
    split_text_into_scenes,
    render_video,
    ai_generate_image,
    test_ai_generation,
    client,
    UPLOADS,
    OUTPUTS,
    MUSIC_CACHE,
    generate_script_openai,
    get_available_voices,
    PEXELS_API_KEY,
    get_scene_durations,
)
import requests
from PIL import Image
from io import BytesIO

from pexels_api import (
    search_pexels_images,
    search_pexels_videos,
    search_and_download_image,
    search_and_download_video
)

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET","POST","PUT","DELETE","OPTIONS"], "allow_headers": ["Content-Type","Authorization","Accept"], "expose_headers": ["Content-Type","Content-Length"], "supports_credentials": False, "max_age": 3600}})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,ngrok-skip-browser-warning')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

for p in (UPLOADS, OUTPUTS, MUSIC_CACHE):
    os.makedirs(p, exist_ok=True)

@app.route("/api/health", methods=["GET","OPTIONS"])
def health_check():
    return jsonify({"status": "ok", "message": "Backend is running", "cors": "enabled"})

@app.route("/api/generate_script", methods=["POST","OPTIONS"])
def api_generate_script():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    data = request.get_json(force=True)
    topic = (data.get("topic") or "").strip()
    style = data.get("style", "educational")
    duration = data.get("duration", 60)
    if not topic: return jsonify({"error": "topic required"}), 400
    try:
        script = generate_script_openai(topic, style=style, duration=duration)
        return jsonify({"success": True, "script": script, "topic": topic, "style": style, "duration": duration})
    except Exception as e:
        print(f"[ERROR] Script generation failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/voices", methods=["GET","OPTIONS"])
def api_get_voices():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    try:
        voices = get_available_voices()
        return jsonify({"voices": voices, "success": True})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e), "voices": [], "success": False}), 500

@app.route("/api/split", methods=["POST","OPTIONS"])
def api_split():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text: return jsonify({"error": "text required"}), 400
    chunks = split_text_into_scenes(text)
    scenes = [{"id": f"scene_{i+1}", "text": chunk, "background_path": "", "duration": 5, "voice_id": "", "image_prompt": ""} for i, chunk in enumerate(chunks)]
    return jsonify({"scenes": scenes})

@app.route("/api/upload_background", methods=["POST","OPTIONS"])
def api_upload_background():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    if "file" not in request.files: return jsonify({"error": "file is required"}), 400
    scene_id = request.form.get("scene_id", "scene")
    f = request.files["file"]
    ext = os.path.splitext(f.filename)[1].lower() or ".dat"
    if ext in ['.jpg','.jpeg','.png','.bmp','.gif','.webp']:
        try:
            img = Image.open(f)
            if img.mode in ('RGBA','LA','P'):
                bg = Image.new('RGB', img.size, (255,255,255))
                if img.mode == 'P': img = img.convert('RGBA')
                if img.mode in ('RGBA','LA'): bg.paste(img, mask=img.split()[-1]); img = bg
            filename = f"{scene_id}_uploaded.png"
            out = os.path.join(UPLOADS, filename)
            img.save(out, 'PNG', optimize=False, compress_level=3)
            return jsonify({"scene_id": scene_id, "background_path": out, "filename": filename, "url": f"/api/uploads/{filename}"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        filename = f"{scene_id}{ext}"
        out = os.path.join(UPLOADS, filename)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        f.save(out)
        return jsonify({"scene_id": scene_id, "background_path": out, "filename": filename, "url": f"/api/uploads/{filename}"})

@app.route("/api/uploads/<filename>", methods=["GET","OPTIONS"])
def serve_upload(filename):
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    try:
        return send_from_directory(UPLOADS, filename)
    except:
        return jsonify({"error": "File not found"}), 404

@app.route("/api/test_cloudflare", methods=["GET","OPTIONS"])
def api_test_cloudflare():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    try:
        if not client.get("available", False):
            return jsonify({"status":"error","message":"Cloudflare Workers AI not available."}), 500
        success = test_ai_generation()
        if success: return jsonify({"status":"success","message":"Cloudflare Workers AI is working!","client_available":True})
        return jsonify({"status":"error","message":"API test failed","client_available":True}), 500
    except Exception as e:
        return jsonify({"status":"error","message":f"Test failed: {str(e)}","client_available":client.get("available",False)}), 500

@app.route("/api/generate_single_image", methods=["POST","OPTIONS"])
def api_generate_single_image():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    data = request.get_json(force=True)
    prompt = (data.get("prompt") or "").strip()
    if not prompt: return jsonify({"error": "prompt required"}), 400
    try:
        scene_id = f"test_{uuid.uuid4().hex[:8]}"
        filename = f"{scene_id}.png"
        path = os.path.join(UPLOADS, filename)
        result_path = ai_generate_image(prompt, path)
        return jsonify({"success":True,"prompt":prompt,"image_path":result_path,"filename":filename,"download_url":f"/api/uploads/{filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download_image", methods=["GET","OPTIONS"])
def api_download_image():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    path = os.path.abspath(request.args.get("path",""))
    uploads_abs = os.path.abspath(UPLOADS)
    gen_img_abs = os.path.abspath(os.path.join(os.path.dirname(__file__),"generated_images"))
    if not (path.startswith(uploads_abs) or path.startswith(gen_img_abs)):
        return jsonify({"error":"invalid path"}), 400
    try:
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stock_search", methods=["GET","OPTIONS"])
def api_stock_search():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    query = request.args.get("query","").strip()
    if not query: return jsonify({"error":"query required"}), 400
    pexels_key = os.getenv('PEXELS_API_KEY')
    if not pexels_key: return jsonify({"results":[],"message":"Pexels API not configured"}), 200
    try:
        r = requests.get(f"https://api.pexels.com/v1/search?query={query}&per_page=15", headers={"Authorization":pexels_key}, timeout=10)
        if r.status_code == 200:
            results = [{"type":"image","url":p['src']['large2x'],"thumbnail":p['src']['medium'],"alt":p.get('alt',''),"photographer":p.get('photographer','')} for p in r.json().get('photos',[])]
            return jsonify({"results":results,"success":True})
        return jsonify({"results":[],"error":"Pexels API error"}), 500
    except Exception as e:
        return jsonify({"results":[],"error":str(e)}), 500

@app.route("/api/download_stock", methods=["POST","OPTIONS"])
def api_download_stock():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    data = request.get_json(force=True)
    url = data.get("url",""); scene_id = data.get("scene_id","scene"); media_type = data.get("type","image")
    if not url: return jsonify({"error":"url required"}), 400
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            if media_type == "image":
                img = Image.open(BytesIO(r.content))
                if img.mode in ('RGBA','LA','P'):
                    bg = Image.new('RGB', img.size, (255,255,255))
                    if img.mode == 'P': img = img.convert('RGBA')
                    if img.mode in ('RGBA','LA'): bg.paste(img, mask=img.split()[-1]); img = bg
                filename = f"{scene_id}_stock.png"
                filepath = os.path.join(UPLOADS, filename)
                img.save(filepath,'PNG',optimize=False,compress_level=3)
                return jsonify({"path":filepath,"filename":filename,"url":f"/api/uploads/{filename}","success":True})
            else:
                filename = f"{scene_id}_stock.mp4"
                filepath = os.path.join(UPLOADS, filename)
                with open(filepath,'wb') as f: f.write(r.content)
                return jsonify({"path":filepath,"filename":filename,"url":f"/api/uploads/{filename}","success":True})
        return jsonify({"error":f"Download failed: {r.status_code}"}), 500
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/music/upload", methods=["POST","OPTIONS"])
def api_music_upload():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    if "file" not in request.files: return jsonify({"error":"file is required"}), 400
    f = request.files["file"]
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ['.mp3','.wav','.m4a','.ogg']: return jsonify({"error":"Invalid audio format"}), 400
    filename = f"custom_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(MUSIC_CACHE, filename)
    os.makedirs(MUSIC_CACHE, exist_ok=True)
    try:
        f.save(filepath)
        return jsonify({"success":True,"path":filepath,"filename":filename})
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/generate_images", methods=["POST","OPTIONS"])
def api_generate_images():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    data = request.get_json(force=True)
    scenes = data.get("scenes",[]) or []
    out = []
    for s in scenes:
        scene_id = s.get("id","scene")
        filename = f"{scene_id}.png"
        path = os.path.join(UPLOADS, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        image_prompt = s.get("image_prompt","").strip() or s.get("text","").strip()
        try:
            result_path = ai_generate_image(image_prompt, path)
            out.append({"id":scene_id,"background_path":result_path,"filename":filename,"url":f"/api/uploads/{filename}","success":True,"prompt_used":image_prompt[:50]})
        except Exception as e:
            out.append({"id":scene_id,"background_path":"","success":False,"error":str(e)})
    return jsonify({"images":out})

@app.route("/api/video/<filename>", methods=["GET","OPTIONS"])
def serve_video(filename):
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    try:
        video_path = os.path.abspath(os.path.join(OUTPUTS, filename))
        if not video_path.startswith(os.path.abspath(OUTPUTS)): return jsonify({"error":"invalid path"}), 400
        if not os.path.exists(video_path): return jsonify({"error":"file not found"}), 404
        file_size = os.path.getsize(video_path)
        range_header = request.headers.get('Range')
        if not range_header:
            is_download = request.args.get('download') == 'true'
            def generate():
                with open(video_path,'rb') as f:
                    d = f.read(8192)
                    while d: yield d; d = f.read(8192)
            headers = {'Content-Type':'video/mp4','Content-Length':str(file_size),'Accept-Ranges':'bytes','Content-Disposition':f"{'attachment' if is_download else 'inline'}; filename={filename}"}
            return app.response_class(generate(), headers=headers)
        parts = range_header.replace('bytes=','').split('-')
        start = int(parts[0]) if parts[0] else 0
        end   = int(parts[1]) if len(parts)>1 and parts[1] else file_size-1
        if start >= file_size or end >= file_size or start > end: return jsonify({"error":"Invalid range"}), 416
        length = end - start + 1
        def generate_range():
            with open(video_path,'rb') as f:
                f.seek(start); rem = length
                while rem > 0:
                    chunk = f.read(min(8192,rem))
                    if not chunk: break
                    rem -= len(chunk); yield chunk
        headers = {'Content-Type':'video/mp4','Content-Range':f'bytes {start}-{end}/{file_size}','Accept-Ranges':'bytes','Content-Length':str(length),'Content-Disposition':f'inline; filename={filename}'}
        return app.response_class(generate_range(), status=206, headers=headers)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e)}), 500

# ── RENDER ───────────────────────────────────────────────────────────────────
@app.route("/api/render", methods=["POST","OPTIONS"])
def api_render():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    data             = request.get_json(force=True)
    project          = data.get("project_name","video_project")
    main_keyword     = (data.get("main_keyword") or "").strip()
    scenes           = data.get("scenes",[]) or []
    auto_ai          = bool(data.get("auto_ai_images",True))
    subtitles        = bool(data.get("subtitles", True))
    subtitle_style   = data.get("subtitle_style","bottom")
    font_size        = int(data.get("font_size",48))
    use_elevenlabs   = True
    background_music = data.get("background_music",None)
    music_volume     = float(data.get("music_volume",0.1))
    use_avatar       = bool(data.get("use_avatar",False))
    avatar_position  = data.get("avatar_position","bottom-right")
    avatar_size      = data.get("avatar_size","medium")
    avatar_style     = data.get("avatar_style","male")

    print(f"[INFO] Render: '{project}' | {len(scenes)} scenes | elevenlabs=ALWAYS | avatar={use_avatar}")
    try:
        path = render_video(
            project_name=project, scenes=scenes, auto_ai=auto_ai,
            size=(1280,720), fps=25, subtitles=subtitles,
            subtitle_style=subtitle_style, font_size=font_size,
            use_elevenlabs=use_elevenlabs,
            background_music=background_music, music_volume=music_volume,
            use_avatar=use_avatar, avatar_position=avatar_position,
            avatar_size=avatar_size, avatar_style=avatar_style,
            main_keyword=main_keyword
        )
        filename = os.path.basename(path)
        return jsonify({"video_path":path,"filename":filename,"download_url":f"/api/video/{filename}"})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e)}), 500

@app.route("/api/download", methods=["GET","OPTIONS"])
def api_download():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    path = os.path.abspath(request.args.get("path",""))
    if not path or not path.startswith(os.path.abspath(OUTPUTS)): return jsonify({"error":"invalid path"}), 400
    if not os.path.exists(path): return jsonify({"error":"file not found"}), 404
    try:
        filename = os.path.basename(path)
        def generate():
            with open(path,'rb') as f:
                while True:
                    d = f.read(4096)
                    if not d: break
                    yield d
        return app.response_class(generate(), mimetype="video/mp4", headers={"Content-Disposition":f"attachment; filename={filename}","Content-Type":"video/mp4"})
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.get("/")
def root():
    return jsonify({"ok":True,"service":"ai-text-to-video-backend","cloudflare":client.get("available",False),"cors":"enabled","avatar":"enabled"})

# ── STATIC images ────────────────────────────────────────────────────────────
@app.route("/api/generate_images_v2", methods=["POST","OPTIONS"])
def generate_images_v2():
    if request.method == "OPTIONS": return "", 200
    try:
        scenes       = request.json.get("scenes",[])
        main_keyword = (request.json.get("main_keyword") or "").strip()
        results = []
        for scene in scenes:
            scene_id = scene["id"]
            base_prompt = scene.get("image_prompt") or scene.get("text","")
            # Prepend keyword so Flux stays on-topic even when scene text is vague
            # e.g. keyword="cats" + "they are very curious" → "cats, they are very curious"
            prompt = f"{main_keyword}, {base_prompt}" if main_keyword and main_keyword.lower() not in base_prompt.lower() else base_prompt
            print(f"[INFO] Static image: {scene_id} — prompt: '{prompt[:80]}'")
            ok = False
            try:
                filename    = f"{scene_id}.png"
                result_path = os.path.join(UPLOADS, filename)
                os.makedirs(UPLOADS, exist_ok=True)
                result_path = ai_generate_image(prompt, result_path)
                if result_path and os.path.exists(result_path):
                    ok = True; filename = os.path.basename(result_path); source = "cloudflare"
            except Exception as e:
                print(f"[WARN] Cloudflare failed: {e}")
            if not ok:
                pr = search_and_download_image(prompt, scene_id, UPLOADS)
                if pr["success"]:
                    result_path = pr["path"]; filename = pr["filename"]; source = "pexels"
                else:
                    results.append({"id":scene_id,"success":False,"error":"Both Cloudflare and Pexels failed"}); continue
            results.append({"id":scene_id,"success":True,"background_path":result_path,"url":f"/api/uploads/{filename}","filename":filename,"source":source})
        return jsonify({"images":results})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e)}), 500

# ── DYNAMIC videos — PARALLELISED ────────────────────────────────────────────
@app.route("/api/generate_images_v2_dynamic", methods=["POST","OPTIONS"])
def generate_images_v2_dynamic():
    """
    Fetch Pexels videos per scene — fully parallelised with ThreadPoolExecutor.
    All scenes search + download simultaneously; total time ≈ slowest single scene.
    - Max 30MB per file, per_page=20, duration-aware, prefers 1080p, rejects 4K
    - Falls back to static image if nothing found
    """
    if request.method == "OPTIONS": return "", 200
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    MAX_MB = 30

    try:
        scenes     = request.json.get("scenes", [])
        pexels_key = os.getenv("PEXELS_API_KEY", "")
        main_keyword = (request.json.get("main_keyword") or "").strip()

        # Thread-safe set for deduplicating video IDs across parallel workers
        used_video_ids = set()
        _lock = threading.Lock()

        _sample_voice = next(
            (s.get("voice_id", "").strip() for s in scenes
             if s.get("voice_id", "").strip()
             and s.get("voice_id", "").lower() != "gtts"),
            None
        )

        # Pre-compute TTS durations (already parallelised inside get_scene_durations)
        print("[INFO] Pre-computing scene durations from TTS...")
        try:
            duration_map = {sid: dur for sid, dur
                            in get_scene_durations(scenes, voice_id=_sample_voice)}
        except Exception as _de:
            print(f"[WARN] get_scene_durations failed ({_de}), using 5s defaults")
            duration_map = {s["id"]: 5.0 for s in scenes}

        # Shared subject for Pexels queries:
        # - One-click: extracted from the topic string ("the future of electric vehicles" → "electric vehicles")
        # - Normal UI:  user types it directly in the keyword popup → sent as main_keyword
        # Either way, one Groq call extracts the core noun/phrase from whatever was provided.
        _shared_subject = ""
        _keyword_source = main_keyword or (scenes[0].get("text", "") if scenes else "")
        if _keyword_source:
            try:
                from utils import groq_client, groq_available
                if groq_available and groq_client:
                    _sr = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content":
                            f"Extract ONLY the main subject noun or short noun phrase (1-3 words, e.g. 'cat', "
                            f"'electric vehicles', 'coffee shop') from this text. "
                            f"Reply with ONLY that noun/phrase, nothing else:\n\n{_keyword_source[:200]}"}],
                        max_tokens=8, temperature=0.0)
                    _shared_subject = _sr.choices[0].message.content.strip().strip(" \t\"'.,").lower()
                    print(f"[INFO] Shared Pexels subject: '{_shared_subject}' (from: '{_keyword_source[:60]}')")
            except Exception as _se:
                print(f"[WARN] Subject extraction failed ({_se}), using source directly")
                _shared_subject = _keyword_source.split()[-1].lower()  # last word of topic as fallback
        if not _shared_subject and scenes:
            _shared_subject = (scenes[0].get("text") or "").split()[0].lower()

        def _get_search_query(scene_text, shared_subject):
            """Fallback: build a query from scene text + shared subject."""
            if not shared_subject:
                return scene_text[:60]
            words = [w.strip(".,!?") for w in scene_text.split() if len(w) > 4]
            extra = words[0] if words else ""
            return f"{shared_subject} {extra}".strip() if extra else shared_subject

        # Pre-compute ALL Pexels queries in ONE Groq call so each scene gets a
        # distinct, context-aware query based on the full narrative — not just
        # its own 3 words.
        _query_map = {}
        try:
            from utils import groq_client, groq_available
            if groq_available and groq_client and _shared_subject and scenes:
                _scene_list = "\n".join(
                    f"{i+1}. [{s['id']}] {(s.get('text') or '')[:120]}"
                    for i, s in enumerate(scenes)
                    if not s.get("image_prompt", "").strip()
                )
                if _scene_list:
                    _qr = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content":
                            f"Subject: '{_shared_subject}'\n"
                            f"Here are the video scenes:\n{_scene_list}\n\n"
                            f"For EACH scene generate a unique 2-4 word Pexels stock video search query.\n"
                            f"Rules:\n"
                            f"- Always start with '{_shared_subject}'\n"
                            f"- Each query MUST be different — no two identical queries\n"
                            f"- Use each scene's specific content for the action/setting\n"
                            f"  (e.g. 'charging station', 'highway driving', 'factory production', 'city commute')\n"
                            f"- Reply ONLY as valid JSON: {{\"scene_id\": \"query\", ...}}\n"
                            f"- Example: {{\"scene_1\": \"electric vehicles charging\", \"scene_2\": \"electric vehicles highway\"}}"
                        }],
                        max_tokens=400,
                        temperature=0.4,
                    )
                    import json as _json, re as _re4
                    _raw = _qr.choices[0].message.content.strip()
                    _raw = _re4.sub(r"```[a-z]*\n?|```", "", _raw).strip()
                    try:
                        _query_map = _json.loads(_raw)
                        print(f"[INFO] Pre-computed {len(_query_map)} Pexels queries:")
                        for sid, q in _query_map.items():
                            print(f"       {sid}: '{q}'")
                    except Exception as _je:
                        print(f"[WARN] Query map parse failed ({_je}), falling back to per-scene")
        except Exception as _qe:
            print(f"[WARN] Bulk query generation failed ({_qe}), falling back to per-scene")

        def _fetch_one(scene):
            """Search Pexels and download video for one scene. Runs in its own thread."""
            scene_id     = scene["id"]
            raw_text     = scene.get("text", "")
            min_duration = duration_map.get(scene_id, 5.0)

            # Use custom image_prompt if set, otherwise ask Groq for context-aware query
            if scene.get("image_prompt", "").strip():
                prompt = scene["image_prompt"].strip()
                print(f"[INFO] Dynamic video search: {scene_id} — using custom prompt")
            else:
                # Use pre-computed query if available, else fallback
                if scene_id in _query_map:
                    prompt = _query_map[scene_id]
                    if _shared_subject and _shared_subject.lower() not in prompt.lower():
                        prompt = _shared_subject + " " + prompt
                else:
                    prompt = _get_search_query(raw_text, _shared_subject)
                print(f"[INFO] Dynamic video search: {scene_id} — query: '{prompt}'")
            print(f"       Min duration needed: {min_duration:.1f}s")

            video_url       = None
            selected_vid_id = None

            def score_file(f):
                w    = f.get("width", 0)
                size = f.get("size", 0) / (1024 * 1024)
                if size > MAX_MB: return -1
                if w > 2560:     return -1  # reject 4K
                return -abs(w - 1920)        # closest to 1080p wins

            def best_file_for_vid(vid):
                files = [f for f in vid.get("video_files", [])
                         if "video" in f.get("file_type", "")]
                if not files: return None
                bf = max(files, key=score_file)
                if score_file(bf) < 0:
                    bf = min(files, key=lambda f: f.get("size", 999999999))
                    if bf.get("size", 0) / 1024 / 1024 > MAX_MB: return None
                return bf

            try:
                r = requests.get(
                    "https://api.pexels.com/videos/search",
                    params={"query": prompt, "per_page": 20, "orientation": "landscape"},
                    headers={"Authorization": pexels_key},
                    timeout=15
                )
                if r.status_code == 200:
                    videos = r.json().get("videos", [])

                    # Snapshot used IDs under lock so we don't block during selection
                    with _lock:
                        _used = set(used_video_ids)

                    # First pass: clips >= min_duration (no looping needed)
                    candidates = []
                    for vid in videos:
                        vid_id  = vid.get("id")
                        vid_dur = float(vid.get("duration", 0))
                        if vid_id in _used: continue
                        if vid_dur < min_duration: continue
                        bf = best_file_for_vid(vid)
                        if bf:
                            candidates.append((vid_id, bf, bf.get("size", 0) / 1024 / 1024, vid_dur))

                    if not candidates:
                        # Second pass: accept any duration (utils.py loops seamlessly)
                        print(f"    [WARN] No clip >= {min_duration:.1f}s — fallback to any duration (will loop)")
                        for vid in videos:
                            vid_id  = vid.get("id")
                            vid_dur = float(vid.get("duration", 0))
                            if vid_id in _used: continue
                            bf = best_file_for_vid(vid)
                            if bf:
                                candidates.append((vid_id, bf, bf.get("size", 0) / 1024 / 1024, vid_dur))

                    if candidates:
                        candidates.sort(key=lambda x: abs(x[1].get("width", 0) - 1920))
                        # Pick randomly from top-10 (wider pool = fewer repeats across scenes)
                        import random as _rnd
                        pool = candidates[:10]
                        _rnd.shuffle(pool)
                        selected_vid_id, selected_file, size_mb, vid_dur = pool[0]
                        video_url = selected_file.get("link")
                        w = selected_file.get("width", "?")
                        h = selected_file.get("height", "?")
                        suffix = "✓ long enough" if vid_dur >= min_duration else "— will loop"
                        print(f"    [Pexels] selected: {w}×{h} ({size_mb:.1f}MB, {vid_dur:.1f}s) {suffix}")
                    else:
                        print(f"[WARN] No suitable video found for {scene_id}")
                else:
                    print(f"[WARN] Pexels API: HTTP {r.status_code}")

            except Exception as e:
                print(f"[WARN] Pexels search error for {scene_id}: {e}")

            # Fall back to static image if no video found
            if not video_url:
                print(f"[WARN] Falling back to Pexels image for {scene_id}")
                pr = search_and_download_image(prompt, scene_id, UPLOADS)
                if pr["success"]:
                    return {
                        "id": scene_id, "success": True,
                        "background_path": pr["path"],
                        "url": f"/api/uploads/{pr['filename']}",
                        "filename": pr["filename"],
                        "source": "pexels_image_fallback"
                    }
                return {"id": scene_id, "success": False, "error": "No video or image found"}

            # Download with hard size guard
            filename  = f"{scene_id}_dynamic.mp4"
            save_path = os.path.join(UPLOADS, filename)
            print(f"[INFO] Downloading Pexels video -> {filename}")
            try:
                dl = requests.get(video_url, timeout=120, stream=True)
                if dl.status_code == 200:
                    downloaded = 0
                    limit = MAX_MB * 1024 * 1024
                    with open(save_path, "wb") as fout:
                        for chunk in dl.iter_content(chunk_size=65536):
                            if chunk:
                                downloaded += len(chunk)
                                if downloaded > limit:
                                    print(f"[WARN] File exceeded {MAX_MB}MB during download, skipping")
                                    fout.close()
                                    try: os.remove(save_path)
                                    except: pass
                                    downloaded = -1
                                    break
                                fout.write(chunk)

                    if downloaded > 0 and os.path.exists(save_path):
                        mb = os.path.getsize(save_path) / 1024 / 1024
                        print(f"[OK] {mb:.1f} MB -> {save_path}")
                        if selected_vid_id:
                            with _lock:
                                used_video_ids.add(selected_vid_id)
                        return {
                            "id": scene_id, "success": True,
                            "background_path": save_path,
                            "url": f"/api/uploads/{filename}",
                            "filename": filename,
                            "source": "pexels_video"
                        }
                    return {"id": scene_id, "success": False, "error": "Download aborted (too large)"}
                return {"id": scene_id, "success": False, "error": f"HTTP {dl.status_code}"}

            except requests.Timeout:
                print(f"[ERR] Download timeout for {scene_id}")
                return {"id": scene_id, "success": False, "error": "Download timeout"}
            except Exception as e:
                print(f"[ERR] Download error for {scene_id}: {e}")
                return {"id": scene_id, "success": False, "error": str(e)}

        # Run all scenes in parallel — max 6 workers (Pexels rate-limit safe)
        print(f"[INFO] Fetching {len(scenes)} scenes in parallel (max 10 workers)...")
        results_map = {}
        with ThreadPoolExecutor(max_workers=min(10, len(scenes))) as pool:
            futures = {pool.submit(_fetch_one, scene): scene["id"] for scene in scenes}
            for fut in as_completed(futures):
                sid = futures[fut]
                try:
                    results_map[sid] = fut.result()
                except Exception as e:
                    results_map[sid] = {"id": sid, "success": False, "error": str(e)}

        # Preserve original scene order in response
        results = [results_map[s["id"]] for s in scenes if s["id"] in results_map]
        return jsonify({"images": results})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ── Pexels video search / manual download ────────────────────────────────────
@app.route("/api/search_pexels_videos", methods=["GET","OPTIONS"])
def search_videos():
    if request.method == "OPTIONS": return "", 200
    query = request.args.get("query","")
    if not query: return jsonify({"success":False,"error":"Query required"}), 400
    try:
        results = search_pexels_videos(query, per_page=15)
        return jsonify({"success":True,"results":results,"count":len(results)})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}), 500

@app.route("/api/download_pexels_video", methods=["POST","OPTIONS"])
def download_video():
    if request.method == "OPTIONS": return "", 200
    try:
        data = request.json
        url = data.get("url"); scene_id = data.get("scene_id")
        if not url or not scene_id: return jsonify({"success":False,"error":"Missing parameters"}), 400
        filename  = f"{scene_id}_pexels_video.mp4"
        save_path = os.path.join(UPLOADS, filename)
        from pexels_api import download_pexels_media
        result = download_pexels_media(url, save_path)
        if result["success"]:
            return jsonify({"success":True,"path":save_path,"url":f"/api/uploads/{filename}","filename":filename})
        return jsonify(result), 500
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}), 500

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎬 AI Text-to-Video API Server + AVATAR")
    print("="*60)
    print(f"🌐 CORS:         ENABLED (all origins)")
    print(f"🖼️  Cloudflare:   {'✅' if client.get('available',False) else '❌'}")
    print(f"📸 Pexels:       {'✅' if os.getenv('PEXELS_API_KEY') else '❌'}")
    print(f"🎭 Avatar:       ENABLED")
    print(f"🎵 ElevenLabs:   ALWAYS ON")
    print(f"🎬 Dynamic mode: /api/generate_images_v2_dynamic (PARALLELISED)")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=5001, debug=True)

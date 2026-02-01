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
    PEXELS_API_KEY
)
import requests
from PIL import Image
from io import BytesIO

app = Flask(__name__)

# ========== FIXED CORS CONFIGURATION ==========
CORS(app, resources={
    r"/*": {
        "origins": "*",  # Allow all origins for development
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept"],
        "expose_headers": ["Content-Type", "Content-Length"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

for p in (UPLOADS, OUTPUTS, MUSIC_CACHE):
    os.makedirs(p, exist_ok=True)

# ========== HEALTH CHECK ENDPOINT ==========
@app.route("/api/health", methods=["GET", "OPTIONS"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "message": "Backend is running",
        "cors": "enabled"
    })

# ========== API Routes ==========
@app.route("/api/generate_script", methods=["POST", "OPTIONS"])
def api_generate_script():
    """Generate script using Groq AI"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json(force=True)
    topic = (data.get("topic") or "").strip()
    style = data.get("style", "educational")
    duration = data.get("duration", 60)
    
    if not topic:
        return jsonify({"error": "topic required"}), 400
    
    try:
        script = generate_script_openai(topic, style=style, duration=duration)
        return jsonify({
            "success": True,
            "script": script,
            "topic": topic,
            "style": style,
            "duration": duration
        })
    except Exception as e:
        print(f"[ERROR] Script generation failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/voices", methods=["GET", "OPTIONS"])
def api_get_voices():
    """Get available ElevenLabs voices"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        print("[INFO] Fetching ElevenLabs voices...")
        voices = get_available_voices()
        print(f"[SUCCESS] Returning {len(voices)} voices")
        return jsonify({"voices": voices, "success": True})
    except Exception as e:
        print(f"[ERROR] Voice fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "voices": [], "success": False}), 500

@app.route("/api/split", methods=["POST", "OPTIONS"])
def api_split():
    """Split text into scenes by period (.)"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    
    if not text:
        return jsonify({"error": "text required"}), 400

    chunks = split_text_into_scenes(text)
    scenes = [
        {"id": f"scene_{i+1}", "text": chunk, "background_path": "", "duration": 5, "voice_id": "", "image_prompt": ""}
        for i, chunk in enumerate(chunks)
    ]
    return jsonify({"scenes": scenes})

@app.route("/api/upload_background", methods=["POST", "OPTIONS"])
def api_upload_background():
    """Upload background image/video - Save as PNG for images"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    scene_id = request.form.get("scene_id", "scene")
    f = request.files["file"]
    ext = os.path.splitext(f.filename)[1].lower() or ".dat"
    
    # For images, convert to PNG for better quality
    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']:
        try:
            img = Image.open(f)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                    img = background
            
            filename = f"{scene_id}_uploaded.png"
            out = os.path.join(UPLOADS, filename)
            img.save(out, 'PNG', optimize=False, compress_level=3)
            print(f"[OK] Uploaded image saved as PNG: {out}")
            
            # Return relative path that frontend can use
            return jsonify({
                "scene_id": scene_id, 
                "background_path": out,
                "filename": filename,
                "url": f"/api/uploads/{filename}"
            })
            
        except Exception as e:
            print(f"[ERROR] Image conversion failed: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        filename = f"{scene_id}{ext}"
        out = os.path.join(UPLOADS, filename)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        f.save(out)
        
        return jsonify({
            "scene_id": scene_id, 
            "background_path": out,
            "filename": filename,
            "url": f"/api/uploads/{filename}"
        })

# ========== NEW: SERVE UPLOADED FILES ==========
@app.route("/api/uploads/<filename>", methods=["GET", "OPTIONS"])
def serve_upload(filename):
    """Serve uploaded files"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        return send_from_directory(UPLOADS, filename)
    except Exception as e:
        print(f"[ERROR] File not found: {filename}")
        return jsonify({"error": "File not found"}), 404

@app.route("/api/test_cloudflare", methods=["GET", "OPTIONS"])
def api_test_cloudflare():
    """Test endpoint to verify Cloudflare Workers AI integration"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        if not client.get("available", False):
            return jsonify({
                "status": "error", 
                "message": "Cloudflare Workers AI endpoint not available."
            }), 500
        
        success = test_ai_generation()
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Cloudflare Workers AI is working!",
                "client_available": True
            })
        else:
            return jsonify({
                "status": "error",
                "message": "API test failed",
                "client_available": True
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Test failed: {str(e)}",
            "client_available": client.get("available", False)
        }), 500

@app.route("/api/generate_single_image", methods=["POST", "OPTIONS"])
def api_generate_single_image():
    """Generate a single AI image for testing"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json(force=True)
    prompt = (data.get("prompt") or "").strip()
    
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    
    try:
        scene_id = f"test_{uuid.uuid4().hex[:8]}"
        filename = f"{scene_id}.png"
        path = os.path.join(UPLOADS, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        result_path = ai_generate_image(prompt, path)
        
        return jsonify({
            "success": True,
            "prompt": prompt,
            "image_path": result_path,
            "filename": filename,
            "download_url": f"/api/uploads/{filename}"
        })
        
    except Exception as e:
        print(f"[ERROR] Image generation failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/download_image", methods=["GET", "OPTIONS"])
def api_download_image():
    """Download generated images"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "path required"}), 400

    path = os.path.abspath(path)
    
    uploads_abs = os.path.abspath(UPLOADS)
    gen_img_abs = os.path.abspath(os.path.join(os.path.dirname(__file__), "generated_images"))
    
    if not (path.startswith(uploads_abs) or path.startswith(gen_img_abs)):
        return jsonify({"error": "invalid path"}), 400

    try:
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stock_search", methods=["GET", "OPTIONS"])
def api_stock_search():
    """Search Pexels for stock photos/videos"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "query required"}), 400
    
    pexels_api_key = os.getenv('PEXELS_API_KEY')
    if not pexels_api_key:
        return jsonify({"results": [], "message": "Pexels API not configured"}), 200
    
    try:
        print(f"[INFO] Searching Pexels for: {query}")
        headers = {"Authorization": pexels_api_key}
        response = requests.get(
            f"https://api.pexels.com/v1/search?query={query}&per_page=15",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for photo in data.get('photos', []):
                results.append({
                    "type": "image",
                    "url": photo['src']['large2x'],
                    "thumbnail": photo['src']['medium'],
                    "alt": photo.get('alt', ''),
                    "photographer": photo.get('photographer', '')
                })
            print(f"[SUCCESS] Found {len(results)} results")
            return jsonify({"results": results, "success": True})
        else:
            print(f"[ERROR] Pexels returned status {response.status_code}")
            return jsonify({"results": [], "error": "Pexels API error"}), 500
            
    except Exception as e:
        print(f"[ERROR] Stock search failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"results": [], "error": str(e)}), 500

@app.route("/api/download_stock", methods=["POST", "OPTIONS"])
def api_download_stock():
    """Download stock media and save as HIGH QUALITY PNG"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json(force=True)
    url = data.get("url", "")
    scene_id = data.get("scene_id", "scene")
    media_type = data.get("type", "image")
    
    if not url:
        return jsonify({"error": "url required"}), 400
    
    try:
        print(f"[INFO] Downloading stock {media_type} from: {url}")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            if media_type == "image":
                try:
                    img = Image.open(BytesIO(response.content))
                    
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode in ('RGBA', 'LA'):
                            background.paste(img, mask=img.split()[-1])
                            img = background
                    
                    filename = f"{scene_id}_stock.png"
                    filepath = os.path.join(UPLOADS, filename)
                    
                    img.save(filepath, 'PNG', optimize=False, compress_level=3)
                    print(f"[OK] Saved stock image: {filepath}")
                    
                    return jsonify({
                        "path": filepath,
                        "filename": filename,
                        "url": f"/api/uploads/{filename}",
                        "success": True
                    })
                    
                except Exception as img_error:
                    print(f"[ERROR] Image processing failed: {img_error}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({"error": f"Image processing failed: {str(img_error)}"}), 500
            else:
                ext = ".mp4"
                filename = f"{scene_id}_stock{ext}"
                filepath = os.path.join(UPLOADS, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                print(f"[OK] Saved stock video: {filepath}")
                return jsonify({
                    "path": filepath,
                    "filename": filename,
                    "url": f"/api/uploads/{filename}",
                    "success": True
                })
        else:
            return jsonify({"error": f"Download failed with status {response.status_code}"}), 500
            
    except Exception as e:
        print(f"[ERROR] Stock download failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/music/upload", methods=["POST", "OPTIONS"])
def api_music_upload():
    """Upload custom music file"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    f = request.files["file"]
    ext = os.path.splitext(f.filename)[1].lower()
    
    if ext not in ['.mp3', '.wav', '.m4a', '.ogg']:
        return jsonify({"error": "Invalid audio format. Use MP3, WAV, M4A, or OGG"}), 400
    
    filename = f"custom_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(MUSIC_CACHE, filename)
    os.makedirs(MUSIC_CACHE, exist_ok=True)
    
    try:
        f.save(filepath)
        print(f"[OK] Custom music uploaded: {filepath}")
        return jsonify({"success": True, "path": filepath, "filename": filename})
    except Exception as e:
        print(f"[ERROR] Music upload failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/generate_images", methods=["POST", "OPTIONS"])
def api_generate_images():
    """Generate AI images for all scenes"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json(force=True)
    scenes = data.get("scenes", []) or []
    out = []

    for s in scenes:
        scene_id = s.get("id", "scene")
        filename = f"{scene_id}.png"
        path = os.path.join(UPLOADS, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        image_prompt = s.get("image_prompt", "").strip()
        if not image_prompt:
            image_prompt = s.get("text", "").strip()
        
        try:
            print(f"[INFO] Generating image for scene {scene_id}")
            result_path = ai_generate_image(image_prompt, path)
            out.append({
                "id": scene_id,
                "background_path": result_path,
                "filename": filename,
                "url": f"/api/uploads/{filename}",
                "success": True,
                "prompt_used": image_prompt[:50]
            })
        except Exception as e:
            print(f"[ERROR] Failed to generate image for scene {scene_id}: {e}")
            out.append({
                "id": scene_id,
                "background_path": "",
                "success": False,
                "error": str(e)
            })

    return jsonify({"images": out})

@app.route("/api/video/<filename>", methods=["GET", "OPTIONS"])
def serve_video(filename):
    """Serve video files with range request support"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        video_path = os.path.join(OUTPUTS, filename)
        video_path = os.path.abspath(video_path)
        outputs_abs = os.path.abspath(OUTPUTS)
        
        if not video_path.startswith(outputs_abs):
            return jsonify({"error": "invalid path"}), 400
            
        if not os.path.exists(video_path):
            return jsonify({"error": "file not found"}), 404
        
        file_size = os.path.getsize(video_path)
        range_header = request.headers.get('Range')
        
        if not range_header:
            is_download = request.args.get('download') == 'true'
            
            def generate():
                with open(video_path, 'rb') as f:
                    data = f.read(8192)
                    while data:
                        yield data
                        data = f.read(8192)
            
            headers = {
                'Content-Type': 'video/mp4',
                'Content-Length': str(file_size),
                'Accept-Ranges': 'bytes'
            }
            
            if is_download:
                headers["Content-Disposition"] = f"attachment; filename={filename}"
            else:
                headers["Content-Disposition"] = f"inline; filename={filename}"
            
            return app.response_class(generate(), headers=headers)
        
        byte_range = range_header.replace('bytes=', '').split('-')
        start = int(byte_range[0]) if byte_range[0] else 0
        end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
        
        if start >= file_size or end >= file_size or start > end:
            return jsonify({"error": "Invalid range"}), 416
        
        length = end - start + 1
        
        def generate_range():
            with open(video_path, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
        
        headers = {
            'Content-Type': 'video/mp4',
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
            'Content-Disposition': f'inline; filename={filename}'
        }
        
        return app.response_class(generate_range(), status=206, headers=headers)
        
    except Exception as e:
        print(f"[ERROR] Video serving failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/render", methods=["POST", "OPTIONS"])
def api_render():
    """Render video"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json(force=True)
    project = data.get("project_name", "video_project")
    scenes = data.get("scenes", []) or []
    auto_ai = bool(data.get("auto_ai_images", True))
    subtitles = bool(data.get("subtitles", False))
    subtitle_style = data.get("subtitle_style", "bottom")
    font_size = int(data.get("font_size", 48))
    use_elevenlabs = bool(data.get("use_elevenlabs", False))
    background_music = data.get("background_music", None)
    music_volume = float(data.get("music_volume", 0.1))

    print(f"[INFO] Render request: project='{project}', scenes={len(scenes)}")

    try:
        path = render_video(
            project_name=project,
            scenes=scenes,
            auto_ai=auto_ai,
            size=(1280, 720),
            fps=25,
            subtitles=subtitles,
            subtitle_style=subtitle_style,
            font_size=font_size,
            use_elevenlabs=use_elevenlabs,
            background_music=background_music,
            music_volume=music_volume
        )
        print(f"[OK] Video rendered: {path}")
        
        filename = os.path.basename(path)
        return jsonify({
            "video_path": path,
            "filename": filename,
            "download_url": f"/api/video/{filename}"
        })
    except Exception as e:
        print(f"[ERROR] Rendering failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/download", methods=["GET", "OPTIONS"])
def api_download():
    """Download rendered video"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "path required"}), 400

    path = os.path.normpath(path)
    path = os.path.abspath(path)
    outputs_abs = os.path.abspath(OUTPUTS)
    
    if not path.startswith(outputs_abs):
        return jsonify({"error": "invalid path"}), 400

    if not os.path.exists(path):
        return jsonify({"error": "file not found"}), 404

    try:
        filename = os.path.basename(path)
        
        def generate():
            with open(path, 'rb') as f:
                while True:
                    data = f.read(4096)
                    if not data:
                        break
                    yield data
        
        return app.response_class(
            generate(),
            mimetype="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "video/mp4"
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/")
def root():
    return jsonify({
        "ok": True, 
        "service": "ai-text-to-video-backend",
        "cloudflare": client.get("available", False),
        "cors": "enabled"
    })

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎬 AI Text-to-Video API Server")
    print("="*60)
    print(f"🌐 CORS: ENABLED (All origins)")
    print(f"🖼️  Cloudflare: {'✅' if client.get('available', False) else '❌'}")
    print(f"📸 Pexels: {'✅' if os.getenv('PEXELS_API_KEY') else '❌'}")
    print("="*60 + "\n")
    
    app.run(host="0.0.0.0", port=5001, debug=True)
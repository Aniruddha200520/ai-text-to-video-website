#!/usr/bin/env python3
import os, uuid, re, hashlib, requests, time, json
from typing import List, Tuple, Optional, Dict
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from gtts import gTTS
from moviepy.editor import (
    ImageClip,
    VideoFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    AudioFileClip,
    ColorClip
)
from dotenv import load_dotenv
from io import BytesIO

# ---------- Paths ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE_DIR, "uploads")
OUTPUTS = os.path.join(BASE_DIR, "outputs")
GEN_IMG = os.path.join(BASE_DIR, "generated_images")
GEN_AUD = os.path.join(BASE_DIR, "generated_audio")
MUSIC_CACHE = os.path.join(BASE_DIR, "music_cache")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
VOICES_CACHE_FILE = os.path.join(CACHE_DIR, "elevenlabs_voices.json")

for p in (UPLOADS, OUTPUTS, GEN_IMG, GEN_AUD, MUSIC_CACHE, TEMP_DIR, CACHE_DIR):
    os.makedirs(p, exist_ok=True)

# ---------- Environment Setup ----------
load_dotenv()

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
CLOUDFLARE_WORKER_URL = os.getenv('CLOUDFLARE_WORKER_URL')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')

# ---------- Groq AI Setup ----------
groq_client = None
groq_available = False

if GROQ_API_KEY and GROQ_API_KEY != 'your_groq_key_here':
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        groq_available = True
        print("[✅] Groq AI configured")
    except ImportError:
        print("[❌] Groq not installed. Run: pip install groq")
    except Exception as e:
        print(f"[❌] Groq setup failed: {e}")
else:
    print("[❌] Groq API key not found")

# ---------- ElevenLabs Setup ----------
elevenlabs_available = False
if ELEVENLABS_API_KEY and ELEVENLABS_API_KEY != 'your_elevenlabs_key_here':
    try:
        from elevenlabs import generate, voices, set_api_key
        set_api_key(ELEVENLABS_API_KEY)
        elevenlabs_available = True
        print("[✅] ElevenLabs API configured")
    except ImportError:
        print("[⚠️] ElevenLabs not installed")
    except Exception as e:
        print(f"[⚠️] ElevenLabs setup failed: {e}")
else:
    print("[ℹ️] ElevenLabs not configured")

# ---------- Cloudflare Workers AI Configuration ----------
def test_cloudflare_worker():
    if not CLOUDFLARE_WORKER_URL or CLOUDFLARE_WORKER_URL == 'https://your-worker.your-subdomain.workers.dev':
        return False
    try:
        print(f"[INFO] Testing Cloudflare Worker: {CLOUDFLARE_WORKER_URL}")
        response = requests.get(CLOUDFLARE_WORKER_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"[✅] Worker Online: {data.get('model', 'Unknown model')}")
            return True
        else:
            print(f"[❌] Worker returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"[❌] Worker test failed: {e}")
        return False

client_available = test_cloudflare_worker()
client = {"available": client_available, "url": CLOUDFLARE_WORKER_URL}

if client_available:
    print("[✅] Cloudflare Workers AI ready (Flux Model)")
else:
    print("[⚠️] Cloudflare Workers AI not configured - Check your .env file!")
    print("[⚠️] Make sure CLOUDFLARE_WORKER_URL is set correctly")

# ---------- IMPROVED PROMPT SYSTEM FOR FLUX ----------
def create_flux_prompt(user_prompt: str) -> dict:
    """
    Flux-optimized prompts - simpler is better for Flux
    Flux understands natural language very well
    """
    
    user_prompt = user_prompt.strip()
    
    # For Flux, keep it simple and natural
    # Flux is smart enough to understand without heavy modification
    positive = f"professional photograph of {user_prompt}, high quality, detailed, realistic"
    negative = "blurry, low quality, distorted, ugly, deformed, watermark"
    
    print(f"[FLUX] Generating: '{user_prompt[:50]}...'")
    
    return {
        "positive": positive,
        "negative": negative,
        "guidance": 7.5,  # Good for Flux-1-Dev
        "steps": 25       # Quality mode
    }

# ---------- Groq Script Generation ----------
def generate_script_openai(topic: str, style: str = "educational", duration: int = 60) -> str:
    if not groq_available:
        raise Exception("Groq API not configured!")
    
    target_words = int((duration / 60) * 150)
    
    style_prompts = {
        "educational": "Create an informative and engaging educational script about",
        "narrative": "Write a compelling storytelling script about", 
        "promotional": "Create an exciting promotional script about",
        "documentary": "Write a documentary-style script exploring",
        "tutorial": "Create a step-by-step tutorial script about"
    }
    
    prompt = f"""{style_prompts.get(style, style_prompts['educational'])} {topic}.

Requirements:
- Target length: approximately {target_words} words
- Duration: {duration} seconds
- Style: {style}
- Make it engaging and suitable for video narration
- Use clear, conversational language

Topic: {topic}

Script:"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a professional scriptwriter."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=target_words + 100,
            temperature=0.7
        )
        
        script = response.choices[0].message.content.strip()
        print(f"[OK] Script generated: {len(script.split())} words")
        return script
        
    except Exception as e:
        raise Exception(f"Groq AI error: {str(e)}")

# ---------- ElevenLabs Voice Integration with Disk Caching ----------
_cached_voices = None

def get_available_voices() -> List[Dict]:
    """Get ElevenLabs voices with disk caching"""
    global _cached_voices
    
    if not elevenlabs_available:
        return []
    
    if _cached_voices is not None:
        print(f"[OK] Using {len(_cached_voices)} voices from memory cache")
        return _cached_voices
    
    if os.path.exists(VOICES_CACHE_FILE):
        try:
            with open(VOICES_CACHE_FILE, 'r', encoding='utf-8') as f:
                _cached_voices = json.load(f)
            print(f"[OK] Loaded {len(_cached_voices)} voices from disk cache")
            return _cached_voices
        except Exception as e:
            print(f"[WARNING] Failed to load voice cache: {e}")
    
    try:
        from elevenlabs import voices as get_voices
        print("[INFO] Fetching voices from ElevenLabs API...")
        voice_list = get_voices()
        
        _cached_voices = [
            {
                "voice_id": voice.voice_id,
                "name": voice.name,
                "category": voice.category if hasattr(voice, 'category') else 'unknown',
                "description": voice.description if hasattr(voice, 'description') else ''
            }
            for voice in voice_list
        ]
        
        try:
            with open(VOICES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(_cached_voices, f, indent=2)
            print(f"[OK] Cached {len(_cached_voices)} voices to disk")
        except Exception as e:
            print(f"[WARNING] Failed to save voice cache: {e}")
        
        return _cached_voices
        
    except Exception as e:
        print(f"[ERROR] Failed to get voices: {e}")
        return []

def tts_elevenlabs(text: str, out_path: str, voice_id: str = None) -> str:
    if not elevenlabs_available:
        raise Exception("ElevenLabs API not configured")
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    try:
        from elevenlabs import generate
        
        if not voice_id:
            voice_id = "21m00Tcm4TlvDq8ikWAM"
            print(f"[INFO] Using default ElevenLabs voice")
        
        print(f"[INFO] Generating audio with ElevenLabs...")
        audio = generate(text=text, voice=voice_id, model="eleven_turbo_v2")
        
        with open(out_path, 'wb') as f:
            f.write(audio)
        
        print(f"[OK] ElevenLabs audio generated")
        return out_path
        
    except Exception as e:
        raise Exception(f"ElevenLabs TTS failed: {str(e)}")

# ---------- Text splitting ----------
def split_text_into_scenes(text: str, words_per_scene: int = 30) -> List[str]:
    text = text.strip()
    if not text:
        return []
    
    scenes = [sentence.strip() + '.' for sentence in text.split('.') if sentence.strip()]
    return scenes

# ---------- TTS with fallback ----------
def tts_generate(text: str, out_path: str, voice_id: str = None, use_elevenlabs: bool = False) -> str:
    if use_elevenlabs and elevenlabs_available:
        try:
            return tts_elevenlabs(text, out_path, voice_id)
        except Exception as e:
            print(f"[WARNING] ElevenLabs failed, using GTTS: {e}")
    
    return tts_gtts(text, out_path)

def tts_gtts(text: str, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tts = gTTS(text=text or " ", lang='en', slow=False)
    tts.save(out_path)
    return out_path

# ---------- Enhanced subtitle system ----------
def create_subtitle_image(
    text: str, 
    size: Tuple[int, int], 
    font_path: Optional[str] = None,
    fontsize: int = 24,
    padding: int = 25,
    position: str = "bottom",
    background_opacity: int = 180,
    text_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    background_color: Tuple[int, int, int, int] = (0, 0, 0, 180)
) -> str:
    w, h = size
    
    try:
        if font_path and os.path.exists(font_path):
            font = ImageFont.truetype(font_path, fontsize)
        else:
            for font_name in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]:
                try:
                    font = ImageFont.truetype(font_name, fontsize)
                    break
                except:
                    continue
            else:
                font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    max_w = int(w * 0.85)
    words = text.split()
    lines, cur = [], []
    img_dummy = Image.new("RGBA", (w, h))
    draw_dummy = ImageDraw.Draw(img_dummy)

    for word in words:
        test = " ".join(cur + [word])
        bbox = draw_dummy.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))

    line_height = fontsize + 10
    text_h = len(lines) * line_height
    total_h = text_h + padding * 2

    img = Image.new("RGBA", (w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    box_padding = 35
    box_x0 = box_padding
    box_x1 = w - box_padding
    box_y0 = 0
    box_y1 = total_h
    
    bg_color = background_color[:3] + (background_opacity,)
    draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=bg_color)
    
    border_color = (255, 255, 255, 90)
    draw.rectangle([box_x0, box_y0, box_x1, box_y1], outline=border_color, width=2)

    y = padding
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        
        shadow_offset = 3
        draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=(0, 0, 0, 150))
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height

    out = os.path.join(UPLOADS, f"subtitle_{uuid.uuid4().hex}.png")
    img.save(out, 'PNG', optimize=False)
    return out

# ---------- Improved overlay fallback ----------
def overlay_image_from_text(text: str, out_path: str, size=(1280, 720)) -> str:
    w, h = size
    img = Image.new("RGB", size)
    pixels = img.load()
    
    for y in range(h):
        ratio = y / h
        r = int(25 + (45 - 25) * ratio)
        g = int(25 + (35 - 25) * ratio)
        b = int(45 + (65 - 45) * ratio)
        for x in range(w):
            pixels[x, y] = (r, g, b)
    
    draw = ImageDraw.Draw(img)

    font_size = int(h * 0.065)
    try:
        for font_path in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    words = text.split()
    lines, cur = [], []
    max_w = int(w * 0.85)

    for word in words:
        test = " ".join(cur + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))

    line_height = int(font_size * 1.4)
    total_text_height = len(lines) * line_height
    y_start = (h - total_text_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        y = y_start + (i * line_height)
        
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    img.save(out_path, 'PNG', optimize=False)
    return out_path

# ---------- FLUX AI IMAGE GENERATION ----------
def ai_generate_image(prompt: str, out_path: str, size=(1280, 720), max_retries: int = 3, auto_improve: bool = True) -> str:
    """
    Generate images using Cloudflare Flux model
    """
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    original_prompt = prompt.strip()
    
    if not original_prompt:
        print("[WARNING] Empty prompt, using text overlay")
        return overlay_image_from_text("Generated Scene", out_path, size=size)
    
    # Create Flux-optimized prompt
    prompt_data = create_flux_prompt(original_prompt)
    
    positive_prompt = prompt_data['positive']
    negative_prompt = prompt_data['negative']
    guidance = prompt_data['guidance']
    steps = prompt_data['steps']
    
    if client["available"] and CLOUDFLARE_WORKER_URL:
        for attempt in range(max_retries):
            try:
                seed = (int(time.time()) + attempt * 1000) % 10000
                
                payload = {
                    "prompt": positive_prompt,
                    "negative_prompt": negative_prompt,
                    "guidance": guidance,
                    "num_steps": steps,
                    "seed": seed
                }
                
                response = requests.post(
                    CLOUDFLARE_WORKER_URL,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "AI-Text-to-Video-Flux/1.0"
                    },
                    timeout=120
                )
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    # Check if it's an error JSON response
                    if 'application/json' in content_type:
                        error_data = response.json()
                        print(f"[ERROR] Worker returned error: {error_data}")
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            time.sleep(wait_time)
                            continue
                    
                    # It's an image
                    if content_type.startswith('image/') or len(response.content) > 1000:
                        try:
                            image = Image.open(BytesIO(response.content))
                            
                            # Convert modes
                            if image.mode in ('RGBA', 'LA', 'P'):
                                background = Image.new('RGB', image.size, (0, 0, 0))
                                if image.mode == 'P':
                                    image = image.convert('RGBA')
                                if image.mode in ('RGBA', 'LA'):
                                    background.paste(image, mask=image.split()[-1])
                                    image = background
                            
                            # Resize with highest quality
                            if image.size != size:
                                image = image.resize(size, Image.Resampling.LANCZOS)
                            
                            # Enhance
                            enhancer = ImageEnhance.Sharpness(image)
                            image = enhancer.enhance(1.15)
                            
                            enhancer = ImageEnhance.Contrast(image)
                            image = enhancer.enhance(1.08)
                            
                            # Save
                            image.save(out_path, 'PNG', optimize=False, compress_level=3)
                            
                            print(f"[SUCCESS] Image saved: {os.path.basename(out_path)}")
                            return out_path
                            
                        except Exception as e:
                            print(f"[ERROR] Image processing failed: {e}")
                else:
                    print(f"[WARNING] HTTP {response.status_code}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    
            except Exception as e:
                print(f"[ERROR] Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

    print(f"[FALLBACK] Using text overlay")
    return overlay_image_from_text(original_prompt, out_path, size=size)

# ---------- Test AI generation ----------
def test_ai_generation():
    if not client["available"]:
        return False
    
    try:
        test_prompt = "modern college building"
        test_path = os.path.join(GEN_IMG, "test_generation.png")
        result_path = ai_generate_image(test_prompt, test_path, auto_improve=True)
        
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            img = Image.open(result_path)
            if img.size == (1280, 720) and file_size > 10000:
                print(f"[TEST SUCCESS] Generated test image: {file_size} bytes")
                return True
        return False
            
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

# ---------- Background clip with quality optimization ----------
def background_clip(path: Optional[str], duration: float, size=(1280, 720)):
    if path and os.path.exists(path):
        path = os.path.abspath(path)
        ext = os.path.splitext(path)[1].lower()
        
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(path)
                
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = PILImage.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        background.paste(img, mask=img.split()[-1])
                        img = background
                
                if img.size != size:
                    if img.size[0] > size[0] * 1.2 or img.size[1] > size[1] * 1.2:
                        img = img.resize(size, PILImage.Resampling.LANCZOS)
                    else:
                        img = img.resize(size, PILImage.Resampling.LANCZOS)
                
                if img.size != size:
                    enhancer = ImageEnhance.Sharpness(img)
                    img = enhancer.enhance(1.12)
                
                temp_path = path.replace(ext, '_optimized.png')
                img.save(temp_path, 'PNG', optimize=False, compress_level=1)
                
                clip = ImageClip(temp_path, duration=duration)
                return clip
                
            except Exception as e:
                print(f"[ERROR] Image load failed: {e}")
                
        if ext in [".mp4", ".mov", ".avi", ".mkv"]:
            try:
                v = VideoFileClip(path)
                if v.duration < duration and v.duration > 0.1:
                    loops = int(duration // v.duration) + 1
                    v = concatenate_videoclips([v] * loops, method="compose")
                return v.subclip(0, duration).resize(size)
            except Exception as e:
                print(f"[ERROR] Video load failed: {e}")
                
    return ColorClip(size=size, color=(20, 20, 30), duration=duration)

# ---------- Render pipeline ----------
def render_video(
    project_name: str,
    scenes: List[dict],
    auto_ai: bool = True,
    size=(1280, 720),
    fps: int = 25,
    subtitles: bool = False,
    subtitle_style: str = "bottom",
    font_size: int = 24,
    use_elevenlabs: bool = False,
    background_music: Optional[str] = None,
    music_volume: float = 0.1
) -> str:
    print(f"[INFO] Rendering: {size[0]}x{size[1]} @ {fps}fps")
    print(f"[INFO] Project: {project_name}, Scenes: {len(scenes)}")
    
    clips = []
    for i, s in enumerate(scenes):
        print(f"[INFO] Processing scene {i+1}/{len(scenes)}")
        
        text = (s.get("text") or "").strip()
        bg = (s.get("background_path") or "").strip() or None
        duration = float(s.get("duration") or 5.0)
        voice_id = s.get("voice_id", "") or None
        audio = None

        if text:
            aud_path = os.path.join(GEN_AUD, f"{s.get('id','scene')}_{uuid.uuid4().hex[:6]}.mp3")
            try:
                tts_generate(text, aud_path, voice_id=voice_id, use_elevenlabs=use_elevenlabs)
                audio = AudioFileClip(aud_path)
            except Exception as e:
                print(f"[ERROR] TTS failed: {e}")
                if use_elevenlabs:
                    try:
                        tts_gtts(text, aud_path)
                        audio = AudioFileClip(aud_path)
                    except:
                        audio = None

        if audio:
            try:
                audio_dur = max(0.1, audio.duration)
                if audio_dur > duration:
                    duration = audio_dur + 0.5
            except:
                pass

        if not bg and auto_ai:
            img_path = os.path.join(GEN_IMG, f"{s.get('id','scene')}_{uuid.uuid4().hex[:6]}.png")
            
            image_prompt = s.get("image_prompt", "").strip()
            if not image_prompt:
                image_prompt = text
            
            if image_prompt:
                try:
                    ai_generate_image(image_prompt, img_path, size=size, auto_improve=True)
                    bg = img_path
                except Exception as e:
                    print(f"[ERROR] Image generation failed: {e}")

        try:
            bg_clip = background_clip(bg, duration, size=size)
        except Exception as e:
            print(f"[ERROR] Background failed: {e}")
            raise e

        if audio:
            try:
                bg_clip = bg_clip.set_audio(audio)
            except Exception as e:
                print(f"[ERROR] Audio add failed: {e}")

        if subtitles and text:
            try:
                sub_img = create_subtitle_image(
                    text, 
                    size=size, 
                    fontsize=font_size,
                    padding=25,
                    position=subtitle_style,
                    background_opacity=180
                )
                
                if subtitle_style == "top":
                    position = ("center", 50)
                elif subtitle_style == "center":
                    position = ("center", "center")
                else:
                    position = ("center", size[1] - 140)
                
                sub_clip = ImageClip(sub_img).set_duration(duration).set_position(position)
                comp = CompositeVideoClip([bg_clip, sub_clip])
                if audio:
                    comp = comp.set_audio(audio)
                clips.append(comp)
            except Exception as e:
                print(f"[ERROR] Subtitle failed: {e}")
                clips.append(bg_clip)
        else:
            clips.append(bg_clip)

    if not clips:
        raise ValueError("No valid clips")

    print(f"[INFO] Concatenating {len(clips)} clips...")
    try:
        final = concatenate_videoclips(clips, method="compose")
    except Exception as e:
        print(f"[ERROR] Concatenation failed: {e}")
        raise e

    if background_music and os.path.exists(background_music):
        try:
            print(f"[INFO] Adding background music")
            music = AudioFileClip(background_music)
            
            video_duration = final.duration
            if music.duration < video_duration:
                loops_needed = int(video_duration / music.duration) + 1
                from moviepy.audio.AudioClip import concatenate_audioclips
                music = concatenate_audioclips([music] * loops_needed)
            
            music = music.subclip(0, video_duration)
            music = music.volumex(music_volume)
            
            if final.audio:
                from moviepy.audio.AudioClip import CompositeAudioClip
                final_audio = CompositeAudioClip([final.audio, music])
                final = final.set_audio(final_audio)
            else:
                final = final.set_audio(music)
        except Exception as e:
            print(f"[WARNING] Music failed: {e}")

    out_path = os.path.join(OUTPUTS, f"{project_name}_{uuid.uuid4().hex[:8]}.mp4")
    temp_audio = os.path.join(TEMP_DIR, f'temp-audio-{uuid.uuid4().hex[:8]}.m4a')
    
    try:
        print(f"[INFO] Encoding video...")
        final.write_videofile(
            out_path, 
            fps=fps, 
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            bitrate="3500k",
            audio_bitrate="192k",
            ffmpeg_params=[
                "-crf", "20",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p"
            ],
            temp_audiofile=temp_audio,
            remove_temp=False,
            verbose=False,
            logger=None,
            threads=4
        )
        print(f"[SUCCESS] Video rendered: {os.path.basename(out_path)}")
        
        try:
            if os.path.exists(temp_audio):
                time.sleep(0.1)
                os.remove(temp_audio)
        except:
            pass
            
    except Exception as e:
        print(f"[ERROR] Encoding failed: {e}")
        try:
            if os.path.exists(temp_audio):
                time.sleep(0.1)
                os.remove(temp_audio)
        except:
            pass
        raise e

    try:
        final.close()
    except:
        pass
    for c in clips:
        try:
            c.close()
        except:
            pass

    return out_path

if __name__ == "__main__":
    print("="*70)
    print("🎬 AI Text-to-Video Utils - FLUX MODEL")
    print("="*70)
    print(f"📐 Resolution: 1280x720 HD")
    print(f"🎨 Quality: LANCZOS + Sharpening")
    print(f"🤖 AI Model: Flux-1-Schnell (High Quality)")
    print(f"✨ Mode: Natural language prompts")
    print(f"💾 Voice Cache: {VOICES_CACHE_FILE}")
    print(f"🚀 Groq: {'✅' if groq_available else '❌'} (Script generation)")
    print(f"🎙️  ElevenLabs: {'✅' if elevenlabs_available else '❌'}")
    print(f"🖼️  Cloudflare: {'✅' if client['available'] else '❌'}")
    print("="*70)
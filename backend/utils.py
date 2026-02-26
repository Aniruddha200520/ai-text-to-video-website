#!/usr/bin/env python3
"""
utils.py v9
BACKGROUND REMOVAL: PNG alpha channel only.
Prepare presenter photo using remove.bg or onlinepngtools.com
Save as presenter_photo.png in assets/avatars/
"""
import os, uuid, requests, time, json, subprocess, shutil, hashlib
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from gtts import gTTS
from moviepy.editor import (
    ImageClip, VideoFileClip, CompositeVideoClip,
    concatenate_videoclips, AudioFileClip, ColorClip, VideoClip
)
from dotenv import load_dotenv
from io import BytesIO
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

REMBG_AVAILABLE = False
REMBG_SESSION   = None

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
UPLOADS         = os.path.join(BASE_DIR, "uploads")
OUTPUTS         = os.path.join(BASE_DIR, "outputs")
GEN_IMG         = os.path.join(BASE_DIR, "generated_images")
GEN_AUD         = os.path.join(BASE_DIR, "generated_audio")
MUSIC_CACHE     = os.path.join(BASE_DIR, "music_cache")
TEMP_DIR        = os.path.join(BASE_DIR, "temp")
CACHE_DIR       = os.path.join(BASE_DIR, "cache")
ALPHA_CACHE_DIR = os.path.join(CACHE_DIR, "alpha_masks")
VOICES_CACHE_FILE = os.path.join(CACHE_DIR, "elevenlabs_voices.json")

WAV2LIP_DIR     = r"E:\Projects\Wav2Lip"
WAV2LIP_RUNNER  = os.path.join(WAV2LIP_DIR, "wav2lip_runner.py")
WAV2LIP_CONDA   = "wav2lip"
AVATARS_DIR      = os.path.join(BASE_DIR, "assets", "avatars")
PRESENTER_MALE   = os.path.join(AVATARS_DIR, "presenter_photo.png")
PRESENTER_FEMALE = os.path.join(AVATARS_DIR, "presenter_photo_female.png")

def get_presenter_photo(avatar_style: str = "male") -> str:
    """Return path to the correct presenter PNG based on gender selection."""
    if avatar_style in ("female", "female_business", "female_casual"):
        return PRESENTER_FEMALE
    return PRESENTER_MALE  # default: male

PRESENTER_PHOTO = PRESENTER_MALE  # kept for backwards compat

for _p in (UPLOADS, OUTPUTS, GEN_IMG, GEN_AUD, MUSIC_CACHE,
           TEMP_DIR, CACHE_DIR, ALPHA_CACHE_DIR):
    os.makedirs(_p, exist_ok=True)

load_dotenv()
GROQ_API_KEY          = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY    = os.getenv("ELEVENLABS_API_KEY")
CLOUDFLARE_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL")
PEXELS_API_KEY        = os.getenv("PEXELS_API_KEY")

groq_client = None; groq_available = False
if GROQ_API_KEY and GROQ_API_KEY != "your_groq_key_here":
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        groq_available = True
        print("[OK] Groq AI configured")
    except Exception as e:
        print(f"[ERR] Groq: {e}")
else:
    print("[ERR] Groq API key not found")

elevenlabs_available = False
if ELEVENLABS_API_KEY and ELEVENLABS_API_KEY != "your_elevenlabs_key_here":
    try:
        from elevenlabs import generate, voices, set_api_key
        set_api_key(ELEVENLABS_API_KEY)
        elevenlabs_available = True
        print("[OK] ElevenLabs configured")
    except Exception as e:
        print(f"[WARN] ElevenLabs: {e}")

def test_cloudflare_worker():
    if not CLOUDFLARE_WORKER_URL or "your-worker" in CLOUDFLARE_WORKER_URL:
        return False
    try:
        r = requests.get(CLOUDFLARE_WORKER_URL, timeout=10)
        if r.status_code == 200:
            print(f"[OK] Worker Online: {r.json().get('model','?')}")
            return True
        return False
    except Exception as e:
        print(f"[ERR] Worker: {e}")
        return False

client_available = test_cloudflare_worker()
client = {"available": client_available, "url": CLOUDFLARE_WORKER_URL}
if client_available: print("[OK] Cloudflare Workers AI ready")
else:                 print("[WARN] Cloudflare Workers AI not configured")

def _find_ffmpeg():
    ff = shutil.which("ffmpeg")
    if ff: return ff
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        if ff and os.path.exists(ff): return ff
    except: pass
    for p in [r"C:\ffmpeg\bin\ffmpeg.exe",
              r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if os.path.exists(p): return p
    try:
        from moviepy.config import get_setting
        ff = get_setting("FFMPEG_BINARY")
        if ff and os.path.exists(ff): return ff
    except: pass
    return None

FFMPEG_PATH = _find_ffmpeg()
print(f"[OK] ffmpeg: {FFMPEG_PATH}" if FFMPEG_PATH else "[WARN] ffmpeg not found")


# ============================================================
#  ALPHA MASK — PNG alpha channel only
# ============================================================

def _presenter_cache_key(avatar_style: str = "male"):
    """MD5 of presenter photo file → stable cache key."""
    photo_path = get_presenter_photo(avatar_style)
    if not os.path.exists(photo_path):
        return None
    try:
        with open(photo_path, "rb") as f:
            digest = hashlib.md5(f.read()).hexdigest()[:16]
        return f"{digest}_{avatar_style}"
    except Exception:
        return None


def _load_cached_alpha(cache_key):
    """Load alpha mask from disk cache. Returns float32 array or None."""
    if not cache_key:
        return None
    path = os.path.join(ALPHA_CACHE_DIR, f"alpha_{cache_key}.npy")
    if os.path.exists(path):
        try:
            arr = np.load(path)
            print(f"[OK] Alpha loaded from cache: {os.path.basename(path)}")
            return arr.astype(np.float32)
        except Exception as e:
            print(f"[WARN] Cache load failed: {e}")
    return None


def _save_cached_alpha(cache_key, alpha):
    """Save alpha mask to disk cache."""
    if not cache_key:
        return
    os.makedirs(ALPHA_CACHE_DIR, exist_ok=True)
    path = os.path.join(ALPHA_CACHE_DIR, f"alpha_{cache_key}.npy")
    try:
        np.save(path, alpha.astype(np.float32))
        print(f"[OK] Alpha cached: {os.path.basename(path)}")
    except Exception as e:
        print(f"[WARN] Cache save failed: {e}")


def _load_presenter_alpha(target_w: int, target_h: int, avatar_style: str = "male"):
    """
    Extract alpha directly from transparent presenter PNG.
    Use remove.bg / onlinepngtools to prepare the PNG before use.
    Returns float32 alpha [0..1] or None if no alpha channel found.
    """
    photo_path = get_presenter_photo(avatar_style)
    if not os.path.exists(photo_path):
        print(f"[ERR] Presenter photo not found: {photo_path}")
        return None
    try:
        img = cv2.imread(photo_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            print("[ERR] Could not read presenter photo")
            return None
        if img.ndim < 3 or img.shape[2] < 4:
            print("[WARN] Presenter photo has no alpha channel — use a transparent PNG")
            return None
        alpha = img[:, :, 3].astype(np.float32) / 255.0
        # Light feather for smooth compositing edges
        a_u8    = (alpha * 255).astype(np.uint8)
        a_u8    = cv2.GaussianBlur(a_u8, (3, 3), 0)
        resized = cv2.resize(a_u8, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        coverage = resized.mean() / 255 * 100
        print(f"    [PNG alpha] fg={coverage:.1f}%", end=" ", flush=True)
        return resized.astype(np.float32) / 255.0
    except Exception as e:
        print(f"[ERR] PNG alpha load failed: {e}")
        return None


def build_static_alpha(frames_bgr: list, cache_key: str = None,
                       feather: int = 2, avatar_style: str = "male") -> np.ndarray:
    """
    Build alpha mask for avatar compositing.
    Uses PNG alpha channel from presenter_photo.png (cached to disk).
    """
    h0, w0 = frames_bgr[0].shape[:2]

    # ── cache hit ────────────────────────────────────────────────────
    if cache_key:
        cached = _load_cached_alpha(cache_key)
        if cached is not None:
            if cached.shape == (h0, w0):
                return cached
            print("[WARN] Cached alpha shape mismatch — recomputing")

    # ── PNG alpha (primary and only method) ──────────────────────────
    print(f"[INFO] Loading alpha from presenter PNG …")
    alpha = _load_presenter_alpha(w0, h0, avatar_style=avatar_style)

    if alpha is None:
        # Fallback: fully opaque (shows whole frame including background)
        print("[WARN] No PNG alpha found — using fully opaque mask")
        alpha = np.ones((h0, w0), dtype=np.float32)

    print(f"\n[OK] Alpha ready — fg={alpha.mean()*100:.1f}%")

    if cache_key:
        _save_cached_alpha(cache_key, alpha)

    return alpha


# ============================================================
#  WAV2LIP
# ============================================================
AVATAR_SIZE_H = {"small": 260, "medium": 360, "large": 460}

def run_wav2lip(audio_path: str, output_path: str, avatar_style: str = "male") -> bool:
    photo_path = get_presenter_photo(avatar_style)
    if not os.path.exists(photo_path):
        print(f"[ERR] Presenter photo not found: {photo_path}"); return False
    if not os.path.exists(WAV2LIP_RUNNER):
        print(f"[ERR] wav2lip_runner.py not found: {WAV2LIP_RUNNER}"); return False
    py = rf"C:\Users\aniru\anaconda3\envs\{WAV2LIP_CONDA}\python.exe"
    if not os.path.exists(py):
        print(f"[ERR] Wav2Lip python not found: {py}"); return False
    cmd = [py, WAV2LIP_RUNNER,
           "--face",   photo_path,
           "--audio",  audio_path,
           "--output", output_path]
    print("[INFO] Running Wav2Lip …")
    try:
        res = subprocess.run(cmd, timeout=300, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(output_path):
            mb = os.path.getsize(output_path) / 1024 / 1024
            print(f"[OK] Wav2Lip → {output_path} ({mb:.1f} MB)")
            return True
        print(f"[ERR] Wav2Lip failed (rc={res.returncode})")
        if res.stderr: print(res.stderr[-400:])
        return False
    except subprocess.TimeoutExpired:
        print("[ERR] Wav2Lip timed out"); return False
    except Exception as e:
        print(f"[ERR] Wav2Lip: {e}"); return False


# ============================================================
#  AVATAR COMPOSITE
# ============================================================

def composite_avatar_on_video(video_clip, wav2lip_path: str,
                               position_name: str = "bottom-right",
                               size_name: str = "medium",
                               avatar_style: str = "male"):
    try:
        vw, vh    = video_clip.size
        vfps      = float(video_clip.fps or 25)
        base_key  = _presenter_cache_key(avatar_style=avatar_style)

        # ── read Wav2Lip frames ───────────────────────────────────────
        cap   = cv2.VideoCapture(wav2lip_path)
        sfps  = cap.get(cv2.CAP_PROP_FPS) or 25
        sw    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        sh    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        bgrs, rgbs = [], []
        while True:
            ok, frm = cap.read()
            if not ok: break
            bgrs.append(frm)
            rgbs.append(cv2.cvtColor(frm, cv2.COLOR_BGR2RGB))
        cap.release()

        if not bgrs:
            print("[ERR] No frames from Wav2Lip"); return video_clip
        print(f"[INFO] Wav2Lip: {len(bgrs)} frames  {sw}×{sh}")

        sized_key = f"{base_key}_{sw}x{sh}" if base_key else None
        alpha     = build_static_alpha(bgrs, cache_key=sized_key, feather=2, avatar_style=avatar_style)

        # ── display geometry ──────────────────────────────────────────
        ah = AVATAR_SIZE_H.get(size_name, 280)
        aw = max(80, int(ah * sw / sh))

        ay = vh - ah
        if   position_name == "bottom-right": ax = vw - aw
        elif position_name == "bottom-left":  ax = 0
        elif position_name == "top-right":    ax = vw - aw; ay = 0
        elif position_name == "top-left":     ax = 0;       ay = 0
        else:                                 ax = vw - aw
        ax = max(0, min(ax, vw - aw))
        ay = max(0, min(ay, vh - ah))
        print(f"[INFO] Avatar {aw}×{ah} at ({ax},{ay})")

        a_disp = cv2.resize(alpha, (aw, ah), interpolation=cv2.INTER_LINEAR)
        a3     = np.stack([a_disp] * 3, axis=2)

        av_f = [cv2.resize(f, (aw, ah), interpolation=cv2.INTER_LINEAR).astype(np.float32)
                for f in rgbs]
        print(f"[OK] {len(av_f)} avatar frames ready")

        # ── composite every video frame ───────────────────────────────
        total = int(video_clip.duration * vfps) + 1
        out   = []
        y1, y2 = ay, ay + ah
        x1, x2 = ax, ax + aw
        y2c, x2c = min(y2, vh), min(x2, vw)
        ph, pw   = y2c - y1, x2c - x1

        for i in range(total):
            t   = i / vfps
            ai  = min(int(i * sfps / vfps), len(av_f) - 1)
            bg  = video_clip.get_frame(t).astype(np.float32)
            bg[y1:y2c, x1:x2c] = (
                av_f[ai][:ph, :pw] * a3[:ph, :pw] +
                bg[y1:y2c, x1:x2c] * (1.0 - a3[:ph, :pw])
            )
            out.append(bg.astype(np.uint8))

        print(f"[OK] Composited {len(out)} frames")

        def make_frame(t):
            return out[min(int(t * vfps), len(out) - 1)]

        result = VideoClip(make_frame, duration=video_clip.duration)
        return result.set_fps(vfps).set_audio(video_clip.audio)

    except Exception as e:
        print(f"[ERR] Composite failed: {e}")
        import traceback; traceback.print_exc()
        return video_clip


def create_avatar_overlay(video_clip, audio_clip, avatar_config: dict):
    pos   = avatar_config.get("position", "bottom-right")
    size  = avatar_config.get("size",     "medium")
    style = avatar_config.get("style",    "business")
    print(f"\n[INFO] Avatar: style={style} | size={size} | pos={pos}")

    t_wav = os.path.join(TEMP_DIR, f"_av_{uuid.uuid4().hex[:8]}.wav")
    t_out = os.path.join(TEMP_DIR, f"_wav2lip_{uuid.uuid4().hex[:8]}.mp4")

    try:
        ff  = FFMPEG_PATH or shutil.which("ffmpeg") or "ffmpeg"
        ac  = audio_clip
        if not getattr(ac, "fps", None): ac = ac.set_fps(44100)
        mp3 = t_wav.replace(".wav", ".mp3")
        ac.write_audiofile(mp3, logger=None, verbose=False)
        res = subprocess.run(
            [ff, "-y", "-i", mp3, "-ac", "1", "-ar", "16000", t_wav],
            capture_output=True)
        if res.returncode == 0 and os.path.exists(t_wav) and os.path.getsize(t_wav) > 0:
            kb  = os.path.getsize(t_wav) // 1024
            dur = os.path.getsize(t_wav) / (16000 * 2)
            print(f"[INFO] Audio ready: {kb} KB (~{dur:.1f}s)")
            try: os.remove(mp3)
            except: pass
        else:
            t_wav = mp3
    except Exception as e:
        print(f"[WARN] Audio write failed: {e}"); t_wav = None

    presenter = get_presenter_photo(style)
    print(f"[DEBUG] t_wav={t_wav}, exists={t_wav and os.path.exists(t_wav)}")
    print(f"[DEBUG] WAV2LIP_RUNNER={WAV2LIP_RUNNER}, exists={os.path.exists(WAV2LIP_RUNNER)}")
    print(f"[DEBUG] PRESENTER_PHOTO={presenter}, exists={os.path.exists(presenter)}")
    if t_wav and os.path.exists(WAV2LIP_RUNNER) and os.path.exists(presenter):
        if run_wav2lip(t_wav, t_out, avatar_style=style):
            result = composite_avatar_on_video(video_clip, t_out, pos, size, avatar_style=style)
            for p in (t_wav, t_out):
                try: os.remove(p)
                except: pass
            print("[OK] Avatar overlay complete!")
            return result
        print("[ERR] Wav2Lip failed")

    print("[WARN] Avatar skipped")
    return video_clip


# ============================================================
#  SUBTITLE
# ============================================================

def create_subtitle_image(text, size, font_path=None, fontsize=32, padding=18,
                           position="bottom", avatar_side="none",
                           avatar_width=0, avatar_margin=25):
    vw, vh = size

    if   avatar_side == "right" and avatar_width > 0:
        zone_x, zone_w = 0, vw - avatar_width - avatar_margin
    elif avatar_side == "left"  and avatar_width > 0:
        zone_x, zone_w = avatar_width + avatar_margin, vw - avatar_width - avatar_margin
    else:
        zone_x, zone_w = 0, vw

    max_tw = max(200, int(zone_w * 0.85))
    font   = ImageFont.load_default()
    for fn in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf",
               r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
               r"C:\Windows\Fonts\calibrib.ttf"]:
        try: font = ImageFont.truetype(fn, fontsize); break
        except: pass

    dummy = ImageDraw.Draw(Image.new("RGBA", (vw, vh)))
    words = text.split(); lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if dummy.textbbox((0, 0), test, font=font)[2] <= max_tw:
            cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    if not lines: lines = [text]

    lh       = fontsize + 10
    canvas_h = len(lines) * lh + 16
    img      = Image.new("RGBA", (vw, canvas_h), (0, 0, 0, 0))
    draw     = ImageDraw.Draw(img)
    stroke   = max(2, fontsize // 13)
    y        = 8

    for line in lines:
        tw = draw.textbbox((0, 0), line, font=font)[2]
        tx = zone_x + (zone_w - tw) // 2
        for dx in range(-stroke, stroke + 1):
            for dy in range(-stroke, stroke + 1):
                if dx or dy:
                    draw.text((tx+dx, y+dy), line, font=font, fill=(0, 0, 0, 230))
        draw.text((tx+1, y+2), line, font=font, fill=(0, 0, 0, 130))
        draw.text((tx,   y),   line, font=font, fill=(255, 255, 255, 255))
        y += lh

    out = os.path.join(UPLOADS, f"subtitle_{uuid.uuid4().hex}.png")
    img.save(out, "PNG", optimize=False)
    return out


# ============================================================
#  IMAGE / SCRIPT / TTS HELPERS
# ============================================================

def create_flux_prompt(user_prompt):
    p = user_prompt.strip()
    return {
        "positive": f"professional photograph of {p}, high quality, detailed, realistic",
        "negative": "blurry, low quality, distorted, ugly, deformed, watermark",
        "guidance": 7.5, "steps": 25,
    }

def generate_script_openai(topic, style="educational", duration=60):
    if not groq_available: raise Exception("Groq not configured")
    tw = int((duration / 60) * 150)
    sm = {
        "educational": "Create an informative educational script about",
        "narrative":   "Write a compelling story script about",
        "promotional": "Create an exciting promotional script about",
        "documentary": "Write a documentary-style script about",
        "tutorial":    "Create a step-by-step tutorial about",
    }
    res = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a professional scriptwriter."},
            {"role": "user",   "content":
             f"{sm.get(style, sm['educational'])} {topic}.\n~{tw} words, {duration}s.\nScript:"},
        ],
        max_tokens=tw + 100, temperature=0.7,
    )
    script = res.choices[0].message.content.strip()
    print(f"[OK] Script: {len(script.split())} words")
    return script

_cached_voices = None
def get_available_voices():
    global _cached_voices
    if not elevenlabs_available: return []
    if _cached_voices is not None: return _cached_voices
    if os.path.exists(VOICES_CACHE_FILE):
        try:
            with open(VOICES_CACHE_FILE) as f:
                _cached_voices = json.load(f); return _cached_voices
        except: pass
    try:
        from elevenlabs import voices as gv
        vl = gv()
        _cached_voices = [
            {"voice_id": v.voice_id, "name": v.name,
             "category": getattr(v, "category", "unknown"),
             "description": getattr(v, "description", "")}
            for v in vl
        ]
        with open(VOICES_CACHE_FILE, "w") as f:
            json.dump(_cached_voices, f, indent=2)
        return _cached_voices
    except Exception as e:
        print(f"[ERR] Voices: {e}"); return []

def tts_elevenlabs(text, out_path, voice_id=None):
    if not elevenlabs_available: raise Exception("ElevenLabs not configured")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    from elevenlabs import generate
    audio = generate(text=text, voice=voice_id or "21m00Tcm4TlvDq8ikWAM",
                     model="eleven_turbo_v2")
    with open(out_path, "wb") as f: f.write(audio)
    return out_path

def split_text_into_scenes(text, words_per_scene=30):
    text = text.strip()
    if not text: return []
    return [s.strip() + "." for s in text.split(".") if s.strip()]

def tts_generate(text, out_path, voice_id=None, use_elevenlabs=False):
    if use_elevenlabs and elevenlabs_available:
        try: return tts_elevenlabs(text, out_path, voice_id)
        except Exception as e: print(f"[WARN] ElevenLabs→gTTS: {e}")
    return tts_gtts(text, out_path)

def tts_gtts(text, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    gTTS(text=text or " ", lang="en", slow=False).save(out_path)
    return out_path

def overlay_image_from_text(text, out_path, size=(1280, 720)):
    w, h = size
    img  = Image.new("RGB", size)
    pix  = img.load()
    for y in range(h):
        r = int(25 + 20*y/h); g = int(25 + 10*y/h); b = int(45 + 20*y/h)
        for x in range(w): pix[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for fn in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
        try: font = ImageFont.truetype(fn, int(h * 0.065)); break
        except: pass
    words = text.split(); lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        if draw.textbbox((0, 0), test, font=font)[2] <= int(w * 0.85):
            cur.append(word)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [word]
    if cur: lines.append(" ".join(cur))
    try:    lh = int(font.size * 1.4)
    except: lh = 30
    ys = (h - len(lines) * lh) // 2
    for i, line in enumerate(lines):
        bx = draw.textbbox((0, 0), line, font=font)
        x  = (w - (bx[2] - bx[0])) // 2
        y  = ys + i * lh
        draw.text((x+3, y+3), line, font=font, fill=(0, 0, 0))
        draw.text((x,   y),   line, font=font, fill=(255, 255, 255))
    img.save(out_path, "PNG", optimize=False)
    return out_path

def ai_generate_image(prompt, out_path, size=(1280, 720), max_retries=3,
                      auto_improve=True):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    original = prompt.strip()
    if not original:
        return overlay_image_from_text("Generated Scene", out_path, size=size)
    pd = create_flux_prompt(original)
    if client["available"] and CLOUDFLARE_WORKER_URL:
        for attempt in range(max_retries):
            try:
                payload = {
                    "prompt":          pd["positive"],
                    "negative_prompt": pd["negative"],
                    "guidance":        pd["guidance"],
                    "num_steps":       pd["steps"],
                    "seed":            (int(time.time()) + attempt * 1000) % 10000,
                }
                r = requests.post(CLOUDFLARE_WORKER_URL, json=payload,
                                  headers={"Content-Type": "application/json"},
                                  timeout=120)
                if r.status_code == 200:
                    ct = r.headers.get("content-type", "").lower()
                    if "application/json" in ct:
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt); continue
                    if ct.startswith("image/") or len(r.content) > 1000:
                        try:
                            img = Image.open(BytesIO(r.content))
                            if img.mode in ("RGBA", "LA", "P"):
                                bg = Image.new("RGB", img.size, (0, 0, 0))
                                if img.mode == "P": img = img.convert("RGBA")
                                if img.mode in ("RGBA", "LA"):
                                    bg.paste(img, mask=img.split()[-1]); img = bg
                            if img.size != size:
                                img = img.resize(size, Image.Resampling.LANCZOS)
                            img = ImageEnhance.Sharpness(img).enhance(1.15)
                            img = ImageEnhance.Contrast(img).enhance(1.08)
                            img.save(out_path, "PNG", optimize=False, compress_level=3)
                            print(f"[OK] {os.path.basename(out_path)}")
                            return out_path
                        except Exception as e:
                            print(f"[ERR] {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[ERR] {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
    return overlay_image_from_text(original, out_path, size=size)

def test_ai_generation():
    if not client["available"]: return False
    try:
        tp = os.path.join(GEN_IMG, "test_generation.png")
        r  = ai_generate_image("modern college building", tp)
        if os.path.exists(r):
            sz = os.path.getsize(r)
            if Image.open(r).size == (1280, 720) and sz > 10000:
                print(f"[TEST OK] {sz} bytes"); return True
        return False
    except Exception as e:
        print(f"[ERR] {e}"); return False

def background_clip(path, duration, size=(1280, 720)):
    if path and os.path.exists(path):
        path = os.path.abspath(path)
        ext  = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"):
            try:
                img = Image.open(path)
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P": img = img.convert("RGBA")
                    if img.mode in ("RGBA", "LA"):
                        bg.paste(img, mask=img.split()[-1]); img = bg
                if img.size != size:
                    img = img.resize(size, Image.Resampling.LANCZOS)
                img = ImageEnhance.Sharpness(img).enhance(1.12)
                tmp = path.replace(ext, "_optimized.png")
                img.save(tmp, "PNG", optimize=False, compress_level=1)
                return ImageClip(tmp, duration=duration)
            except Exception as e:
                print(f"[ERR] Image: {e}")
        if ext in (".mp4", ".mov", ".avi", ".mkv"):
            try:
                v = VideoFileClip(path)
                if v.duration < duration and v.duration > 0.1:
                    v = concatenate_videoclips(
                        [v] * (int(duration // v.duration) + 1), method="compose")
                return v.subclip(0, duration).resize(size)
            except Exception as e:
                print(f"[ERR] Video: {e}")
    return ColorClip(size=size, color=(20, 20, 30), duration=duration)


# ============================================================
#  MAIN RENDER
# ============================================================

def render_video(project_name, scenes, auto_ai=True, size=(1280, 720), fps=25,
                 subtitles=False, subtitle_style="bottom", font_size=32,
                 use_elevenlabs=False, background_music=None, music_volume=0.1,
                 use_avatar=False, avatar_position="bottom-right",
                 avatar_size="medium", avatar_style="business"):

    print(f"[INFO] Rendering {size[0]}×{size[1]} @ {fps} fps | {len(scenes)} scenes")
    if use_avatar:
        print(f"[INFO] Avatar: {avatar_style} ({avatar_size}) @ {avatar_position}")

    vw, vh = size

    if use_avatar and subtitle_style == "bottom":
        av_h = AVATAR_SIZE_H.get(avatar_size, 280)
        av_w = max(80, int(av_h * 572 / 618))
        sub_side  = ("right" if "right" in avatar_position
                     else "left" if "left" in avatar_position else "none")
        sub_avw   = av_w
        print(f"[INFO] Subtitle zone: {sub_side}, reserving {av_w}px")
    else:
        sub_side = "none"; sub_avw = 0

    clips = []
    for i, s in enumerate(scenes):
        print(f"\n[INFO] Scene {i+1}/{len(scenes)}")
        text     = (s.get("text") or "").strip()
        bg       = (s.get("background_path") or "").strip() or None
        duration = float(s.get("duration") or 5.0)
        voice_id = s.get("voice_id") or None
        audio    = None

        if text:
            aud = os.path.join(GEN_AUD,
                               f"{s.get('id','scene')}_{uuid.uuid4().hex[:6]}.mp3")
            try:
                tts_generate(text, aud, voice_id=voice_id,
                             use_elevenlabs=use_elevenlabs)
                audio = AudioFileClip(aud)
            except Exception as e:
                print(f"[ERR] TTS: {e}")
                if use_elevenlabs:
                    try: tts_gtts(text, aud); audio = AudioFileClip(aud)
                    except: pass

        if audio:
            try:
                d = max(0.1, audio.duration)
                if d > duration: duration = d + 0.5
            except: pass

        if not bg and auto_ai:
            img_path = os.path.join(GEN_IMG,
                                    f"{s.get('id','scene')}_{uuid.uuid4().hex[:6]}.png")
            prompt = s.get("image_prompt", "").strip() or text
            if prompt:
                try: ai_generate_image(prompt, img_path, size=size); bg = img_path
                except Exception as e: print(f"[ERR] ImgGen: {e}")

        try:   bg_clip = background_clip(bg, duration, size=size)
        except Exception as e: print(f"[ERR] BG: {e}"); raise

        if audio:
            try: bg_clip = bg_clip.set_audio(audio)
            except: pass

        if subtitles and text:
            try:
                si = create_subtitle_image(
                    text, size=size, fontsize=font_size, padding=18,
                    position=subtitle_style,
                    avatar_side=sub_side, avatar_width=sub_avw, avatar_margin=25)
                if   subtitle_style == "top":    sub_pos = ("center", 20)
                elif subtitle_style == "center": sub_pos = ("center", "center")
                else:                            sub_pos = ("center", vh - 90)
                sc   = ImageClip(si).set_duration(duration).set_position(sub_pos)
                comp = CompositeVideoClip([bg_clip, sc])
                if audio: comp = comp.set_audio(audio)
                clips.append(comp)
            except Exception as e:
                print(f"[ERR] Subtitles: {e}"); clips.append(bg_clip)
        else:
            clips.append(bg_clip)

    if not clips: raise ValueError("No valid clips")

    print(f"\n[INFO] Concatenating {len(clips)} clips …")
    final = concatenate_videoclips(clips, method="compose")

    if use_avatar:
        try:
            print("\n[INFO] Adding avatar …")
            va = final.audio
            if va:
                final = create_avatar_overlay(
                    final, va,
                    {"position": avatar_position,
                     "size":     avatar_size,
                     "style":    avatar_style})
                print("[OK] Avatar added!")
            else:
                print("[WARN] No audio for avatar")
        except Exception as e:
            print(f"[WARN] Avatar failed: {e}")
            import traceback; traceback.print_exc()

    if background_music and os.path.exists(background_music):
        try:
            music = AudioFileClip(background_music)
            vd    = final.duration
            if music.duration < vd:
                from moviepy.audio.AudioClip import concatenate_audioclips
                music = concatenate_audioclips(
                    [music] * (int(vd / music.duration) + 1))
            music = music.subclip(0, vd).volumex(music_volume)
            if final.audio:
                from moviepy.audio.AudioClip import CompositeAudioClip
                final = final.set_audio(CompositeAudioClip([final.audio, music]))
            else:
                final = final.set_audio(music)
        except Exception as e:
            print(f"[WARN] Music: {e}")

    out_path  = os.path.join(OUTPUTS, f"{project_name}_{uuid.uuid4().hex[:8]}.mp4")
    tmp_audio = os.path.join(TEMP_DIR, f"tmp-{uuid.uuid4().hex[:8]}.m4a")
    try:
        print(f"\n[INFO] Encoding → {os.path.basename(out_path)}")
        final.write_videofile(
            out_path, fps=fps, codec="libx264", audio_codec="aac",
            preset="medium", bitrate="3500k", audio_bitrate="192k",
            ffmpeg_params=["-crf", "20", "-movflags", "+faststart",
                           "-pix_fmt", "yuv420p"],
            temp_audiofile=tmp_audio, remove_temp=False,
            verbose=False, logger=None, threads=4)
        print(f"[OK] {os.path.basename(out_path)}")
        try:
            if os.path.exists(tmp_audio): time.sleep(0.1); os.remove(tmp_audio)
        except: pass
    except Exception as e:
        print(f"[ERR] Encoding: {e}")
        try:
            if os.path.exists(tmp_audio): time.sleep(0.1); os.remove(tmp_audio)
        except: pass
        raise

    try: final.close()
    except: pass
    for c in clips:
        try: c.close()
        except: pass

    return out_path


# ============================================================
#  __main__ diagnostics
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("AI Text-to-Video Utils v8")
    print("=" * 70)
    print(f"Groq:         {'OK' if groq_available       else 'MISSING'}")
    print(f"ElevenLabs:   {'OK' if elevenlabs_available  else 'MISSING'}")
    print(f"Cloudflare:   {'OK' if client['available']   else 'MISSING'}")
    print(f"ffmpeg:       {FFMPEG_PATH or 'MISSING'}")
    print(f"Alpha method: PNG alpha channel (presenter_photo.png)")
    print(f"OpenCV:       {'OK (fallback)' if CV2_AVAILABLE else 'MISSING'}")
    print(f"Alpha cache:  {ALPHA_CACHE_DIR}")
    cached = [f for f in os.listdir(ALPHA_CACHE_DIR) if f.endswith(".npy")]
    if cached:
        print(f"Cached masks ({len(cached)}):")
        for m in cached:
            kb = os.path.getsize(os.path.join(ALPHA_CACHE_DIR, m)) // 1024
            print(f"  {m}  ({kb} KB)")
    else:
        print("No masks cached yet — created automatically on first render")
    print("=" * 70)
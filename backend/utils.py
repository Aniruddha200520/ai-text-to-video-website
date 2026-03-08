#!/usr/bin/env python3
"""
utils.py v14
- GPU compositing via PyTorch CUDA (torch+cu118)
- RTX 3050 optimised: NO temp bg file written — frames stream directly from MoviePy
- NVIDIA encoder: hevc_nvenc with CORRECT preset args (p4 instead of fast)
  'fast' preset is NOT valid for hevc_nvenc — must use p1..p7 or 'medium'
- ffmpeg: auto-detects from PATH, imageio_ffmpeg, and common Windows locations
- Male avatar defaults to Will voice, Female to Jessica
- Subtitle position clamped so text never overflows the frame
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
import torch
import cv2

# ── GPU via PyTorch CUDA ──────────────────────────────────────────────────────
if not torch.cuda.is_available():
    raise RuntimeError("[FATAL] torch.cuda not available — check CUDA installation.")
DEVICE = torch.device("cuda")
GPU_NAME = torch.cuda.get_device_name(0)
print(f"[OK] PyTorch CUDA: {GPU_NAME} — GPU compositing ENABLED")

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
    if avatar_style in ("female", "female_business", "female_casual"):
        return PRESENTER_FEMALE
    return PRESENTER_MALE

PRESENTER_PHOTO = PRESENTER_MALE

for _p in (UPLOADS, OUTPUTS, GEN_IMG, GEN_AUD, MUSIC_CACHE,
           TEMP_DIR, CACHE_DIR, ALPHA_CACHE_DIR):
    os.makedirs(_p, exist_ok=True)

load_dotenv()
GROQ_API_KEY          = os.getenv("GROQ_API_KEY")
_raw_el_keys = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_API_KEYS = [k.strip() for k in _raw_el_keys.split(",")
                       if k.strip() and k.strip() != "your_elevenlabs_key_here"]
ELEVENLABS_API_KEY  = ELEVENLABS_API_KEYS[0] if ELEVENLABS_API_KEYS else None
_el_key_index       = 0
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
if ELEVENLABS_API_KEYS:
    try:
        from elevenlabs import generate, voices, set_api_key
        set_api_key(ELEVENLABS_API_KEYS[0])
        elevenlabs_available = True
        n = len(ELEVENLABS_API_KEYS)
        print(f"[OK] ElevenLabs configured ({n} key{'s' if n>1 else ''})")
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


# ============================================================
#  FFMPEG — ROBUST DETECTION + VERIFICATION
# ============================================================

def _find_ffmpeg():
    import sys, glob as _glob

    candidates = []

    env_path = os.getenv("FFMPEG_PATH", "").strip()
    if env_path and os.path.exists(env_path):
        candidates.append(("FFMPEG_PATH env var", env_path))

    prefix = sys.prefix
    conda_paths = [
        os.path.join(prefix, "bin", "ffmpeg"),
        os.path.join(prefix, "bin", "ffmpeg.exe"),
        os.path.join(prefix, "Library", "bin", "ffmpeg.exe"),
        os.path.join(prefix, "Library", "bin", "ffmpeg"),
    ]
    for p in conda_paths:
        if os.path.exists(p):
            candidates.append(("conda env (conda-forge)", p))

    try:
        import ffmpeg_downloader as ffdl
        ffdl_ff = ffdl.ffmpeg_path
        if ffdl_ff and os.path.exists(ffdl_ff):
            candidates.append(("ffmpeg-downloader (full NVENC build)", ffdl_ff))
    except Exception:
        pass

    try:
        import site
        for sp in site.getsitepackages():
            ffdl_guess = os.path.join(sp, "ffmpeg_downloader", "ffmpeg.exe")
            if os.path.exists(ffdl_guess):
                candidates.append(("ffmpeg-downloader (site-packages path)", ffdl_guess))
    except Exception:
        pass

    path_ff = shutil.which("ffmpeg")
    if path_ff:
        candidates.append(("system PATH", path_ff))

    # imageio_ffmpeg — stripped, no NVENC, lowest priority
    try:
        import imageio_ffmpeg
        iio_ff = imageio_ffmpeg.get_ffmpeg_exe()
        if iio_ff and os.path.exists(iio_ff):
            candidates.append(("imageio_ffmpeg (stripped, no NVENC)", iio_ff))
    except Exception:
        pass

    win_paths = [
        r"C:\Users\aniru\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in win_paths:
        if os.path.exists(p):
            candidates.append(("windows standalone", p))

    seen, unique = set(), []
    for source, path in candidates:
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in seen:
            seen.add(norm)
            unique.append((source, path))

    for source, path in unique:
        try:
            result = subprocess.run([path, "-version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                ver_line = result.stdout.split("\n")[0] if result.stdout else "?"
                is_stripped = "imageio_ffmpeg" in path.lower()
                flag = " ⚠️ stripped build (no NVENC)" if is_stripped else ""
                print(f"[OK] ffmpeg: {path}")
                print(f"     Source:  {source}{flag}")
                print(f"     Version: {ver_line}")
                return path
        except Exception as e:
            continue

    print("[WARN] No ffmpeg found!")
    return None

FFMPEG_PATH = _find_ffmpeg()
if not FFMPEG_PATH:
    print("[WARN] ffmpeg not found.")


def _get_ffmpeg_version(ff_path: str):
    try:
        result = subprocess.run([ff_path, "-version"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if line.startswith("ffmpeg version"):
                parts = line.split()
                if len(parts) >= 3:
                    ver_str = parts[2].lstrip("nN")
                    major = int(ver_str.split(".")[0])
                    return major
    except Exception:
        pass
    return 0


def _nvenc_preset_for_version(major_version: int) -> str:
    if major_version >= 5:
        return "p4"
    else:
        return "fast"


def _test_nvenc_encoder(ff_path: str, codec: str, preset: str) -> tuple:
    presets_to_try = [preset]
    if preset == "fast":
        presets_to_try += ["medium", "hq", "hp", "default"]
    elif preset == "p4":
        presets_to_try += ["p5", "p3", "fast", "medium", "hq"]

    for p in presets_to_try:
        try:
            test_out = os.path.join(TEMP_DIR, f"_nvenc_test_{codec}_{p}.mp4")
            cmd = [
                ff_path, "-y",
                "-f", "lavfi", "-i", "color=black:size=640x480:rate=25:duration=0.4",
                "-c:v", codec, "-preset", p, "-pix_fmt", "yuv420p",
                "-t", "0.4",
                test_out
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            success = (result.returncode == 0
                       and os.path.exists(test_out)
                       and os.path.getsize(test_out) > 100)
            try:
                if os.path.exists(test_out):
                    os.remove(test_out)
            except Exception:
                pass
            if success:
                print(f"[OK] {codec} test passed with preset='{p}'")
                return True, p
            else:
                err_lines = [l for l in (result.stderr or "").splitlines()
                             if any(k in l for k in ("error", "Error", "Unable", "Invalid"))]
                err = err_lines[-1] if err_lines else ""
                print(f"     [SKIP] {codec} preset='{p}': {err[:120]}")
        except Exception as e:
            print(f"     [SKIP] {codec} preset='{p}': {e}")

    return False, None


def _detect_nvenc():
    ff = FFMPEG_PATH or "ffmpeg"
    if not ff or not os.path.exists(ff if ff != "ffmpeg" else shutil.which("ffmpeg") or ""):
        print("[WARN] No ffmpeg — run: conda install -c conda-forge ffmpeg")
        return (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"],
                "libx264 CPU (no ffmpeg found)")

    ff_major = _get_ffmpeg_version(ff)
    preset   = _nvenc_preset_for_version(ff_major)
    ff_lower = ff.lower()
    is_stripped = "imageio_ffmpeg" in ff_lower or "imageio-ffmpeg" in ff_lower

    if is_stripped:
        print(f"[INFO] imageio-ffmpeg (stripped, no NVENC) — using libx264 for encoding")
        return (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"],
                "libx264 CPU encode + PyTorch CUDA GPU composite ✅")

    print(f"[INFO] Testing NVENC (ffmpeg v{ff_major}, preset='{preset}')...")
    try:
        check = subprocess.run([ff, "-codecs"], capture_output=True, text=True, timeout=5)
        codec_list = check.stdout

        if "hevc_nvenc" in codec_list:
            ok, working_preset = _test_nvenc_encoder(ff, "hevc_nvenc", preset)
            if ok:
                return (["-c:v", "hevc_nvenc", "-preset", working_preset, "-pix_fmt", "yuv420p"],
                        f"NVIDIA HEVC (hevc_nvenc preset={working_preset}) — full GPU ✅")
            print("[INFO] hevc_nvenc not available, trying h264_nvenc")

        if "h264_nvenc" in codec_list:
            ok, working_preset = _test_nvenc_encoder(ff, "h264_nvenc", preset)
            if ok:
                return (["-c:v", "h264_nvenc", "-preset", working_preset, "-pix_fmt", "yuv420p"],
                        f"NVIDIA H264 (h264_nvenc preset={working_preset}) — full GPU ✅")
            print("[INFO] h264_nvenc not available, using libx264")

    except Exception as e:
        print(f"[WARN] NVENC test error: {e}")

    return (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"],
            "libx264 CPU encode + PyTorch CUDA GPU composite ✅")


_NVENC_ARGS, _NVENC_LABEL = _detect_nvenc()
print(f"[OK] Encoder: {_NVENC_LABEL}")

_CPU_ARGS = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"]


# ============================================================
#  ALPHA MASK
# ============================================================

def _presenter_cache_key(avatar_style: str = "male"):
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
    h0, w0 = frames_bgr[0].shape[:2]

    if cache_key:
        cached = _load_cached_alpha(cache_key)
        if cached is not None:
            if cached.shape == (h0, w0):
                return cached
            print("[WARN] Cached alpha shape mismatch — recomputing")

    print(f"[INFO] Loading alpha from presenter PNG …")
    alpha = _load_presenter_alpha(w0, h0, avatar_style=avatar_style)

    if alpha is None:
        print("[WARN] No PNG alpha found — using fully opaque mask")
        alpha = np.ones((h0, w0), dtype=np.float32)

    print(f"\n[OK] Alpha ready — fg={alpha.mean()*100:.1f}%")

    if cache_key:
        _save_cached_alpha(cache_key, alpha)

    return alpha


# ============================================================
#  WAV2LIP
# ============================================================
AVATAR_SIZE_H = {"small": 200, "medium": 280, "large": 360}

def run_wav2lip(audio_path: str, output_path: str, avatar_style: str = "male") -> bool:
    photo_path = get_presenter_photo(avatar_style)
    if not os.path.exists(photo_path):
        print(f"[ERR] Presenter photo not found: {photo_path}"); return False
    if not os.path.exists(WAV2LIP_RUNNER):
        print(f"[ERR] wav2lip_runner.py not found: {WAV2LIP_RUNNER}"); return False
    # Search common anaconda/miniconda locations for wav2lip env python
    base_paths = [
        r"C:\Users\aniru\anaconda3\envs",
        r"C:\Users\aniru\Anaconda3\envs",
        r"C:\Users\aniru\miniconda3\envs",
        r"C:\ProgramData\anaconda3\envs",
        r"C:\ProgramData\miniconda3\envs",
    ]
    py = None
    for base in base_paths:
        candidate = os.path.join(base, WAV2LIP_CONDA, "python.exe")
        if os.path.exists(candidate):
            py = candidate
            break
    if not py:
        print(f"[ERR] Wav2Lip python not found in any conda env location"); return False
    print(f"[DEBUG] wav2lip python: {py}")
    cmd = [py, WAV2LIP_RUNNER,
           "--face",   photo_path,
           "--audio",  audio_path,
           "--output", output_path]
    print("[INFO] Running Wav2Lip …")
    try:
        res = subprocess.run(cmd, timeout=300, capture_output=True, text=True,
                             cwd=WAV2LIP_DIR)
        if res.returncode == 0 and os.path.exists(output_path):
            mb = os.path.getsize(output_path) / 1024 / 1024
            print(f"[OK] Wav2Lip → {output_path} ({mb:.1f} MB)")
            return True
        print(f"[ERR] Wav2Lip failed (rc={res.returncode})")
        if res.stdout: print("[wav2lip stdout]", res.stdout[-800:])
        if res.stderr: print("[wav2lip stderr]", res.stderr[-800:])
        return False
    except subprocess.TimeoutExpired:
        print("[ERR] Wav2Lip timed out"); return False
    except Exception as e:
        print(f"[ERR] Wav2Lip: {e}"); return False


# ============================================================
#  GPU ALPHA BLEND — PyTorch CUDA
# ============================================================

def _blend_chunk_torch(bg_chunk_np, av_sel_np, a3_roi_np, y1, y2c, x1, x2c):
    N = len(bg_chunk_np)
    t_alpha     = torch.from_numpy(a3_roi_np).to(DEVICE)
    t_inv_alpha = 1.0 - t_alpha
    t_av = torch.from_numpy(av_sel_np).to(DEVICE)
    t_bg = torch.from_numpy(bg_chunk_np[:, y1:y2c, x1:x2c, :]).to(DEVICE)
    blended = t_av * t_alpha + t_bg * t_inv_alpha
    bg_chunk_np[:, y1:y2c, x1:x2c, :] = blended.cpu().numpy()
    return bg_chunk_np


# ============================================================
#  AVATAR COMPOSITE — ffmpeg one-pass
# ============================================================

def composite_avatar_on_video(video_clip, wav2lip_path: str,
                               position_name: str = "bottom-right",
                               size_name: str = "medium",
                               avatar_style: str = "male",
                               bg_video_path: str = None,
                               scene_bg_paths=None,
                               audio_path: str = None,
                               subtitle_segments=None,
                               vw_out: int = 1280,
                               vh_out: int = 720,
                               font_size: int = 18):
    import time as _t
    ff = FFMPEG_PATH or "ffmpeg"

    try:
        vw, vh = video_clip.size
        vfps   = float(video_clip.fps or 25)
    except:
        vw, vh, vfps = 1280, 720, 25.0

    # Avatar dimensions & position
    ah = AVATAR_SIZE_H.get(size_name, 280)
    aw = max(80, int(ah * 572 / 618))
    margin = 5
    pos_map = {
        "bottom-right":  (vw - aw - margin, vh - ah),
        "bottom-left":   (margin,            vh - ah),
        "top-right":     (vw - aw - margin,  margin),
        "top-left":      (margin,            margin),
        "bottom-center": (vw//2 - aw//2,     vh - ah),
    }
    ax, ay = pos_map.get(position_name, pos_map["bottom-right"])
    print(f"[INFO] Avatar {aw}×{ah} at ({ax},{ay})")

    # Load Wav2Lip frames + alpha
    cap  = cv2.VideoCapture(wav2lip_path)
    sfps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames_bgr = []
    while True:
        ok, frm = cap.read()
        if not ok: break
        frames_bgr.append(frm)
    cap.release()

    if not frames_bgr:
        print("[ERR] No Wav2Lip frames"); return video_clip

    n_av = len(frames_bgr)
    print(f"[INFO] Wav2Lip: {n_av} frames  {frames_bgr[0].shape[1]}×{frames_bgr[0].shape[0]}")

    base_key  = _presenter_cache_key(avatar_style=avatar_style)
    sw, sh    = frames_bgr[0].shape[1], frames_bgr[0].shape[0]
    sized_key = f"{base_key}_{sw}x{sh}" if base_key else None
    alpha_bgr = build_static_alpha(frames_bgr, cache_key=sized_key, feather=2,
                                   avatar_style=avatar_style)

    frames_rgb = []
    for frm in frames_bgr:
        rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
        # LANCZOS4 for upscaling (sharper), AREA for downscaling
        interp = cv2.INTER_LANCZOS4 if (aw * ah > frm.shape[1] * frm.shape[0]) else cv2.INTER_AREA
        rgb = cv2.resize(rgb, (aw, ah), interpolation=interp)
        frames_rgb.append(rgb)

    if alpha_bgr is not None:
        a1 = alpha_bgr[:, :, 0] if alpha_bgr.ndim == 3 else alpha_bgr
        _a_interp = cv2.INTER_LANCZOS4 if (aw * ah > a1.shape[1] * a1.shape[0]) else cv2.INTER_AREA
        a1 = cv2.resize(a1.astype(np.float32), (aw, ah), interpolation=_a_interp)
        alpha_uint8 = (a1 * 255).clip(0, 255).astype(np.uint8)
    else:
        alpha_uint8 = np.full((ah, aw), 255, dtype=np.uint8)

    print(f"[OK] {n_av} avatar frames ready ({aw}×{ah})")

    # Write avatar RGBA video via pipe (GPU torch for RGBA assembly)
    av_path = os.path.join(TEMP_DIR, f"_av_rgba_{uuid.uuid4().hex[:8]}.mp4")
    av_cmd  = [ff, "-y",
               "-f", "rawvideo", "-vcodec", "rawvideo",
               "-s", f"{aw}x{ah}", "-pix_fmt", "rgba", "-r", str(sfps),
               "-i", "pipe:0",
               "-c:v", "png", "-pix_fmt", "rgba",
               av_path]
    t0 = _t.time()
    av_proc = subprocess.Popen(av_cmd, stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    alpha_t = torch.from_numpy(alpha_uint8).to(DEVICE)
    for rgb in frames_rgb:
        rgb_t  = torch.from_numpy(rgb).to(DEVICE)
        rgba_t = torch.cat([rgb_t, alpha_t.unsqueeze(-1)], dim=-1)
        av_proc.stdin.write(rgba_t.cpu().numpy().tobytes())
    av_proc.stdin.close()
    av_proc.wait()
    print(f"[INFO] Avatar RGBA video written in {_t.time()-t0:.1f}s → {av_path}")

    if not os.path.exists(av_path) or os.path.getsize(av_path) < 1000:
        print("[ERR] Avatar RGBA write failed"); return video_clip

    # Build bg concat
    bg_src  = bg_video_path if (bg_video_path and os.path.exists(bg_video_path)) else None
    bg_temp = None

    if not bg_src:
        valid = [(p, d) for p, d in (scene_bg_paths or []) if p and os.path.exists(p)]
        if valid:
            bg_temp = os.path.join(TEMP_DIR, f"_bg_{uuid.uuid4().hex[:8]}.mp4")
            print(f"[INFO] Building bg via ffmpeg concat ({len(valid)} clips)...")
            t0 = _t.time()
            inputs, fparts = [], []
            for idx, (p, dur) in enumerate(valid):
                inputs += ["-i", p]
                # FIX: Use loop+trim instead of bare trim so short video clips
                # (e.g. 3.9s clip needing 5s) are looped to fill the duration.
                # The old tpad caused double-processing. loop+trim is correct and fast.
                fparts.append(
                    f"[{idx}:v]setpts=PTS-STARTPTS,"
                    f"loop=loop=-1:size=32767:start=0,"
                    f"trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
                    f"scale={vw}:{vh}:force_original_aspect_ratio=decrease,"
                    f"pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2,fps={vfps}[v{idx}]"
                )
            cin = "".join(f"[v{i}]" for i in range(len(valid)))
            fstr = ";".join(fparts) + f";{cin}concat=n={len(valid)}:v=1:a=0[vout]"
            res = subprocess.run(
                [ff, "-y"] + inputs +
                ["-filter_complex", fstr, "-map", "[vout]",
                 "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-crf", "28",
                 bg_temp],
                capture_output=True, timeout=300)
            if res.returncode != 0 or not os.path.exists(bg_temp):
                print(f"[WARN] bg concat failed: {res.stderr.decode(errors='replace')[-200:]}")
                bg_temp = None
            else:
                sz = os.path.getsize(bg_temp)//1024//1024
                print(f"[INFO] Bg concat done in {_t.time()-t0:.1f}s — {sz}MB")
                bg_src = bg_temp

    if not bg_src:
        print("[WARN] No bg source, returning original clip")
        try: os.remove(av_path)
        except: pass
        return video_clip

    # Use sum of scene durations directly — MoviePy concatenation adds tiny gaps
    total_dur = sum(d for _, d in (scene_bg_paths or [])) or video_clip.duration
    out_comp  = os.path.join(TEMP_DIR, f"_comp_{uuid.uuid4().hex[:8]}.mp4")

    fc_parts = []
    fc_parts.append(
        f"[0:v]scale={vw_out}:{vh_out}:force_original_aspect_ratio=decrease,"
        f"pad={vw_out}:{vh_out}:(ow-iw)/2:(oh-ih)/2,fps={vfps}[bg]"
    )
    fc_parts.append(
        f"[1:v]loop=loop=-1:size={n_av}:start=0,"
        f"trim=duration={total_dur:.3f},setpts=PTS-STARTPTS[av]"
    )
    fc_parts.append(f"[bg][av]overlay={ax}:{ay}:format=auto[ov]")

    last_label = "ov"

    # SRT subtitles
    ass_path = None
    if subtitle_segments:
        import re as _re2
        def _ts_ass(s):
            h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
            cs = int((sec % 1) * 100); sec = int(sec)
            return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"
        ass_path = os.path.join(TEMP_DIR, f"_subs_{uuid.uuid4().hex[:8]}.ass")
        # PlayResX/PlayResY tell ASS the canvas size so margins are pixel-accurate
        # With PlayResX=1280 and MarginR=320, text wraps at x=960 (left of avatar at 1016)
        ass_header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            f"PlayResX: {vw_out}\n"
            f"PlayResY: {vh_out}\n"
            "WrapStyle: 1\n\n"
            "[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
            "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
            "Alignment,MarginL,MarginR,MarginV,Encoding\n"
            "Style: Default,Arial,22,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
            "1,0,0,0,100,100,0,0,1,2,0,1,20,320,30,1\n\n"
            "[Events]\n"
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        )
        with open(ass_path, "w", encoding="utf-8") as _sf:
            _sf.write(ass_header)
            for _txt, _ts2, _te in subtitle_segments:
                _safe = _re2.sub(r"[{}<>|\\]", " ", _txt).strip()
                _sf.write(f"Dialogue: 0,{_ts_ass(_ts2)},{_ts_ass(_te)},Default,,0,0,0,,{_safe}\n")
        print(f"[INFO] ASS: {len(subtitle_segments)} entries")
        _sp = ass_path.replace("\\", "/")
        if len(_sp) > 1 and _sp[1] == ":":
            _sp = _sp[0] + "\\:" + _sp[2:]
        fc_parts.append(f"[{last_label}]subtitles='{_sp}'[vsub]")
        last_label = "vsub"
    filter_complex = ";".join(fc_parts)

    enc = list(_NVENC_ARGS) if _NVENC_ARGS else \
          ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"]

    cmd = [ff, "-y", "-i", bg_src, "-i", av_path]
    if audio_path and os.path.exists(audio_path):
        cmd += ["-i", audio_path]
        audio_map = ["-map", "2:a", "-c:a", "copy"]
    else:
        audio_map = ["-an"]

    cmd += ["-filter_complex", filter_complex,
            "-map", f"[{last_label}]",
            "-r", str(vfps)]
    cmd += enc + audio_map + ["-movflags", "+faststart", out_comp]

    print(f"[INFO] One-pass encode: overlay + subs + audio (NVENC)...")
    t0 = _t.time()
    res = subprocess.run(cmd, capture_output=True, timeout=600)
    elapsed = _t.time() - t0

    for p in [av_path]:
        try: os.remove(p)
        except: pass
    if bg_temp and bg_temp != bg_video_path:
        try: os.remove(bg_temp)
        except: pass
    if ass_path:
        try: os.remove(ass_path)
        except: pass

    if res.returncode != 0 or not os.path.exists(out_comp) or os.path.getsize(out_comp) < 10000:
        err = res.stderr.decode(errors="replace")[-500:]
        print(f"[ERR] ffmpeg one-pass failed ({elapsed:.1f}s):\n{err}")
        return video_clip

    sz = os.path.getsize(out_comp) // 1024 // 1024
    print(f"[OK] Composite+subs+audio: {os.path.basename(out_comp)} ({elapsed:.1f}s, {sz}MB)")

    from moviepy.editor import VideoFileClip as _VFC
    result = _VFC(out_comp)
    return result


def create_avatar_overlay(video_clip, audio_clip, avatar_config: dict,
                          bg_video_path: str = None, scene_bg_paths=None,
                          audio_path: str = None, subtitle_segments=None,
                          font_size: int = 18):
    pos   = avatar_config.get("position", "bottom-right")
    size  = avatar_config.get("size",     "medium")
    style = avatar_config.get("style",    "male")
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
            result = composite_avatar_on_video(video_clip, t_out, pos, size,
                                               avatar_style=style,
                                               bg_video_path=bg_video_path,
                                               scene_bg_paths=scene_bg_paths,
                                               audio_path=audio_path,
                                               subtitle_segments=subtitle_segments,
                                               vw_out=video_clip.size[0],
                                               vh_out=video_clip.size[1],
                                               font_size=font_size)
            for p in (t_wav, t_out):
                try: os.remove(p)
                except: pass
            print("[OK] Avatar overlay complete!")
            return result
        print("[ERR] Wav2Lip failed")

    print("[WARN] Avatar skipped")
    return video_clip


# ============================================================
#  SUBTITLE IMAGE (legacy fallback)
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
    return out, canvas_h


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
    if not groq_available:
        raise Exception("Groq not configured")

    tw = int((duration / 60) * 150)

    sm = {
        "educational": "Write an informative educational script about",
        "narrative":   "Write a compelling narrative story about",
        "promotional": "Write an exciting promotional script about",
        "documentary": "Write a documentary-style script about",
        "tutorial":    "Write a step-by-step tutorial script about",
    }

    res = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional scriptwriter. "
                    "Output ONLY the spoken script text — plain sentences only, no formatting. "
                    "Absolutely DO NOT include: timestamps, time codes, "
                    "narrator labels, stage directions, music cues, "
                    "section headers, brackets [ ], parentheses instructions, "
                    "or any metadata whatsoever. "
                    "Write only the sentences that will be spoken aloud, "
                    "one after another, each ending with a period."
                )
            },
            {
                "role": "user",
                "content": (
                    f"{sm.get(style, sm['educational'])} {topic}. "
                    f"Approximately {tw} words for a {duration}-second video. "
                    f"Write only the spoken sentences, nothing else."
                )
            },
        ],
        max_tokens=tw + 100,
        temperature=0.7,
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
        _resolve_voice_ids()
        from elevenlabs import voices as gv
        vl = gv()
        all_voices = [
            {"voice_id": v.voice_id, "name": v.name,
             "category": getattr(v, "category", "unknown"),
             "description": getattr(v, "description", "")}
            for v in vl
        ]
        will_v    = [v for v in all_voices if v["voice_id"] == VOICE_WILL]
        jessica_v = [v for v in all_voices if v["voice_id"] == VOICE_JESSICA]
        rest      = sorted([v for v in all_voices
                            if v["voice_id"] not in (VOICE_WILL, VOICE_JESSICA)],
                           key=lambda x: x["name"])
        _cached_voices = will_v + jessica_v + rest
        with open(VOICES_CACHE_FILE, "w") as f:
            json.dump(_cached_voices, f, indent=2)
        return _cached_voices
    except Exception as e:
        print(f"[WARN] voices: {e}"); return []

VOICE_WILL    = None
VOICE_JESSICA = None
_VOICE_IDS_RESOLVED = False

def _resolve_voice_ids():
    global VOICE_WILL, VOICE_JESSICA, _VOICE_IDS_RESOLVED
    if _VOICE_IDS_RESOLVED:
        return
    if os.path.exists(VOICES_CACHE_FILE):
        try:
            import json as _json
            cached = _json.load(open(VOICES_CACHE_FILE))
            for v in cached:
                n = v.get("name", "").strip().lower()
                if n == "will"    and not VOICE_WILL:    VOICE_WILL    = v["voice_id"]
                if n == "jessica" and not VOICE_JESSICA: VOICE_JESSICA = v["voice_id"]
        except: pass
    if (not VOICE_WILL or not VOICE_JESSICA) and elevenlabs_available:
        try:
            from elevenlabs import voices as _gv
            for v in _gv():
                n = v.name.strip().lower()
                if n == "will"    and not VOICE_WILL:    VOICE_WILL    = v.voice_id
                if n == "jessica" and not VOICE_JESSICA: VOICE_JESSICA = v.voice_id
        except Exception as e:
            if "voices_read" not in str(e).lower():
                print(f"[WARN] Could not resolve voice IDs: {e}")
    if not VOICE_WILL:    VOICE_WILL    = "bIHbv24MWmeRgasZH58o"
    if not VOICE_JESSICA: VOICE_JESSICA = "cgSgspJ2msm6clMCkdW9"
    _VOICE_IDS_RESOLVED = True
    print(f"[OK] Voices resolved — Will: {VOICE_WILL} | Jessica: {VOICE_JESSICA}")

def _rotate_elevenlabs_key():
    global _el_key_index, ELEVENLABS_API_KEY
    from elevenlabs import set_api_key
    _el_key_index = (_el_key_index + 1) % len(ELEVENLABS_API_KEYS)
    ELEVENLABS_API_KEY = ELEVENLABS_API_KEYS[_el_key_index]
    set_api_key(ELEVENLABS_API_KEY)
    print(f"[INFO] ElevenLabs: rotated to key #{_el_key_index + 1}")


def tts_elevenlabs(text, out_path, voice_id=None):
    if not elevenlabs_available: raise Exception("ElevenLabs not configured")
    _resolve_voice_ids()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    from elevenlabs import generate, set_api_key

    vid = voice_id if (voice_id and voice_id.strip()) else VOICE_WILL
    print(f"    [TTS] voice={vid} | key=#{_el_key_index + 1}/{len(ELEVENLABS_API_KEYS)}")

    for attempt in range(len(ELEVENLABS_API_KEYS)):
        try:
            set_api_key(ELEVENLABS_API_KEYS[_el_key_index])
            audio = generate(text=text, voice=vid, model="eleven_turbo_v2")
            with open(out_path, "wb") as f: f.write(audio)
            return out_path
        except Exception as e:
            err = str(e).lower()
            is_quota = any(k in err for k in ("quota", "credit", "limit", "exceeded", "insufficient"))
            if is_quota and len(ELEVENLABS_API_KEYS) > 1:
                print(f"    [WARN] Key #{_el_key_index + 1} quota exceeded, rotating...")
                _rotate_elevenlabs_key()
                continue
            raise

    raise Exception(f"All {len(ELEVENLABS_API_KEYS)} ElevenLabs keys exhausted")

def split_text_into_scenes(text, words_per_scene=30):
    import re
    text = text.strip()
    if not text: return []
    text = text.strip('"""\'\'\'')
    parts = text.split(".")
    scenes = []
    for p in parts:
        clean = p.strip().strip('"""\'\'\'').strip()
        if clean and re.search(r"[a-zA-Z0-9]", clean):
            scenes.append(clean + ".")
    return scenes

def tts_generate(text, out_path, voice_id=None, use_elevenlabs=False):
    if not voice_id or voice_id.strip().lower() == "gtts":
        return tts_gtts(text, out_path)
    if use_elevenlabs and elevenlabs_available:
        try: return tts_elevenlabs(text, out_path, voice_id)
        except Exception as e: print(f"[WARN] ElevenLabs→gTTS: {e}")
    return tts_gtts(text, out_path)

def tts_gtts(text, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    gTTS(text=text or " ", lang="en", slow=False).save(out_path)
    return out_path


def get_scene_durations(scenes, voice_id=None):
    """
    Pre-generate TTS audio for each scene to measure real duration.
    - Parallelised with ThreadPoolExecutor so N scenes ≈ time of 1 scene.
    - If elevenlabs_available and a non-gtts voice_id is supplied, tries ElevenLabs
      first for accurate timing; falls back to gTTS silently on any error.
    - Returns list of (scene_id, duration_seconds) tuples in original order.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    use_el = (elevenlabs_available
              and voice_id
              and voice_id.strip().lower() not in ("", "gtts"))

    def _measure_one(s):
        scene_id = s.get("id", "scene")
        text     = (s.get("text") or "").strip()
        if not text:
            return scene_id, 5.0
        try:
            tmp = os.path.join(TEMP_DIR, f"_dur_{uuid.uuid4().hex[:8]}.mp3")
            os.makedirs(TEMP_DIR, exist_ok=True)
            if use_el:
                try:
                    tts_elevenlabs(text, tmp, voice_id=voice_id)
                except Exception:
                    tts_gtts(text, tmp)   # EL quota/error — fall back silently
            else:
                tts_gtts(text, tmp)
            clip = AudioFileClip(tmp)
            dur  = max(clip.duration, 5.0)   # minimum 5s so video clips don't loop excessively
            clip.close()
            try: os.remove(tmp)
            except: pass
            return scene_id, dur
        except Exception as e:
            print(f"[WARN] get_scene_durations: {scene_id} failed ({e}), using 5s")
            return scene_id, 5.0

    max_workers = min(len(scenes), 6)   # cap at 6 parallel TTS calls
    order = {s["id"]: i for i, s in enumerate(scenes)}
    out   = [None] * len(scenes)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_measure_one, s): s for s in scenes}
        for fut in as_completed(futures):
            sid, dur = fut.result()
            idx = order.get(sid, len(out) - 1)
            out[idx] = (sid, dur)

    return [r for r in out if r is not None]


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
                vw, vh = v.size
                print(f"[INFO] Video bg: {vw}x{vh}, dur={v.duration:.1f}s")
                if v.duration >= duration:
                    # Clip is long enough — just trim
                    v = v.subclip(0, duration)
                else:
                    # Clip shorter than audio — play clip then freeze last frame
                    freeze_dur = duration - v.duration
                    try:
                        last_t = max(0, v.duration - 0.05)
                        freeze = ImageClip(
                            v.get_frame(last_t), duration=freeze_dur)
                        v = concatenate_videoclips([v, freeze], method="chain")
                    except Exception as _fe:
                        print(f"[WARN] freeze frame failed: {_fe}, looping instead")
                        v = concatenate_videoclips(
                            [v] * (int(duration // v.duration) + 2), method="chain")
                        v = v.subclip(0, duration)
                if v.size != size:
                    v = v.resize(size)
                v = v.without_audio()  # strip Pexels audio, only TTS used
                return v
            except Exception as e:
                print(f"[ERR] Video: {e}")
    return ColorClip(size=size, color=(20, 20, 30), duration=duration)


# ============================================================
#  MAIN RENDER
# ============================================================

AUDIO_TAIL_TRIM = 0.0
_COMP_TMPS = []

def render_video(project_name, scenes, auto_ai=True, size=(1280, 720), fps=25,
                 subtitles=True, subtitle_style="bottom", font_size=18,
                 use_elevenlabs=False, background_music=None, music_volume=0.1,
                 use_avatar=False, avatar_position="bottom-right",
                 avatar_size="medium", avatar_style="male"):

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
    scene_bg_paths    = []
    subtitle_segments = []
    cumulative_t      = 0.0
    # Track (audio_file_path_or_None, scene_duration) explicitly.
    # We CANNOT rely on clip.audio.filename after subclip() — subclip loses .filename.
    scene_audio_info  = []   # list of (aud_path | None, scene_duration_float)

    MIN_SCENE_DUR = 5.0      # minimum scene duration — clips shorter than audio still
                              # get padded to at least this so video never feels rushed

    for i, s in enumerate(scenes):
        print(f"\n[INFO] Scene {i+1}/{len(scenes)}")
        text     = (s.get("text") or "").strip()
        bg       = (s.get("background_path") or "").strip() or None
        duration = max(float(s.get("duration") or MIN_SCENE_DUR), MIN_SCENE_DUR)

        _resolve_voice_ids()
        voice_id = (s.get("voice_id") or "").strip()
        if not voice_id:
            if use_avatar and avatar_style == "female":
                voice_id = VOICE_JESSICA
                print(f"    [Voice] Female avatar → ElevenLabs {voice_id}")
            else:
                voice_id = "gtts"
                print(f"    [Voice] → Google TTS (free)")

        audio     = None
        aud_path  = None      # keep the raw file path separately

        if text:
            aud_path = os.path.join(GEN_AUD,
                                    f"{s.get('id','scene')}_{uuid.uuid4().hex[:6]}.mp3")
            try:
                tts_generate(text, aud_path, voice_id=voice_id,
                             use_elevenlabs=use_elevenlabs)
                # Strip long internal silences ElevenLabs adds between words/phrases.
                # stop_periods=1 removes silence within the stream; threshold=-35dB catches
                # natural pauses while preserving normal speech rhythm.
                _ff = FFMPEG_PATH or "ffmpeg"
                _desilenced = aud_path.replace(".mp3", "_ds.mp3")
                _dsr = subprocess.run(
                    [_ff, "-y", "-i", aud_path,
                     "-af", (
                         "silenceremove="
                         "stop_periods=-1:"          # remove all silent gaps in stream
                         "stop_duration=0.4:"        # gaps longer than 0.4s get trimmed
                         "stop_threshold=-35dB"      # anything below -35dB = silence
                     ),
                     "-c:a", "libmp3lame", "-q:a", "2", _desilenced],
                    capture_output=True, timeout=30)
                if _dsr.returncode == 0 and os.path.exists(_desilenced) and os.path.getsize(_desilenced) > 500:
                    import shutil as _sh3
                    _sh3.move(_desilenced, aud_path)   # replace original with desilenced
                else:
                    try: os.remove(_desilenced)
                    except: pass
                audio = AudioFileClip(aud_path)
            except Exception as e:
                print(f"[ERR] TTS: {e}")
                if use_elevenlabs:
                    try:
                        tts_gtts(text, aud_path)
                        audio = AudioFileClip(aud_path)
                    except:
                        aud_path = None

        if audio:
            try:
                raw_dur = max(0.1, audio.duration)
                trimmed = max(0.1, raw_dur - AUDIO_TAIL_TRIM)
                # subclip loses .filename — we keep aud_path separately
                audio   = audio.subclip(0, trimmed)
                # scene duration = max(speech, minimum)
                if trimmed > duration:
                    duration = trimmed
            except:
                pass

        # Enforce minimum scene duration even if we have no audio
        duration = max(duration, MIN_SCENE_DUR)

        if not bg and auto_ai:
            img_path = os.path.join(GEN_IMG,
                                    f"{s.get('id','scene')}_{uuid.uuid4().hex[:6]}.png")
            prompt = s.get("image_prompt", "").strip() or text
            if prompt:
                try: ai_generate_image(prompt, img_path, size=size); bg = img_path
                except Exception as e: print(f"[ERR] ImgGen: {e}")

        try:   bg_clip = background_clip(bg, duration, size=size)
        except Exception as e: print(f"[ERR] BG: {e}"); raise

        if bg and bg.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            scene_bg_paths.append((bg, duration))
        else:
            scene_bg_paths.append((None, duration))

        # Track audio path + duration explicitly (safe after subclip)
        scene_audio_info.append((aud_path, duration))

        t_end = cumulative_t + duration
        if text:
            subtitle_segments.append((text, cumulative_t, t_end))
        cumulative_t = t_end

        if audio:
            try: bg_clip = bg_clip.set_audio(audio)
            except: pass
        clips.append(bg_clip)

    if not clips: raise ValueError("No valid clips")

    print(f"\n[INFO] Concatenating {len(clips)} clips …")
    final = concatenate_videoclips(clips, method="chain")

    # Build audio with correct per-scene timestamps.
    # Method: one anullsrc stream (full video length) + each TTS at its adelay offset,
    # mixed with amix. The anullsrc guarantees the output always reaches total_dur
    # regardless of when the last TTS finishes.
    pre_audio_path = os.path.join(TEMP_DIR, f"_preaudio_{uuid.uuid4().hex[:8]}.aac")
    _pre_audio_saved = False

    ff = FFMPEG_PATH or "ffmpeg"

    # Collect scenes that have actual TTS audio with their cumulative start times
    _cumulative = 0.0
    _audio_scenes = []   # (filepath, start_seconds, scene_duration)
    for fn, dur in scene_audio_info:
        if fn and os.path.exists(fn):
            _audio_scenes.append((fn, _cumulative, dur))
        _cumulative += dur
    total_dur = _cumulative

    if _audio_scenes:
        try:
            # Build ffmpeg command:
            # Input 0 = anullsrc (silent base, full duration) → ensures output = total_dur
            # Inputs 1..N = TTS mp3 files
            # Each TTS gets adelay'd to its scene start position
            # amix all together (normalize=0 to preserve levels)
            cmd = [ff, "-y",
                   "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={total_dur:.4f}"]
            for fn, _, _ in _audio_scenes:
                cmd += ["-i", fn]

            filter_parts = [f"[0:a]anull[base]"]   # pass-through the silence base
            mix_labels   = ["[base]"]
            for i, (_, start_s, _) in enumerate(_audio_scenes):
                delay_ms = int(start_s * 1000)
                lbl = f"a{i}"
                filter_parts.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[{lbl}]")
                mix_labels.append(f"[{lbl}]")

            n = len(_audio_scenes) + 1   # +1 for the base silence track
            filter_str = (";".join(filter_parts) +
                          f";{''.join(mix_labels)}amix=inputs={n}:"
                          f"duration=first:normalize=0[aout]")
            # duration=first → output ends when input 0 (anullsrc, total_dur) ends

            cmd += [
                "-filter_complex", filter_str,
                "-map", "[aout]",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
                pre_audio_path
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=120)
            if res.returncode != 0:
                err = res.stderr.decode(errors="replace")[-400:]
                print(f"[WARN] Audio build failed (rc={res.returncode}): {err}")

            if os.path.exists(pre_audio_path) and os.path.getsize(pre_audio_path) > 100:
                _pre_audio_saved = True
                _kb  = os.path.getsize(pre_audio_path) // 1024
                _exp = int(total_dur * 192000 / 8 / 1024)
                print(f"[INFO] Audio with timestamps: {_kb}KB / expected ~{_exp}KB "
                      f"(total {total_dur:.1f}s, {len(_audio_scenes)} TTS clips)")
            else:
                print(f"[WARN] Audio build produced empty/tiny file — will use MoviePy fallback")
        except Exception as e:
            print(f"[WARN] Audio build failed: {e}")
            import traceback; traceback.print_exc()

    if not _pre_audio_saved and final.audio is not None:
        try:
            _ac = final.audio
            if not getattr(_ac, "fps", None): _ac = _ac.set_fps(44100)
            _ac.write_audiofile(pre_audio_path, codec="aac", bitrate="192k",
                                verbose=False, logger=None)
            _pre_audio_saved = True
            print(f"[INFO] Audio saved (moviepy fallback): {os.path.getsize(pre_audio_path)//1024}KB")
        except Exception as e:
            print(f"[WARN] Audio save failed: {e}")

    if use_avatar:
        try:
            print("\n[INFO] Adding avatar overlay …")
            # Use final.audio for wav2lip (keeps it fast — it loops the avatar anyway).
            # pre_audio_path is passed separately as the composite audio track.
            va = final.audio
            if va:
                result = create_avatar_overlay(
                    final, va,
                    {"position": avatar_position,
                     "size":     avatar_size,
                     "style":    avatar_style},
                    bg_video_path=None,
                    scene_bg_paths=scene_bg_paths,
                    audio_path=pre_audio_path if _pre_audio_saved else None,
                    subtitle_segments=subtitle_segments if subtitles else None,
                    font_size=font_size)
                if result is not None:
                    final = result
                print("[OK] Avatar overlay complete!")
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

    out_path = os.path.join(OUTPUTS, f"{project_name}_{uuid.uuid4().hex[:8]}.mp4")
    ff       = FFMPEG_PATH or "ffmpeg"
    is_nvenc = "nvenc" in " ".join(_NVENC_ARGS)
    enc_args = list(_NVENC_ARGS) if is_nvenc else \
               ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"]

    print(f"\n[INFO] Encoding → {os.path.basename(out_path)}")

    try:
        # Avatar path: composite already has everything baked in
        comp_path = getattr(final, "filename", None)
        if comp_path and os.path.exists(comp_path) and os.path.getsize(comp_path) > 10000:
            import shutil as _shutil
            _shutil.copy2(comp_path, out_path)
            if os.path.exists(out_path):
                print(f"[OK] {os.path.basename(out_path)}")
                return out_path
            print("[WARN] Copy failed, falling back")

        # No-avatar path — pure ffmpeg concat + NVENC, no MoviePy
        valid_segs = [(p, d) for p, d in scene_bg_paths if p and os.path.exists(p)]
        if valid_segs and not use_avatar:
            print(f"[INFO] ffmpeg concat+encode (no avatar, {len(valid_segs)} clips)...")
            # Build ASS subtitle file for no-avatar path
            ass_path = None
            if subtitles and subtitle_segments:
                import re as _re3
                def _ts_ass3(s):
                    h = int(s//3600); m = int((s%3600)//60); sec = s%60
                    cs = int((sec%1)*100); sec = int(sec)
                    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"
                ass_path = os.path.join(TEMP_DIR, f"_subs_{uuid.uuid4().hex[:8]}.ass")
                ass_hdr = (
                    "[Script Info]\nScriptType: v4.00+\n"
                    f"PlayResX: {vw}\nPlayResY: {vh}\nWrapStyle: 1\n\n"
                    "[V4+ Styles]\n"
                    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
                    "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
                    "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
                    "Alignment,MarginL,MarginR,MarginV,Encoding\n"
                    "Style: Default,Arial,22,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
                    "1,0,0,0,100,100,0,0,1,2,0,2,20,20,30,1\n\n"
                    "[Events]\n"
                    "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
                )
                with open(ass_path, "w", encoding="utf-8") as sf:
                    sf.write(ass_hdr)
                    for txt, ts, te in subtitle_segments:
                        safe = _re3.sub(r"[{}<>|\\]", " ", txt).strip()
                        sf.write(f"Dialogue: 0,{_ts_ass3(ts)},{_ts_ass3(te)},Default,,0,0,0,,{safe}\n")
                print(f"[INFO] ASS: {len(subtitle_segments)} entries")
            inputs, fparts = [], []
            for idx, (p, dur) in enumerate(valid_segs):
                inputs += ["-i", p]
                # FIX: loop+trim handles short clips correctly without tpad double-processing
                fparts.append(
                    f"[{idx}:v]setpts=PTS-STARTPTS,"
                    f"loop=loop=-1:size=32767:start=0,"
                    f"trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
                    f"scale={vw}:{vh}:force_original_aspect_ratio=decrease,"
                    f"pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2,fps={fps}[v{idx}]"
                )
            cin  = "".join(f"[v{i}]" for i in range(len(valid_segs)))
            fc   = ";".join(fparts) + f";{cin}concat=n={len(valid_segs)}:v=1:a=0[vcat]"
            last = "vcat"

            if ass_path:
                sp = ass_path.replace("\\", "/")
                if len(sp) > 1 and sp[1] == ":":
                    sp = sp[0] + "\\:" + sp[2:]
                fc += f";[{last}]subtitles='{sp}'[vsub]"
                last = "vsub"

            audio_input = []
            audio_map   = ["-an"]
            if _pre_audio_saved and os.path.exists(pre_audio_path):
                audio_input = ["-i", pre_audio_path]
                audio_map   = ["-map", f"{len(valid_segs)}:a", "-c:a", "copy"]

            cmd = ([ff, "-y"] + inputs + audio_input +
                   ["-filter_complex", fc, "-map", f"[{last}]", "-r", str(fps)] +
                   enc_args + audio_map + ["-movflags", "+faststart", out_path])

            res = subprocess.run(cmd, capture_output=True, timeout=600)
            if ass_path:
                try: os.remove(ass_path)
                except: pass
            if res.returncode == 0 and os.path.exists(out_path):
                print(f"[OK] {os.path.basename(out_path)}")
                return out_path
            else:
                print(f"[WARN] ffmpeg no-avatar encode failed: {res.stderr.decode(errors='replace')[-300:]}")

        # Final fallback: MoviePy encode
        print(f"[INFO] Fallback encode via moviepy...")
        tmp_video = os.path.join(TEMP_DIR, f"_raw_{uuid.uuid4().hex[:8]}.mp4")
        final.write_videofile(tmp_video, fps=fps, codec="libx264", audio=False,
                              preset="ultrafast",
                              ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "20"],
                              verbose=False, logger=None, threads=4)

        audio_path = pre_audio_path if _pre_audio_saved else None
        audio_in  = ["-i", audio_path, "-c:a", "copy"] if (audio_path and os.path.exists(audio_path)) else ["-an"]
        res = subprocess.run(
            [ff, "-y", "-i", tmp_video] + audio_in + enc_args +
            ["-movflags", "+faststart", out_path],
            capture_output=True, timeout=600)
        if res.returncode != 0:
            subprocess.run(
                [ff, "-y", "-i", tmp_video] + audio_in +
                ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", out_path],
                capture_output=True, timeout=600, check=True)

        try: os.remove(tmp_video)
        except: pass
        print(f"[OK] {os.path.basename(out_path)}")

    except Exception as e:
        print(f"[ERR] Encoding: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        for p in [pre_audio_path]:
            try:
                if os.path.exists(p): os.remove(p)
            except: pass

    try: final.close()
    except: pass
    for c in clips:
        try: c.close()
        except: pass

    _COMP_TMPS.clear()
    cleanup_temp(max_age_hours=0)

    return out_path


# ============================================================
#  TEMP CLEANUP
# ============================================================
def cleanup_temp(max_age_hours: float = 0) -> int:
    patterns = ("_av_", "_wav2lip_", "tmp-", "_bg_", "_comp_", "_subs_",
                "_preaudio_", "_alist_", "_av_rgba_", "_raw_")
    cutoff = time.time() - (max_age_hours * 3600) if max_age_hours > 0 else None
    deleted = 0
    try:
        for fname in os.listdir(TEMP_DIR):
            if not any(fname.startswith(p) for p in patterns):
                continue
            fpath = os.path.join(TEMP_DIR, fname)
            if cutoff and os.path.getmtime(fpath) > cutoff:
                continue
            try:
                os.remove(fpath)
                deleted += 1
            except Exception as e:
                print(f"[WARN] Could not delete {fname}: {e}")
    except Exception as e:
        print(f"[WARN] Temp cleanup failed: {e}")
    if deleted:
        print(f"[OK] Cleaned up {deleted} temp file(s)")
    return deleted


if __name__ == "__main__":
    print("=" * 70)
    print("AI Text-to-Video Utils v14 (patched)")
    print("=" * 70)
    print(f"Groq:         {'OK' if groq_available       else 'MISSING'}")
    print(f"ElevenLabs:   {'OK' if elevenlabs_available  else 'MISSING'}")
    print(f"Cloudflare:   {'OK' if client['available']   else 'MISSING'}")
    print(f"ffmpeg:       {FFMPEG_PATH or 'MISSING'}")
    print(f"GPU:          PyTorch CUDA — {GPU_NAME}")
    print(f"Encoder:      {_NVENC_LABEL}")
    print("=" * 70)
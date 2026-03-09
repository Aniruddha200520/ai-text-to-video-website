"""
wav2lip_runner.py
Place this in E:\Projects\Wav2Lip\
Called by Flask app as a subprocess — completely isolated from project env.
"""
import argparse
import subprocess
import sys
import os
import shutil


def get_ffmpeg():
    """
    Find the best ffmpeg — prefer ffmpeg-downloader (full NVENC build)
    over wav2lip env's stripped imageio-ffmpeg (which can't do conversions).
    """
    # ffmpeg-downloader installs here
    ffdl_path = os.path.join(
        os.path.expanduser("~"),
        "AppData", "Local", "ffmpegio", "ffmpeg-downloader", "ffmpeg", "bin", "ffmpeg.exe"
    )
    if os.path.exists(ffdl_path):
        return ffdl_path

    # System PATH (may be wav2lip stripped one, but try anyway)
    ff = shutil.which("ffmpeg")
    if ff:
        return ff

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except:
        pass
    return "ffmpeg"


def convert_to_wav(audio_path, sr=16000):
    if audio_path.lower().endswith('.wav'):
        return audio_path, False

    wav_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
    os.makedirs(wav_dir, exist_ok=True)
    wav_path = os.path.join(wav_dir, 'input_audio.wav')

    ffmpeg = get_ffmpeg()
    cmd    = [ffmpeg, '-y', '-i', audio_path, '-ac', '1', '-ar', str(sr), wav_path]

    print(f"[Wav2Lip] Converting audio to wav...")
    result = subprocess.run(cmd, capture_output=True)

    if result.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
        print(f"[Wav2Lip] Audio converted OK ({os.path.getsize(wav_path)//1024}KB)")
        return wav_path, True
    else:
        print(f"[Wav2Lip] Audio conversion failed: {result.stderr.decode()}")
        return audio_path, False


def find_output(wav2lip_dir, expected_output_path):
    """
    Wav2Lip saves output to different places depending on version and input type.
    Do a broad search across all known locations.
    """
    candidates = [
        expected_output_path,
        os.path.join(wav2lip_dir, "results", "result_voice.avi"),
        os.path.join(wav2lip_dir, "results", "result_voice.mp4"),
        os.path.join(wav2lip_dir, "result_voice.avi"),
        os.path.join(wav2lip_dir, "result_voice.mp4"),
        os.path.join(wav2lip_dir, "temp", "result.avi"),
        os.path.join(wav2lip_dir, "temp", "result.mp4"),
    ]

    # Also glob search results/ for any recently created video file
    import glob, time
    now = time.time()
    for pattern in [
        os.path.join(wav2lip_dir, "results", "*.avi"),
        os.path.join(wav2lip_dir, "results", "*.mp4"),
        os.path.join(wav2lip_dir, "*.avi"),
        os.path.join(wav2lip_dir, "*.mp4"),
    ]:
        for f in glob.glob(pattern):
            # Only consider files modified in the last 5 minutes
            if os.path.exists(f) and (now - os.path.getmtime(f)) < 300:
                candidates.append(f)

    print(f"[Wav2Lip] Searching {len(candidates)} candidate locations...")
    seen = set()
    for path in candidates:
        norm = os.path.normcase(path)
        if norm in seen: continue
        seen.add(norm)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            print(f"[Wav2Lip] Found output: {path} ({os.path.getsize(path)//1024}KB)")
            return path
        elif os.path.exists(path):
            print(f"[Wav2Lip] Found but too small: {path} ({os.path.getsize(path)} bytes)")

    # Last resort: walk the entire wav2lip dir for recent video files
    print(f"[Wav2Lip] Doing full directory scan of {wav2lip_dir}...")
    for root, dirs, files in os.walk(wav2lip_dir):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'checkpoints')]
        for fname in files:
            if fname.endswith(('.avi', '.mp4')):
                fpath = os.path.join(root, fname)
                age = now - os.path.getmtime(fpath)
                if age < 300 and os.path.getsize(fpath) > 1000:
                    print(f"[Wav2Lip] Found via scan: {fpath} (age={age:.0f}s)")
                    return fpath
    return None


def convert_to_mp4(src, dst):
    """Convert .avi or any format to .mp4 using ffmpeg."""
    if src == dst:
        return True
    ffmpeg = get_ffmpeg()
    cmd = [ffmpeg, "-y", "-i", src,
           "-c:v", "libx264", "-preset", "fast", "-crf", "18",
           "-c:a", "aac", "-b:a", "128k",
           "-pix_fmt", "yuv420p", dst]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 1000:
        print(f"[Wav2Lip] Converted to mp4: {os.path.getsize(dst)//1024}KB")
        return True
    print(f"[Wav2Lip] mp4 conversion failed: {result.stderr.decode()[-200:]}")
    return False


def run(face_path, audio_path, output_path):
    wav2lip_dir = os.path.dirname(os.path.abspath(__file__))
    checkpoint  = os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth")

    wav_path, _ = convert_to_wav(audio_path)

    cmd = [
        sys.executable,
        os.path.join(wav2lip_dir, "inference.py"),
        "--checkpoint_path", checkpoint,
        "--face",    face_path,
        "--audio",   wav_path,
        "--outfile", output_path,
        "--pads",    "30", "10", "0", "0",
        "--resize_factor", "1",
        "--nosmooth",
    ]

    print(f"[Wav2Lip] Running inference...")
    result = subprocess.run(cmd, cwd=wav2lip_dir)
    print(f"[Wav2Lip] inference.py returncode={result.returncode}")

    # Find wherever wav2lip actually saved its output
    actual_output = find_output(wav2lip_dir, output_path)

    if actual_output is None:
        print(f"[Wav2Lip] No output found in any known location")
        print(f"          Searched: {output_path}")
        print(f"          Also tried: {wav2lip_dir}/results/result_voice.avi")
        return False

    print(f"[Wav2Lip] Output found at: {actual_output}")

    # If output is in wrong place or wrong format, fix it
    if os.path.normcase(actual_output) != os.path.normcase(output_path):
        print(f"[Wav2Lip] Moving/converting to expected path: {output_path}")
        if actual_output.lower().endswith('.avi'):
            # Convert avi -> mp4
            if not convert_to_mp4(actual_output, output_path):
                # fallback: just copy it with original extension
                alt_out = output_path.replace('.mp4', '.avi')
                shutil.copy2(actual_output, alt_out)
                output_path = alt_out
        else:
            shutil.copy2(actual_output, output_path)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        print(f"[Wav2Lip] Done: {os.path.getsize(output_path)//1024}KB -> {output_path}")
        return True

    print(f"[Wav2Lip] Final output missing or too small")
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--face",   required=True)
    ap.add_argument("--audio",  required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    success = run(
        os.path.abspath(args.face),
        os.path.abspath(args.audio),
        os.path.abspath(args.output)
    )
    sys.exit(0 if success else 1)
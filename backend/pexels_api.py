"""
Pexels API Integration
Fetches images and videos from Pexels stock library
"""

import os
import requests
from pathlib import Path

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# Max file size to download — 30MB is plenty for 1280x720 output
MAX_VIDEO_MB = 30
# Max resolution — no point downloading 4K when output is 720p
MAX_WIDTH    = 1920


def search_pexels_images(query, per_page=15):
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": query, "per_page": per_page, "orientation": "landscape"}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results = []
        for photo in data.get("photos", []):
            results.append({
                "id": photo["id"],
                "url": photo["src"]["large2x"],
                "thumbnail": photo["src"]["medium"],
                "photographer": photo["photographer"],
                "type": "image"
            })
        print(f"[PEXELS] Found {len(results)} images for '{query}'")
        return results
    except Exception as e:
        print(f"[ERROR] Pexels image search failed: {e}")
        return []


def _pick_best_video_file(video_files):
    """
    Pick the best video file: prefer 1080p, avoid anything over MAX_VIDEO_MB.
    Never pick 4K (width > MAX_WIDTH) unless there's no other choice.
    """
    if not video_files:
        return None

    def score(f):
        w = f.get("width", 0)
        h = f.get("height", 0)
        size_mb = f.get("file_size", 0) / (1024 * 1024) if f.get("file_size") else 999
        # Reject oversized files and 4K+ unless no choice
        if size_mb > MAX_VIDEO_MB and len(video_files) > 1:
            return -1
        if w > MAX_WIDTH and len(video_files) > 1:
            return -1
        # Score: prefer ~1920x1080, penalize huge files
        res_score = -abs(w - 1920)
        size_penalty = -size_mb * 0.5
        return res_score + size_penalty

    scored = [(score(f), f) for f in video_files]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Filter out rejected (-1) if possible
    valid = [f for s, f in scored if s >= 0]
    if valid:
        return valid[0]

    # All files were too big/large — pick smallest available
    return min(video_files, key=lambda f: f.get("file_size", 999999999))


def search_pexels_videos(query, per_page=15):
    try:
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": query, "per_page": per_page, "orientation": "landscape"}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results = []
        for video in data.get("videos", []):
            video_files = video.get("video_files", [])
            if not video_files:
                continue
            best = _pick_best_video_file(video_files)
            if not best:
                continue
            size_mb = best.get("file_size", 0) / (1024 * 1024)
            results.append({
                "id": video["id"],
                "url": best["link"],
                "thumbnail": video["image"],
                "duration": video.get("duration", 0),
                "photographer": video.get("user", {}).get("name", "Unknown"),
                "type": "video",
                "width": best.get("width", 1920),
                "height": best.get("height", 1080),
                "size_mb": round(size_mb, 1)
            })
        print(f"[PEXELS] Found {len(results)} videos for '{query}'")
        return results
    except Exception as e:
        print(f"[ERROR] Pexels video search failed: {e}")
        return []


def download_pexels_media(url, save_path, max_mb=MAX_VIDEO_MB):
    """Download with size guard — stop if file exceeds max_mb."""
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        downloaded = 0
        limit = max_mb * 1024 * 1024

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    downloaded += len(chunk)
                    if downloaded > limit:
                        print(f"[WARN] Pexels download exceeded {max_mb}MB limit, skipping")
                        f.close()
                        os.remove(save_path)
                        return {"success": False, "error": f"File too large (>{max_mb}MB)"}
                    f.write(chunk)

        mb = downloaded / (1024 * 1024)
        print(f"[PEXELS] Downloaded: {save_path} ({mb:.1f}MB)")
        return {"success": True, "path": save_path}

    except Exception as e:
        print(f"[ERROR] Pexels download failed: {e}")
        return {"success": False, "error": str(e)}


def search_and_download_image(query, scene_id, uploads_dir="uploads"):
    results = search_pexels_images(query, per_page=5)
    if not results:
        return {"success": False, "error": "No images found"}
    best_match = results[0]
    filename = f"{scene_id}_pexels.jpg"
    save_path = os.path.join(uploads_dir, filename)
    download_result = download_pexels_media(best_match["url"], save_path)
    if download_result["success"]:
        return {
            "success": True, "path": save_path,
            "url": f"/api/uploads/{filename}", "filename": filename,
            "source": "pexels", "photographer": best_match["photographer"]
        }
    return download_result


def search_and_download_video(query, scene_id, uploads_dir="uploads"):
    results = search_pexels_videos(query, per_page=5)
    if not results:
        return {"success": False, "error": "No videos found"}
    best_match = results[0]
    filename = f"{scene_id}_pexels.mp4"
    save_path = os.path.join(uploads_dir, filename)
    download_result = download_pexels_media(best_match["url"], save_path)
    if download_result["success"]:
        return {
            "success": True, "path": save_path,
            "url": f"/api/uploads/{filename}", "filename": filename,
            "duration": best_match["duration"], "source": "pexels",
            "photographer": best_match["photographer"]
        }
    return download_result
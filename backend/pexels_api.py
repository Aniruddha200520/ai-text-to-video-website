"""
Pexels API Integration
Fetches images and videos from Pexels stock library
"""

import os
import requests
from pathlib import Path

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")  # Already in your .env

def search_pexels_images(query, per_page=15):
    """
    Search Pexels for images
    
    Args:
        query: Search term
        per_page: Number of results (max 80)
    
    Returns:
        list of dicts with image data
    """
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": "landscape"  # Better for videos
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        results = []
        for photo in data.get("photos", []):
            results.append({
                "id": photo["id"],
                "url": photo["src"]["large2x"],  # High quality
                "thumbnail": photo["src"]["medium"],
                "photographer": photo["photographer"],
                "type": "image"
            })
        
        print(f"[PEXELS] Found {len(results)} images for '{query}'")
        return results
        
    except Exception as e:
        print(f"[ERROR] Pexels image search failed: {e}")
        return []


def search_pexels_videos(query, per_page=15):
    """
    Search Pexels for videos
    
    Args:
        query: Search term
        per_page: Number of results (max 80)
    
    Returns:
        list of dicts with video data
    """
    try:
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": "landscape"
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        results = []
        for video in data.get("videos", []):
            # Get best quality video file
            video_files = video.get("video_files", [])
            if not video_files:
                continue
                
            # Prefer HD quality
            hd_file = next(
                (f for f in video_files if f.get("quality") == "hd"),
                video_files[0]
            )
            
            results.append({
                "id": video["id"],
                "url": hd_file["link"],
                "thumbnail": video["image"],
                "duration": video.get("duration", 0),
                "photographer": video.get("user", {}).get("name", "Unknown"),
                "type": "video",
                "width": hd_file.get("width", 1920),
                "height": hd_file.get("height", 1080)
            })
        
        print(f"[PEXELS] Found {len(results)} videos for '{query}'")
        return results
        
    except Exception as e:
        print(f"[ERROR] Pexels video search failed: {e}")
        return []


def download_pexels_media(url, save_path):
    """
    Download image or video from Pexels
    
    Args:
        url: Media URL
        save_path: Where to save the file
    
    Returns:
        dict: {"success": bool, "path": str, "error": str}
    """
    try:
        print(f"[PEXELS] Downloading: {url}")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Save file
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"[PEXELS] ✅ Downloaded: {save_path}")
        
        return {
            "success": True,
            "path": save_path
        }
        
    except Exception as e:
        print(f"[ERROR] Pexels download failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def search_and_download_image(query, scene_id, uploads_dir="uploads"):
    """
    Search Pexels and download best matching image
    
    Returns:
        dict: {"success": bool, "path": str, "url": str, "filename": str}
    """
    # Search
    results = search_pexels_images(query, per_page=5)
    
    if not results:
        return {
            "success": False,
            "error": "No images found"
        }
    
    # Download first result
    best_match = results[0]
    filename = f"{scene_id}_pexels.jpg"
    save_path = os.path.join(uploads_dir, filename)
    
    download_result = download_pexels_media(best_match["url"], save_path)
    
    if download_result["success"]:
        return {
            "success": True,
            "path": save_path,
            "url": f"/api/uploads/{filename}",
            "filename": filename,
            "source": "pexels",
            "photographer": best_match["photographer"]
        }
    
    return download_result


def search_and_download_video(query, scene_id, uploads_dir="uploads"):
    """
    Search Pexels and download best matching video
    
    Returns:
        dict: {"success": bool, "path": str, "url": str, "filename": str, "duration": float}
    """
    # Search
    results = search_pexels_videos(query, per_page=5)
    
    if not results:
        return {
            "success": False,
            "error": "No videos found"
        }
    
    # Download first result
    best_match = results[0]
    filename = f"{scene_id}_pexels.mp4"
    save_path = os.path.join(uploads_dir, filename)
    
    download_result = download_pexels_media(best_match["url"], save_path)
    
    if download_result["success"]:
        return {
            "success": True,
            "path": save_path,
            "url": f"/api/uploads/{filename}",
            "filename": filename,
            "duration": best_match["duration"],
            "source": "pexels",
            "photographer": best_match["photographer"]
        }
    
    return download_result
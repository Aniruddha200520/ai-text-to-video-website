"""
Stable Video Diffusion - Image Animation Module
Converts static images into short animated video clips
"""

import os
import torch
import cv2
import numpy as np
from PIL import Image
from pathlib import Path

# Global pipeline (load once, reuse)
_svd_pipeline = None

def load_svd_pipeline():
    """Load SVD pipeline once and cache it"""
    global _svd_pipeline
    
    if _svd_pipeline is not None:
        return _svd_pipeline
    
    try:
        from diffusers import StableVideoDiffusionPipeline
        
        print("[SVD] Loading Stable Video Diffusion pipeline...")
        _svd_pipeline = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=torch.float16,
            variant="fp16"
        )
        _svd_pipeline.to("cuda")
        _svd_pipeline.enable_model_cpu_offload()  # Optimize memory
        print("[SVD] Pipeline loaded successfully!")
        return _svd_pipeline
        
    except Exception as e:
        print(f"[ERROR] Failed to load SVD pipeline: {e}")
        return None


def animate_image(image_path, output_path, num_frames=25, fps=7):
    """
    Animate a static image using Stable Video Diffusion
    
    Args:
        image_path: Path to input image
        output_path: Path to save output video
        num_frames: Number of frames to generate (default 25 = ~3.5 sec)
        fps: Frames per second (default 7)
    
    Returns:
        dict: {"success": bool, "path": str, "duration": float, "error": str}
    """
    try:
        # Load pipeline
        pipe = load_svd_pipeline()
        if pipe is None:
            return {
                "success": False,
                "error": "SVD pipeline not available"
            }
        
        print(f"[SVD] Animating image: {image_path}")
        
        # Load and prepare image
        image = Image.open(image_path).convert("RGB")
        
        # Resize to optimal size for SVD (width must be divisible by 8)
        # Use 1024x576 for quality, or 512x288 for speed
        target_size = (1024, 576)  # 16:9 aspect ratio
        image = image.resize(target_size, Image.LANCZOS)
        
        # Generate video frames
        print(f"[SVD] Generating {num_frames} frames...")
        frames = pipe(
            image, 
            num_frames=num_frames,
            decode_chunk_size=8,  # Lower = less VRAM, slower
            fps=fps
        ).frames[0]
        
        # Convert frames to video
        print(f"[SVD] Encoding video...")
        height, width = frames[0].size
        
        # Use H264 codec for better compatibility
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        for frame in frames:
            frame_array = np.array(frame)
            frame_bgr = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
            video.write(frame_bgr)
        
        video.release()
        
        duration = num_frames / fps
        print(f"[SVD] ✅ Video saved: {output_path} ({duration}s)")
        
        return {
            "success": True,
            "path": output_path,
            "duration": duration,
            "frames": num_frames,
            "fps": fps
        }
        
    except torch.cuda.OutOfMemoryError:
        return {
            "success": False,
            "error": "GPU out of memory. Try reducing image size or num_frames."
        }
    except Exception as e:
        print(f"[ERROR] SVD animation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def is_svd_available():
    """Check if SVD can be loaded"""
    try:
        if not torch.cuda.is_available():
            return False
        pipe = load_svd_pipeline()
        return pipe is not None
    except:
        return False


# For backward compatibility - Ken Burns effect (fallback if SVD unavailable)
def ken_burns_effect(image_path, output_path, duration=3, fps=25):
    """
    Simple zoom/pan effect on static image
    Fallback if SVD is not available
    """
    try:
        from moviepy.editor import ImageClip
        
        clip = ImageClip(image_path).set_duration(duration)
        
        # Add zoom effect
        clip = clip.resize(lambda t: 1 + 0.1 * (t / duration))
        
        clip.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio=False,
            logger=None
        )
        
        return {
            "success": True,
            "path": output_path,
            "duration": duration,
            "method": "ken_burns"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
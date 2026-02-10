#!/usr/bin/env python3
"""
Stable Video Diffusion Image Animator
ULTRA-OPTIMIZED for RTX 3050 (4GB VRAM)
"""

import torch
import numpy as np
import cv2
from PIL import Image
import os

# Global pipeline cache
_svd_pipeline = None


def is_svd_available():
    """Check if SVD can be loaded"""
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        
        # Try to load the pipeline
        pipe = load_svd_pipeline()
        return pipe is not None
    except Exception as e:
        print(f"[SVD] Not available: {e}")
        return False


def load_svd_pipeline():
    """Load SVD pipeline once and cache it"""
    global _svd_pipeline
    
    if _svd_pipeline is not None:
        return _svd_pipeline
    
    try:
        from diffusers import StableVideoDiffusionPipeline
        import torch
        
        print("[SVD] Loading Stable Video Diffusion pipeline...")
        
        # Load with optimizations for 4GB VRAM
        _svd_pipeline = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=torch.float16,
            variant="fp16",
            low_cpu_mem_usage=True
        )
        
        # Move to GPU
        _svd_pipeline.to("cuda")
        
        # CRITICAL: Enable CPU offloading to save VRAM
        _svd_pipeline.enable_model_cpu_offload()
        
        print("[SVD] Pipeline loaded successfully!")
        return _svd_pipeline
        
    except Exception as e:
        print(f"[ERROR] Failed to load SVD pipeline: {e}")
        import traceback
        traceback.print_exc()
        return None


def animate_image(image_path, output_path, num_frames=14, fps=6):
    """
    Animate a static image using Stable Video Diffusion
    ULTRA-OPTIMIZED FOR RTX 3050 (4GB VRAM)
    
    Args:
        image_path: Path to input image
        output_path: Path to save output video
        num_frames: Number of frames (14 for SVD-XT)
        fps: Frames per second (6 for smooth motion)
    
    Returns:
        dict: {"success": bool, "path": str, "duration": float, "method": str}
    """
    try:
        # Load pipeline
        pipe = load_svd_pipeline()
        if pipe is None:
            print("[SVD] Pipeline not available, using Ken Burns fallback")
            return ken_burns_effect(image_path, output_path)
        
        print(f"[SVD] Animating image: {image_path}")
        
        # Load and prepare image
        from PIL import Image as PILImage
        image = PILImage.open(image_path).convert("RGB")
        
        # CRITICAL: TINY resolution for RTX 3050
        # 320x180 is safest for 4GB VRAM
        target_width = 320
        target_height = 180
        image = image.resize((target_width, target_height), PILImage.LANCZOS)
        
        # FORCE 14 frames (SVD-XT requirement)
        num_frames = 14
        
        print(f"[SVD] Resolution: {target_width}x{target_height}")
        print(f"[SVD] Frames: {num_frames} @ {fps}fps")
        print(f"[SVD] Estimated time: 2-4 minutes on RTX 3050...")
        
        # Clear CUDA cache before generation
        torch.cuda.empty_cache()
        
        # Generate with MINIMAL settings
        with torch.inference_mode():
            frames = pipe(
                image,
                height=target_height,
                width=target_width,
                num_frames=14,  # Fixed for SVD-XT
                decode_chunk_size=2,  # Minimal - critical for 4GB
                num_inference_steps=25,  # Default
                motion_bucket_id=127,  # Default motion amount
                fps=fps
            ).frames[0]
        
        # Clear cache after generation
        torch.cuda.empty_cache()
        
        # Convert frames to video
        print(f"[SVD] Encoding video to {output_path}...")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # Use H264 codec for compatibility
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        video = cv2.VideoWriter(
            output_path, 
            fourcc, 
            fps, 
            (target_width, target_height)
        )
        
        if not video.isOpened():
            raise RuntimeError(f"Failed to open video writer for {output_path}")
        
        for idx, frame in enumerate(frames):
            # Convert PIL to numpy array
            frame_array = np.array(frame)
            # Convert RGB to BGR for OpenCV
            frame_bgr = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
            video.write(frame_bgr)
        
        video.release()
        
        duration = num_frames / fps
        print(f"[SVD] ✅ Video saved: {output_path} ({duration:.1f}s, {num_frames} frames)")
        
        return {
            "success": True,
            "path": output_path,
            "duration": duration,
            "frames": num_frames,
            "fps": fps,
            "method": "svd",
            "resolution": f"{target_width}x{target_height}"
        }
        
    except torch.cuda.OutOfMemoryError:
        print("[ERROR] GPU out of memory! Falling back to Ken Burns...")
        torch.cuda.empty_cache()
        return ken_burns_effect(image_path, output_path)
        
    except RuntimeError as e:
        if "CUDA" in str(e) or "out of memory" in str(e).lower():
            print(f"[ERROR] CUDA error: {e}")
            print("[INFO] Falling back to Ken Burns...")
            torch.cuda.empty_cache()
            return ken_burns_effect(image_path, output_path)
        raise
        
    except Exception as e:
        print(f"[ERROR] SVD animation failed: {e}")
        import traceback
        traceback.print_exc()
        print("[INFO] Falling back to Ken Burns...")
        return ken_burns_effect(image_path, output_path)


def ken_burns_effect(image_path, output_path, duration=2.0, fps=25):
    """
    Create Ken Burns effect (zoom + pan) as fallback
    INSTANT - no GPU required
    
    Args:
        image_path: Path to input image
        output_path: Path to save output video
        duration: Duration in seconds
        fps: Frames per second
    
    Returns:
        dict: {"success": bool, "path": str, "duration": float, "method": str}
    """
    try:
        print(f"[KEN BURNS] Creating zoom/pan effect for {image_path}")
        
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        height, width = img.shape[:2]
        num_frames = int(duration * fps)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not video.isOpened():
            raise RuntimeError(f"Failed to open video writer for {output_path}")
        
        # Generate frames with zoom effect
        for i in range(num_frames):
            progress = i / num_frames
            
            # Zoom in from 1.0 to 1.2
            zoom = 1.0 + (0.2 * progress)
            
            # Calculate crop region
            new_width = int(width / zoom)
            new_height = int(height / zoom)
            
            x_offset = int((width - new_width) * progress)
            y_offset = int((height - new_height) * 0.5)
            
            # Crop and resize
            cropped = img[
                y_offset:y_offset + new_height,
                x_offset:x_offset + new_width
            ]
            frame = cv2.resize(cropped, (width, height))
            
            video.write(frame)
        
        video.release()
        
        print(f"[KEN BURNS] ✅ Video saved: {output_path} ({duration}s)")
        
        return {
            "success": True,
            "path": output_path,
            "duration": duration,
            "frames": num_frames,
            "fps": fps,
            "method": "ken_burns"
        }
        
    except Exception as e:
        print(f"[ERROR] Ken Burns effect failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    # Test script
    print("Testing SVD availability...")
    available = is_svd_available()
    print(f"SVD Available: {available}")
    
    if available:
        print("\n✅ SVD is ready to use!")
        print("Resolution: 320x180 (optimized for RTX 3050)")
        print("Expected time: 2-4 minutes per animation")
    else:
        print("\n⚠️ SVD not available, will use Ken Burns effect")
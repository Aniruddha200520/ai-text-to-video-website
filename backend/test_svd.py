from diffusers import StableVideoDiffusionPipeline
from PIL import Image
import torch

# Load pipeline
pipe = StableVideoDiffusionPipeline.from_pretrained(
    "stabilityai/stable-video-diffusion-img2vid-xt",
    torch_dtype=torch.float16,
    variant="fp16"
)
pipe.to("cuda")

# Load test image
image = Image.open("uploads/test_image.png").resize((1024, 576))

# Generate video frames
print("Generating video frames...")
frames = pipe(image, num_frames=25, decode_chunk_size=8).frames[0]

# Save as video
import cv2
import numpy as np

height, width = frames[0].size
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
video = cv2.VideoWriter('test_output.mp4', fourcc, 7, (width, height))

for frame in frames:
    frame_array = np.array(frame)
    frame_bgr = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
    video.write(frame_bgr)

video.release()
print("Video saved as test_output.mp4")
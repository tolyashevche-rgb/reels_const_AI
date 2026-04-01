"""Quick FFmpeg drawtext test from Python subprocess."""
import subprocess
import os
import sys

fontfile = "C:/Windows/Fonts/arial.ttf"
# Escape for FFmpeg filter: colon needs \: 
font_escaped = fontfile.replace(":", "\\:")

text = "Привіт 🤔 світ!"
text_escaped = (
    text.replace("\\", "\\\\")
    .replace("'", "\u2019")
    .replace(":", "\\:")
    .replace("%", "%%")
)

vf = (
    f"drawtext=fontfile='{font_escaped}'"
    f":text='{text_escaped}'"
    f":fontsize=52"
    f":fontcolor=white"
    f":x=(w-text_w)/2"
    f":y=h*0.75"
)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_out.mp4")

cmd = [
    "ffmpeg", "-y",
    "-f", "lavfi",
    "-i", "color=c=0xFFF3E0:s=1080x1920:d=3:r=30",
    "-vf", vf,
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-t", "3",
    out,
]

print("CMD:", " ".join(cmd))
print("VF:", vf)
print()

r = subprocess.run(cmd, capture_output=True)
print("Return code:", r.returncode)
if r.returncode != 0:
    print("STDERR (last 500):")
    print(r.stderr.decode("utf-8", errors="replace")[-500:])
else:
    print("SUCCESS! File:", out)
    print("Size:", os.path.getsize(out), "bytes")

"""
Вузол 10: Рендер відео — FFmpeg (subprocess).
Збирає відеокліпи (реальні від TwelveLabs або кольорові плейсхолдери)
+ text overlays + voice-over.
Конфігурується через RenderConfig (формат, шрифт, переходи, аудіо).

Без Creatomate — повністю локально.
"""
import os
import json
import uuid
import subprocess
import shutil

from app.state import ReelsState
from app.twelvelabs_client import get_twelvelabs_client
from app.render_config import RenderConfig, DEFAULT_CONFIG, AMBIENT_TYPES

MEDIA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "media",
)
RENDERS_DIR = os.path.join(MEDIA_ROOT, "renders")
TRIMMED_DIR = os.path.join(MEDIA_ROOT, "trimmed_clips")

# Кольори для placeholder-кадрів (пастельні, приємні для дитячої тематики)
PALETTE = [
    "#FFF3E0",  # warm peach
    "#E8F5E9",  # soft green
    "#E3F2FD",  # light blue
    "#FFF9C4",  # warm yellow
    "#F3E5F5",  # lavender
    "#FFEBEE",  # soft pink
    "#E0F7FA",  # mint
    "#FBE9E7",  # apricot
]

# Шрифт для тексту (системний fallback)
FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _find_font() -> str:
    """Знаходить перший доступний шрифт."""
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return f.replace("\\", "/").replace(":", "\\:")
    return "arial"


def _escape_text(text: str) -> str:
    """Escape тексту для FFmpeg drawtext."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\u2019")
        .replace(":", "\\:")
        .replace("%", "%%")
    )


def _hex_to_ffmpeg(hex_color: str) -> str:
    """#RRGGBB → 0xRRGGBB для FFmpeg."""
    return "0x" + hex_color.lstrip("#")


def _get_selected_asset(shot_order: int, selected_assets: list) -> dict | None:
    """Знаходить обраний кліп для даного shot."""
    for sa in selected_assets:
        if sa.get("shot_order") == shot_order and sa.get("selected"):
            return sa["selected"]
    return None


def _download_and_trim_clip(
    video_id: str,
    index_id: str,
    start: float,
    end: float,
    duration_needed: float,
    output_path: str,
    cfg: RenderConfig = DEFAULT_CONFIG,
) -> bool:
    """
    Завантажує відео з TwelveLabs через HLS URL і обрізає потрібний фрагмент.
    Масштабує до цільового формату з crop/pad.
    Повертає True якщо успішно.
    """
    client = get_twelvelabs_client()
    if client is None:
        return False

    w, h = cfg.video.resolved_width, cfg.video.resolved_height

    try:
        video_info = client.indexes.videos.retrieve(
            index_id=index_id,
            video_id=video_id,
        )
        hls_obj = getattr(video_info, "hls", None)
        hls_url = None
        if hls_obj and hasattr(hls_obj, "video_url"):
            hls_url = hls_obj.video_url

        if not hls_url or not isinstance(hls_url, str):
            return False

        trim_duration = min(end - start, duration_needed)
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(hls_url),
            "-ss", str(start),
            "-t", str(trim_duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(cfg.video.crf),
            "-an",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=90)
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")[-1000:]
            print(f"[render] _download_and_trim_clip ffmpeg error: {stderr_text}")
            return False
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1024

    except Exception as exc:
        print(f"[render] _download_and_trim_clip exception: {exc}")
        return False


def _build_shot_clip(
    shot: dict,
    index: int,
    font: str,
    output_path: str,
    base_clip: str | None = None,
    cfg: RenderConfig = DEFAULT_CONFIG,
) -> str:
    """
    Генерує один кадр як mp4.
    Якщо base_clip є — накладає text overlay на реальне відео.
    Якщо нема — використовує кольоровий placeholder.
    """
    w, h = cfg.video.resolved_width, cfg.video.resolved_height
    fps = cfg.video.fps
    crf = cfg.video.crf
    tc = cfg.text

    duration = shot.get("duration_sec", 3)
    color = PALETTE[index % len(PALETTE)]

    # Швидкість відтворення
    speed = cfg.video.speed
    speed_filter = f"setpts={1.0/speed}*PTS" if speed != 1.0 else None

    filter_parts = []

    # Текст overlay прибраний звідси — накладається окремо на фінальне відео
    # через _apply_text_overlays() з time-based enable

    # Description (менший текст зверху) — тільки для placeholder
    if not base_clip:
        desc = shot.get("description", "")
        if desc:
            short_desc = desc[:60] + "..." if len(desc) > 60 else desc
            escaped_desc = _escape_text(short_desc)
            filter_parts.append(
                f"drawtext=fontfile='{font}'"
                f":text='{escaped_desc}'"
                f":fontsize={tc.font_size_desc}"
                f":fontcolor={tc.font_color}@0.7"
                f":borderw={max(1, tc.border_width - 1)}"
                f":bordercolor={tc.border_color}@0.4"
                f":x=(w-text_w)/2"
                f":y=h*{tc.position_y_desc}"
            )

    if speed_filter:
        filter_parts.insert(0, speed_filter)

    vf = ",".join(filter_parts) if filter_parts else "null"

    if base_clip and os.path.exists(base_clip):
        vf_real = vf if vf != "null" else "null"
        cmd = [
            "ffmpeg", "-y",
            "-i", base_clip,
            "-vf", vf_real,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf),
            "-r", str(fps),
            "-t", str(duration),
            "-an",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={_hex_to_ffmpeg(color)}:s={w}x{h}:d={duration}:r={fps}",
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf),
            "-t", str(duration),
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return output_path


def _concat_clips(clip_paths: list[str], output_path: str,
                   cfg: RenderConfig = DEFAULT_CONFIG) -> None:
    """
    Конкатенує кліпи з xfade переходами між ними.
    Тип переходу та тривалість беруться з cfg.video.
    """
    if len(clip_paths) == 1:
        cmd = ["ffmpeg", "-y", "-i", clip_paths[0], "-c", "copy", output_path]
        subprocess.run(cmd, capture_output=True, check=True)
        return

    transition_type = cfg.video.transition
    transition_dur = cfg.video.transition_duration
    fps = cfg.video.fps
    crf = cfg.video.crf

    def get_duration(path: str) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True,
        )
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 3.0

    durations = [get_duration(p) for p in clip_paths]

    n = len(clip_paths)
    inputs = []
    for p in clip_paths:
        inputs += ["-i", p]

    filter_parts = []
    offset = 0.0
    prev_label = "0:v"

    for i in range(1, n):
        offset += durations[i - 1] - transition_dur
        out_label = f"v{i:02d}"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition={transition_type}"
            f":duration={transition_dur}:offset={offset:.3f}[{out_label}]"
        )
        prev_label = out_label

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{prev_label}]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(crf),
        "-r", str(fps),
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def _generate_ambient(duration: float, output_path: str,
                      cfg: RenderConfig = DEFAULT_CONFIG) -> bool:
    """
    Генерує ambient-фон через FFmpeg.
    Використовує акорди (кілька частот) для музичного звучання.
    """
    ambient_info = AMBIENT_TYPES.get(cfg.audio.ambient_type, AMBIENT_TYPES["calm"])
    freqs = ambient_info.get("frequencies", [220])

    # Будуємо вираз для aevalsrc: сума синусоїд / кількість (нормалізація)
    amplitude = 0.03 / max(len(freqs), 1)
    sine_terms = "+".join(f"sin({f}*2*PI*t)" for f in freqs)
    expr = f"{amplitude}*({sine_terms})"

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"aevalsrc={expr}:s=44100:d={duration}",
            "-af", (
                "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                "tremolo=f=0.3:d=0.5,"
                "lowpass=f=500,"
                "afade=t=in:ss=0:d=2,"
                f"afade=t=out:st={max(0, duration - 2)}:d=2"
            ),
            "-c:a", "aac",
            "-b:a", "64k",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return os.path.exists(output_path)
    except Exception:
        return False


def _mix_audio(video_path: str, voice_path: str, output_path: str,
               ambient_path: str | None = None,
               cfg: RenderConfig = DEFAULT_CONFIG) -> None:
    """
    Мікшує voice-over + опційний ambient-трек з відео.
    Гучності беруться з cfg.audio.
    """
    vv = cfg.audio.voice_volume
    av = cfg.audio.ambient_volume
    bitrate = cfg.audio.audio_bitrate

    if ambient_path and os.path.exists(ambient_path):
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", voice_path,
            "-i", ambient_path,
            "-filter_complex",
            f"[1:a]volume={vv}[voice];[2:a]volume={av}[ambient];[voice][ambient]amix=inputs=2:duration=shortest[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", bitrate,
            "-shortest",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", voice_path,
            "-filter_complex",
            f"[1:a]volume={vv}[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", bitrate,
            "-shortest",
            output_path,
        ]
    subprocess.run(cmd, capture_output=True, check=True)


def _wrap_text(text: str, max_chars: int = 28) -> str:
    """Word-wrap: розбиває текст на рядки по max_chars символів."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return "\n".join(lines)


def _apply_text_overlays(
    video_path: str,
    shot_list: list[dict],
    font: str,
    output_path: str,
    script: dict | None = None,
    cfg: RenderConfig = DEFAULT_CONFIG,
) -> str:
    """
    Накладає text overlays на ФІНАЛЬНЕ відео.
    Текст береться зі скрипту (script.text_overlays) — не з кадрів.
    Рівномірно розподіляється на всю тривалість відео.
    """
    tc = cfg.text

    # Отримуємо тривалість відео через ffprobe
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=10,
        )
        video_duration = float(probe.stdout.strip())
    except Exception:
        video_duration = sum(s.get("duration_sec", 3) for s in shot_list)

    # Беремо overlays зі скрипту (оригінальні), не з shot_list
    overlays: list[str] = []
    if script:
        overlays = [t.strip() for t in script.get("text_overlays", []) if t.strip()]
    if not overlays:
        # Fallback: збираємо з shot_list
        overlays = [s.get("text_overlay", "").strip() for s in shot_list
                    if s.get("text_overlay", "").strip()]
    if not overlays:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-c", "copy", output_path],
            capture_output=True, check=True,
        )
        return output_path

    # Рівномірно розподіляємо overlays на всю тривалість відео
    n = len(overlays)
    segment = video_duration / n
    gap = 0.3  # пауза між текстами для плавності

    filters: list[str] = []
    for i, text in enumerate(overlays):
        t_in  = i * segment + (gap if i > 0 else 0)
        t_out = (i + 1) * segment
        if t_out > video_duration:
            t_out = video_duration

        escaped = _escape_text(_wrap_text(text))
        fc = f"{tc.font_color}@{tc.font_color_opacity}" if tc.font_color_opacity < 1.0 else tc.font_color
        bc = f"{tc.border_color}@{tc.border_opacity}"
        enable = f"'gte(t,{t_in:.3f})*lte(t,{t_out:.3f})'"

        # Рахуємо кількість рядків для висоти box
        num_lines = _wrap_text(text).count("\n") + 1
        line_h = int(tc.font_size * 1.3)
        padding = 14
        box_h   = line_h * num_lines + padding * 2
        box_y   = f"h*{tc.position_y}-{padding}"

        filters.append(
            f"drawbox=x=0:y={box_y}:w=iw:h={box_h}"
            f":color=black@0.48:t=fill:enable={enable}"
        )
        filters.append(
            f"drawtext=fontfile='{font}'"
            f":text='{escaped}'"
            f":fontsize={tc.font_size}"
            f":fontcolor={fc}"
            f":borderw={tc.border_width}"
            f":bordercolor={bc}"
            f":x=(w-text_w)/2"
            f":y=h*{tc.position_y}"
            f":enable={enable}"
        )

    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(cfg.video.crf),
        "-r", str(cfg.video.fps),
        "-an",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise subprocess.CalledProcessError(
            result.returncode, cmd, stderr=result.stderr
        )
    return output_path


def render_compose(state: ReelsState) -> dict:
    """
    Вузол 10: Збирає фінальне відео з кадрів + voice-over.
    Читає render_config зі state (або дефолт).
    """
    shot_list = state.get("shot_list", [])
    if not shot_list:
        return {"errors": ["render_compose: no shot_list"]}

    # Конфіг рендеру (з state або дефолт)
    cfg = RenderConfig.from_dict(state.get("render_config"))

    voice_track = state.get("voice_track", "")
    project_id = state.get("project_id", uuid.uuid4().hex[:8])
    selected_assets = state.get("selected_assets", [])

    w, h = cfg.video.resolved_width, cfg.video.resolved_height
    print(f"[render] Config: {w}x{h} {cfg.video.fps}fps, "
          f"transition={cfg.video.transition}/{cfg.video.transition_duration}s, "
          f"speed={cfg.video.speed}x, crf={cfg.video.crf}")

    os.makedirs(RENDERS_DIR, exist_ok=True)
    os.makedirs(TRIMMED_DIR, exist_ok=True)

    # Шрифт: з конфігу або auto-detect
    if cfg.text.font and os.path.exists(cfg.text.font):
        font = cfg.text.font.replace("\\", "/").replace(":", "\\:")
    else:
        font = _find_font()

    # 1. Генеруємо кожен кадр (реальний кліп або placeholder)
    clip_paths = []
    real_count = 0
    placeholder_count = 0
    render_warnings = []

    for i, shot in enumerate(shot_list):
        clip_path = os.path.join(TRIMMED_DIR, f"{project_id}_shot_{i:02d}.mp4")
        base_clip = None

        asset = _get_selected_asset(shot.get("order", i + 1), selected_assets)
        if asset:
            raw_path = os.path.join(
                TRIMMED_DIR, f"{project_id}_raw_{i:02d}.mp4"
            )
            ok = _download_and_trim_clip(
                video_id=asset["video_id"],
                index_id=asset["index_id"],
                start=asset.get("start", 0),
                end=asset.get("end", shot.get("duration_sec", 3)),
                duration_needed=shot.get("duration_sec", 3),
                output_path=raw_path,
                cfg=cfg,
            )
            if ok:
                base_clip = raw_path

        try:
            _build_shot_clip(shot, i, font, clip_path,
                             base_clip=base_clip, cfg=cfg)
            if base_clip:
                real_count += 1
            else:
                placeholder_count += 1
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            warn = f"Shot {i+1}: real clip failed ({stderr[-300:]}), using placeholder"
            render_warnings.append(warn)
            print(f"[render] {warn}")
            try:
                _build_shot_clip(shot, i, font, clip_path,
                                 base_clip=None, cfg=cfg)
                placeholder_count += 1
            except subprocess.CalledProcessError as e2:
                stderr2 = e2.stderr.decode("utf-8", errors="replace") if e2.stderr else str(e2)
                return {"errors": [f"render_compose shot {i+1} placeholder error: {stderr2[-500:]}"]}

        clip_paths.append(clip_path)

    print(f"[render] Shots done: {real_count} real, {placeholder_count} placeholder")

    # 2. Конкатенуємо кадри
    concat_path = os.path.join(RENDERS_DIR, f"{project_id}_concat.mp4")
    try:
        _concat_clips(clip_paths, concat_path, cfg=cfg)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return {"errors": [f"render_compose concat error: {stderr[-500:]}"]}

    # 2.5. Накладаємо text overlays на фінальне відео (незалежний шар)
    script = state.get("script", {})
    text_path = os.path.join(RENDERS_DIR, f"{project_id}_text.mp4")
    try:
        _apply_text_overlays(concat_path, shot_list, font, text_path,
                             script=script, cfg=cfg)
        os.remove(concat_path)
        concat_path = text_path
        print(f"[render] Text overlays накладено на фінальне відео")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        print(f"[render] Text overlay warning: {stderr[-300:]} — продовжуємо без тексту")

    # 3. Генеруємо/підготовлюємо фонову музику
    ambient_path = None
    if cfg.audio.ambient_enabled:
        ambient_path = os.path.join(RENDERS_DIR, f"{project_id}_ambient.aac")
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", concat_path],
                capture_output=True, text=True, timeout=10,
            )
            video_duration = float(probe.stdout.strip())
        except Exception:
            video_duration = sum(s.get("duration_sec", 3) for s in shot_list)

        ambient_ok = _generate_ambient(video_duration, ambient_path, cfg=cfg)
        if ambient_ok:
            print(f"[render] Ambient ({cfg.audio.ambient_type}): {video_duration:.1f}s")
        else:
            print("[render] Ambient generation skipped")
            ambient_path = None

    # 4. Мікс з voice-over + ambient (якщо є)
    final_path = os.path.join(RENDERS_DIR, f"{project_id}_final.mp4")
    if voice_track and os.path.exists(voice_track):
        try:
            _mix_audio(concat_path, voice_track, final_path,
                       ambient_path=ambient_path, cfg=cfg)
            os.remove(concat_path)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            # Fallback — відео без аудіо
            shutil.move(concat_path, final_path)
            return {
                "render_output": final_path,
                "errors": [f"render_compose audio mix warning: {stderr[-300:]}"],
            }
    else:
        shutil.move(concat_path, final_path)

    # 5. Cleanup temp clips + ambient
    for p in clip_paths:
        if os.path.exists(p):
            os.remove(p)
    if ambient_path and os.path.exists(ambient_path):
        os.remove(ambient_path)

    result = {"render_output": final_path}
    if render_warnings:
        result["errors"] = render_warnings
    return result

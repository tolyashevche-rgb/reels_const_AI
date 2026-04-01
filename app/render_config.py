"""
Конфігурація рендеру відео — всі налаштування, які можна змінювати через API.
Дефолти оптимізовані для Instagram Reels (9:16, 30fps).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


# ── Пресети розмірів ──

FORMAT_PRESETS: dict[str, tuple[int, int]] = {
    "reels":     (1080, 1920),   # 9:16 — Instagram Reels / TikTok / Shorts
    "square":    (1080, 1080),   # 1:1  — Instagram post
    "landscape": (1920, 1080),   # 16:9 — YouTube / горизонтальне
    "story":     (1080, 1920),   # alias для reels
}

# ── Доступні xfade transitions (FFmpeg) ──

XFADE_TRANSITIONS = [
    "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "circlecrop", "rectcrop", "circleopen", "circleclose",
    "dissolve", "pixelize", "diagtl", "diagtr", "diagbl", "diagbr",
    "hlslice", "hrslice", "vuslice", "vdslice",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
]

# ── Типи ambient (акорди — кілька частот для музичного звучання) ──

AMBIENT_TYPES = {
    "calm":    {"frequencies": [220, 262, 330], "description": "Am chord, м'який пад"},
    "lullaby": {"frequencies": [262, 330, 392], "description": "C major, ніжна колискова"},
    "deep":    {"frequencies": [110, 165, 220], "description": "Низький A5, глибокий бас"},
    "bright":  {"frequencies": [220, 277, 330, 440], "description": "A major, яскравий"},
    "sine":    {"frequencies": [220], "description": "Один тон (legacy)"},
}


@dataclass
class VideoConfig:
    """Налаштування відео-формату та ефектів."""
    format: str = "reels"               # preset name або "custom"
    width: int = 1080                    # тільки для format="custom"
    height: int = 1920                   # тільки для format="custom"
    fps: int = 30                        # кадрів на секунду
    speed: float = 1.0                   # швидкість відтворення (0.5 – 2.0)
    crf: int = 23                        # якість (0=lossless, 51=worst; 18-28 типово)
    transition: str = "fade"             # тип xfade переходу
    transition_duration: float = 0.3     # тривалість переходу (сек)

    @property
    def resolved_width(self) -> int:
        if self.format in FORMAT_PRESETS:
            return FORMAT_PRESETS[self.format][0]
        return self.width

    @property
    def resolved_height(self) -> int:
        if self.format in FORMAT_PRESETS:
            return FORMAT_PRESETS[self.format][1]
        return self.height


@dataclass
class TextConfig:
    """Налаштування тексту (overlay)."""
    font: str = ""                       # шлях до шрифту (пусто = auto-detect)
    font_size: int = 58                  # розмір основного overlay
    font_size_desc: int = 28             # розмір description (placeholder)
    font_color: str = "white"            # колір тексту
    font_color_opacity: float = 1.0      # прозорість (0.0 – 1.0)
    border_width: int = 2                # обводка (px)
    border_color: str = "black"          # колір обводки
    border_opacity: float = 0.5          # прозорість обводки
    position_y: float = 0.67            # позиція тексту по Y (0.0=верх, 1.0=низ)
    position_y_desc: float = 0.15       # позиція description по Y


@dataclass
class AudioConfig:
    """Налаштування аудіо (voice + ambient)."""
    voice_volume: float = 1.0            # гучність voice-over (0.0 – 2.0)
    ambient_enabled: bool = True         # вкл/викл ambient
    ambient_volume: float = 0.15         # гучність ambient (0.0 – 1.0)
    ambient_type: str = "calm"           # тип ambient (calm, lullaby, deep, bright, sine)
    audio_bitrate: str = "192k"          # бітрейт фінального аудіо


@dataclass
class RenderConfig:
    """Повна конфігурація рендеру. Серіалізується в/з dict для передачі через state."""
    video: VideoConfig = field(default_factory=VideoConfig)
    text: TextConfig = field(default_factory=TextConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "RenderConfig":
        if not data:
            return cls()
        video_data = data.get("video", {})
        text_data = data.get("text", {})
        audio_data = data.get("audio", {})
        return cls(
            video=VideoConfig(**{k: v for k, v in video_data.items()
                                 if k in VideoConfig.__dataclass_fields__}),
            text=TextConfig(**{k: v for k, v in text_data.items()
                               if k in TextConfig.__dataclass_fields__}),
            audio=AudioConfig(**{k: v for k, v in audio_data.items()
                                 if k in AudioConfig.__dataclass_fields__}),
        )


# ── Дефолтна конфігурація ──

DEFAULT_CONFIG = RenderConfig()

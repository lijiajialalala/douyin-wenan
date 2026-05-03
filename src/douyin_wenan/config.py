from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    legacy_input_root: Path
    runtime_root: Path
    manifest_path: Path
    source_links_dir: Path
    raw_video_dir: Path
    raw_audio_dir: Path
    asr_text_dir: Path
    corpus_dir: Path
    analysis_dir: Path
    logs_dir: Path
    asr_provider: str
    asr_model: str
    asr_base_url: str
    asr_api_key_env: str
    text_correction_enabled: bool
    text_correction_provider: str
    text_correction_model: str
    text_correction_base_url: str
    text_correction_api_key_env: str
    text_correction_max_char_delta_ratio: float
    text_correction_max_edit_count: int


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _parse_boolish(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def _parse_floatish(value: object, *, default: float) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_intish(value: object, *, default: int) -> int:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _parse_two_level_yaml(path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())

        if indent == 0:
            if value == "":
                current_section = key
                data[current_section] = {}
            else:
                current_section = None
                data[key] = value
            continue

        if indent == 2 and current_section:
            section = data.setdefault(current_section, {})
            if isinstance(section, dict):
                section[key] = value

    return data


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    root = repo_root()
    local = root / "configs" / "local.yaml"
    if local.exists():
        return local
    return root / "configs" / "local.example.yaml"


def load_runtime_config(config_path: Path | None = None) -> RuntimeConfig:
    path = config_path or default_config_path()
    raw = _parse_two_level_yaml(path)

    runtime = raw.get("runtime", {})
    asr = raw.get("asr", {})
    correction = raw.get("correction", {})

    if not isinstance(runtime, dict) or not isinstance(asr, dict) or not isinstance(correction, dict):
        raise ValueError(f"Invalid config structure: {path}")

    legacy_input_root = Path(str(raw.get("legacy_input_root", "."))).expanduser()
    runtime_root = Path(str(raw.get("runtime_root", repo_root() / "data" / "runtime"))).expanduser()
    manifest_path = Path(str(runtime.get("manifest_path", runtime_root / "manifest" / "douyin_manifest.csv"))).expanduser()
    source_links_dir = Path(str(runtime.get("source_links_dir", runtime_root / "ingest" / "source_links"))).expanduser()
    raw_video_dir = Path(str(runtime.get("raw_video_dir", runtime_root / "assets" / "raw_videos"))).expanduser()
    raw_audio_dir = Path(str(runtime.get("raw_audio_dir", runtime_root / "assets" / "raw_audio"))).expanduser()
    asr_text_dir = Path(str(runtime.get("asr_text_dir", runtime_root / "snapshots" / "asr_text"))).expanduser()
    corpus_dir = Path(str(runtime.get("corpus_dir", runtime_root / "corpus"))).expanduser()
    analysis_dir = Path(str(runtime.get("analysis_dir", runtime_root / "analysis"))).expanduser()
    logs_dir = Path(str(runtime.get("logs_dir", runtime_root / "logs"))).expanduser()
    asr_provider = str(asr.get("provider", "siliconflow")).strip() or "siliconflow"
    asr_model = str(asr.get("model", "")).strip()
    asr_base_url = str(asr.get("base_url", "https://api.siliconflow.cn")).strip() or "https://api.siliconflow.cn"
    asr_api_key_env = str(asr.get("api_key_env", "SILICONFLOW_API_KEY")).strip() or "SILICONFLOW_API_KEY"
    text_correction_enabled = _parse_boolish(correction.get("enabled"), default=False)
    text_correction_provider = str(correction.get("provider", "openai")).strip() or "openai"
    text_correction_model = str(correction.get("model", "")).strip()
    text_correction_base_url = (
        str(correction.get("base_url", "https://api.openai.com")).strip() or "https://api.openai.com"
    )
    text_correction_api_key_env = (
        str(correction.get("api_key_env", "OPENAI_API_KEY")).strip() or "OPENAI_API_KEY"
    )
    text_correction_max_char_delta_ratio = _parse_floatish(
        correction.get("max_char_delta_ratio"),
        default=0.08,
    )
    text_correction_max_edit_count = _parse_intish(correction.get("max_edit_count"), default=40)

    return RuntimeConfig(
        legacy_input_root=legacy_input_root,
        runtime_root=runtime_root,
        manifest_path=manifest_path,
        source_links_dir=source_links_dir,
        raw_video_dir=raw_video_dir,
        raw_audio_dir=raw_audio_dir,
        asr_text_dir=asr_text_dir,
        corpus_dir=corpus_dir,
        analysis_dir=analysis_dir,
        logs_dir=logs_dir,
        asr_provider=asr_provider,
        asr_model=asr_model,
        asr_base_url=asr_base_url,
        asr_api_key_env=asr_api_key_env,
        text_correction_enabled=text_correction_enabled,
        text_correction_provider=text_correction_provider,
        text_correction_model=text_correction_model,
        text_correction_base_url=text_correction_base_url,
        text_correction_api_key_env=text_correction_api_key_env,
        text_correction_max_char_delta_ratio=text_correction_max_char_delta_ratio,
        text_correction_max_edit_count=text_correction_max_edit_count,
    )

"""配置加载与诊断 — 只处理 yaml/json 读取，不关心业务逻辑。"""

import json
from pathlib import Path

import yaml


class ConfigLoader:
    """统一从 project_dir 加载所有配置。"""

    def __init__(self, project_dir: str | Path):
        self._project_dir = Path(project_dir)
        self._data_dir = self._project_dir / "data"
        self._config = self._load_yaml()
        self._validate()

    def _load_yaml(self) -> dict:
        path = self._project_dir / "config.yaml"
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            return {}

    def _validate(self):
        """构造时做必要校验，缺核心配置直接抛。"""
        tw_cfg = self._config.get("twitter", {})
        bearer = tw_cfg.get("bearer", "")
        if not bearer:
            raise ValueError("config.yaml 中 twitter.bearer 未配置")

    # ── 便捷访问器 ──────────────────────────────────────────────────

    @property
    def twitter(self) -> dict:
        return self._config.get("twitter", {})

    @property
    def tts(self) -> dict:
        return self._config.get("tts", {})

    @property
    def paths(self) -> dict:
        return self._config.get("paths", {})

    @property
    def bearer(self) -> str:
        return self.twitter.get("bearer", "")

    @property
    def tweet_detail_query_id(self) -> str:
        return self.twitter.get("tweet_detail_query_id", "_i0BBmP_dK_ZLFa2Y-ei9Q")

    @property
    def tweet_result_query_id(self) -> str:
        return self.twitter.get("tweet_result_by_rest_id_query_id", "uEyKTt72BfzaY84WLGC5Dw")

    @property
    def rate_limit_seconds(self) -> int:
        return self.twitter.get("rate_limit_seconds", 5)

    @property
    def rate_limit_margin(self) -> float:
        return self.twitter.get("rate_limit_margin", 0.1)

    @property
    def voices(self) -> dict:
        return self.tts.get("voices", {"zh": "zh-CN-XiaoxiaoNeural", "en": "en-US-JennyNeural"})

    @property
    def default_rate(self) -> str:
        return self.tts.get("default_rate", "+20%")

    @property
    def max_filename_len(self) -> int:
        return self.tts.get("max_filename_len", 30)

    @property
    def audio_dir(self) -> Path:
        return self._data_dir / self.paths.get("audio_dir", "twts")

    @property
    def index_path(self) -> Path:
        return self._data_dir / self.paths.get("index_file", "twts/index.json")

    @property
    def cookie_path(self) -> Path:
        return self._data_dir / self.paths.get("cookie_file", "secrets/x_cookies.json")

    # ── Cookie ──────────────────────────────────────────────────────

    def load_cookies(self) -> dict:
        """加载 X cookie 文件。文件缺失或格式错误抛异常。"""
        if not self.cookie_path.exists():
            raise FileNotFoundError(f"Cookie 文件未找到: {self.cookie_path}")
        with open(self.cookie_path) as f:
            return json.load(f)

    # ── 诊断 ────────────────────────────────────────────────────────

    def diagnose(self) -> dict:
        """返回完整诊断结果，不抛异常。"""
        status = {"ok": True, "checks": {}}

        # Cookie
        try:
            cookies = self.load_cookies()
            missing = [k for k in ("auth_token", "ct0", "twid") if not cookies.get(k)]
            if missing:
                status["checks"]["cookie"] = {"ok": False, "msg": f"缺少: {', '.join(missing)}"}
                status["ok"] = False
            else:
                status["checks"]["cookie"] = {"ok": True}
        except FileNotFoundError as e:
            status["checks"]["cookie"] = {"ok": False, "msg": str(e)}
            status["ok"] = False
        except json.JSONDecodeError:
            status["checks"]["cookie"] = {"ok": False, "msg": "Cookie 文件格式错误"}
            status["ok"] = False

        # TTS 依赖
        try:
            import edge_tts  # noqa: F401
            status["checks"]["edge_tts"] = {"ok": True}
        except ImportError:
            status["checks"]["edge_tts"] = {"ok": False, "msg": "edge-tts 未安装"}
            status["ok"] = False

        # 配置完整性
        status["checks"]["config"] = {"ok": True, "bearer_configured": bool(self.bearer)}

        return status

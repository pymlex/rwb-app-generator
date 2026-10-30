import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str = "qwen3.8-27b"
    timeout: float = 600
    max_output_tokens: int = 14000
    max_repairs: int = 2

    @classmethod
    def from_env(cls):
        model = os.environ.get("QWEN_MODEL", "qwen3.8-27b")
        if model != "qwen3.8-27b":
            raise ValueError("The competition model must be qwen3.8-27b")
        return cls(
            base_url=os.environ["QWEN_BASE_URL"].rstrip("/"),
            api_key=os.environ["QWEN_API_KEY"],
            model=model,
            timeout=float(os.environ.get("QWEN_TIMEOUT", "600")),
            max_output_tokens=int(os.environ.get("RWB_MAX_OUTPUT_TOKENS", "14000")),
            max_repairs=int(os.environ.get("RWB_MAX_REPAIRS", "2")),
        )

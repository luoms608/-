from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SOURCES_DIR = BASE_DIR / "sources"
VOICES_DIR = BASE_DIR / "voices"
OUTPUT_DIR = BASE_DIR / "output"
PERSONA_PATH = BASE_DIR / "persona.txt"

OLLAMA_BASE_URL = "http://localhost:11434"#修改为你自己的 Ollama 服务器地址
OLLAMA_MODEL = "qwen3-coder:480b-cloud"#修改为你自己的模型名称

GPT_SOVITS_GPT_WEIGHTS = Path(
	"E:/gpt-sovits/GPT-SoVITS-v2pro-20250604/GPT_weights_v2Pro/www-e10.ckpt"#修改为你自己的权重路径 
)
GPT_SOVITS_SOVITS_WEIGHTS = Path(
	"E:/gpt-sovits/GPT-SoVITS-v2pro-20250604/SoVITS_weights_v2Pro/www_e4_s176.pth" #修改为你自己的权重路径  
)



from __future__ import annotations

import json
import os
import random
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TTSConfig:
	endpoint_url: str
	method: str = "GET"  # "GET" or "POST_JSON"
	text_lang: str = "ja"
	ref_audio_path: str = ""
	ref_audio_dir: str = "voices"
	ref_min_seconds: float = 3.0
	ref_max_seconds: float = 10.0
	prompt_lang: str = "ja"
	prompt_text: str = ""
	media_type: str = "wav"
	streaming_mode: bool = False
	text_split_method: str = "cut5"
	batch_size: int = 1
	batch_threshold: float = 0.75
	split_bucket: bool = True
	speed_factor: float = 1.0
	repetition_penalty: float = 1.35
	output_path: str = "output"
	timeout_seconds: int = 60
	extra_params: Dict[str, str] = field(default_factory=dict)


def synthesize(text: str, config: TTSConfig) -> str:
	if not config.endpoint_url:
		raise ValueError("endpoint_url is required")
	if not config.ref_audio_path:
		config.ref_audio_path = _pick_random_ref_audio(
			config.ref_audio_dir,
			min_seconds=config.ref_min_seconds,
			max_seconds=config.ref_max_seconds,
		)
		if not config.ref_audio_path:
			raise ValueError("ref_audio_path is required")
	config.ref_audio_path = _resolve_path(config.ref_audio_path)
	if not config.prompt_lang:
		raise ValueError("prompt_lang is required")
	print(
		"[tts] request",
		{
			"url": config.endpoint_url,
			"text_lang": config.text_lang,
			"prompt_lang": config.prompt_lang,
			"ref_audio_path": config.ref_audio_path,
			"media_type": config.media_type,
		},
	)
	params = {
		"text": text,
		"text_lang": config.text_lang,
		"ref_audio_path": config.ref_audio_path,
		"prompt_lang": config.prompt_lang,
		"prompt_text": config.prompt_text,
		"media_type": config.media_type,
		"streaming_mode": config.streaming_mode,
		"text_split_method": config.text_split_method,
		"batch_size": config.batch_size,
		"batch_threshold": config.batch_threshold,
		"split_bucket": config.split_bucket,
		"speed_factor": config.speed_factor,
		"repetition_penalty": config.repetition_penalty,
	}
	params.update(config.extra_params)
	params = _normalize_params(params)
	data: bytes | None = None
	url = config.endpoint_url
	if config.method.upper() == "GET":
		query = urllib.parse.urlencode(params)
		sep = "&" if "?" in url else "?"
		url = f"{url}{sep}{query}"
		request = urllib.request.Request(url, method="GET")
	elif config.method.upper() == "POST_JSON":
		data = json.dumps(params).encode("utf-8")
		request = urllib.request.Request(
			url,
			data=data,
			headers={"Content-Type": "application/json"},
			method="POST",
		)
	else:
		raise ValueError(f"Unsupported method: {config.method}")

	try:
		with urllib.request.urlopen(request, timeout=config.timeout_seconds) as resp:
			content_type = resp.getheader("Content-Type", "")
			audio = resp.read()
			if "application/json" in content_type:
				try:
					payload = json.loads(audio.decode("utf-8"))
				except Exception:
					payload = {"message": audio.decode("utf-8", errors="ignore")}
				print(f"[tts] GPT-SoVITS error: {payload}")
				raise ValueError(payload.get("message", "TTS request failed"))
	except urllib.error.HTTPError as exc:
		body = exc.read()
		try:
			payload = json.loads(body.decode("utf-8"))
		except Exception:
			payload = {"message": body.decode("utf-8", errors="ignore")}
		print(f"[tts] GPT-SoVITS HTTP {exc.code}: {payload}")
		raise ValueError(payload.get("message", f"HTTP {exc.code}"))

	output_path = _build_output_path(config.output_path)
	out_dir = os.path.dirname(output_path)
	if out_dir:
		os.makedirs(out_dir, exist_ok=True)
	with open(output_path, "wb") as handle:
		handle.write(audio)
	print(f"[tts] saved {len(audio)} bytes -> {output_path}")
	return output_path


def set_gpt_weights(endpoint_url: str, weights_path: str, timeout_seconds: int = 60) -> None:
	_base = _base_url(endpoint_url)
	_request_simple(
		f"{_base}/set_gpt_weights",
		{"weights_path": weights_path},
		timeout_seconds,
	)


def set_sovits_weights(endpoint_url: str, weights_path: str, timeout_seconds: int = 60) -> None:
	_base = _base_url(endpoint_url)
	_request_simple(
		f"{_base}/set_sovits_weights",
		{"weights_path": weights_path},
		timeout_seconds,
	)


def _base_url(endpoint_url: str) -> str:
	parts = urllib.parse.urlsplit(endpoint_url)
	return f"{parts.scheme}://{parts.netloc}"


def _request_simple(url: str, params: Dict[str, str], timeout_seconds: int) -> None:
	query = urllib.parse.urlencode(_normalize_params(params))
	request = urllib.request.Request(f"{url}?{query}", method="GET")
	with urllib.request.urlopen(request, timeout=timeout_seconds) as resp:
		payload = resp.read()
		content_type = resp.getheader("Content-Type", "")
		if "application/json" in content_type:
			try:
				obj = json.loads(payload.decode("utf-8"))
			except Exception:
				obj = {"message": payload.decode("utf-8", errors="ignore")}
			if obj.get("message") not in ("success", None):
				raise ValueError(obj.get("message", "TTS request failed"))


def _normalize_params(params: Dict[str, object]) -> Dict[str, object]:
	return {
		k: str(v).lower() if isinstance(v, bool) else v
		for k, v in params.items()
	}


def play_wav(path: str) -> None:
	import winsound

	winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)


def play_wav_sync(path: str) -> None:
	if not os.path.exists(path):
		raise FileNotFoundError(path)
	print(f"[tts] playing {os.path.abspath(path)} ({os.path.getsize(path)} bytes)")
	command = (
		"Add-Type -AssemblyName System.Media;"
		f"$p='{os.path.abspath(path)}';"
		"$s=New-Object System.Media.SoundPlayer $p;"
		"$s.Load();"
		"$s.PlaySync();"
	)
	subprocess.run(
		["powershell", "-NoProfile", "-Command", command],
		check=False,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
	)


def speak(text: str, config: TTSConfig, auto_play: bool = True) -> str:
	path = synthesize(text, config)
	if auto_play:
		play_wav(path)
	return path


def _pick_random_ref_audio(directory: str, min_seconds: float, max_seconds: float) -> str:
	if not directory or not os.path.isdir(directory):
		return ""
	wavs = [
		os.path.join(directory, name)
		for name in os.listdir(directory)
		if name.lower().endswith(".wav")
	]
	if not wavs:
		return ""
	valid = [path for path in wavs if _is_duration_ok(path, min_seconds, max_seconds)]
	if valid:
		return _resolve_path(random.choice(valid))
	return _resolve_path(random.choice(wavs))


def _is_duration_ok(path: str, min_seconds: float, max_seconds: float) -> bool:
	try:
		import wave
		with wave.open(path, "rb") as handle:
			frames = handle.getnframes()
			rate = handle.getframerate()
		if rate <= 0:
			return False
		duration = frames / float(rate)
		return min_seconds <= duration <= max_seconds
	except Exception:
		return False


def _build_output_path(output_path: str) -> str:
	base = output_path or "output"
	if base.lower().endswith(".wav"):
		out_dir = os.path.dirname(base)
		prefix = os.path.splitext(os.path.basename(base))[0]
	else:
		out_dir = base
		prefix = "tts"
	ts = time.strftime("%Y%m%d_%H%M%S")
	return os.path.join(out_dir, f"{prefix}_{ts}.wav")


def _resolve_path(path: str) -> str:
	if not path:
		return path
	return os.path.abspath(path)

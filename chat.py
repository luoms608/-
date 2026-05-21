"""Ollama chat helper for the desktop pet."""

from __future__ import annotations

import json
import urllib.request
from typing import Iterable, Optional

try:
	from langchain_core.messages import HumanMessage, SystemMessage
	from langchain_ollama import ChatOllama
	_LANGCHAIN_AVAILABLE = True
except Exception:
	_LANGCHAIN_AVAILABLE = False


def chat(
	prompt: str,
	model: str = "qwen3-coder:480b-cloud",
	host: str = "http://localhost:11434",
	system: Optional[str] = None,
) -> str:
	"""Send a prompt to Ollama and return the response text."""
	if system is None:
		system = _load_persona()
	if _LANGCHAIN_AVAILABLE:
		messages = _build_messages(prompt, system)
		llm = ChatOllama(model=model, base_url=host)
		result = llm.invoke(messages)
		return getattr(result, "content", "")
	return _raw_chat(prompt, model=model, host=host, system=system)


def _build_messages(prompt: str, system: Optional[str]) -> list[object]:
	messages: list[object] = []
	if system:
		messages.append(SystemMessage(content=system))
	messages.append(HumanMessage(content=prompt))
	return messages


def stream_chat(
	prompt: str,
	model: str = "qwen3-coder:480b-cloud",
	host: str = "http://localhost:11434",
	system: Optional[str] = None,
) -> Iterable[str]:
	"""Stream tokens from Ollama (yields chunks of text)."""
	if system is None:
		system = _load_persona()
	if _LANGCHAIN_AVAILABLE:
		messages = _build_messages(prompt, system)
		llm = ChatOllama(model=model, base_url=host)
		for chunk in llm.stream(messages):
			text = getattr(chunk, "content", "")
			if text:
				yield text
		return
	for chunk in _raw_stream_chat(prompt, model=model, host=host, system=system):
		yield chunk


def _load_persona() -> str:
	try:
		with open("persona.txt", "r", encoding="utf-8") as handle:
			return handle.read().strip()
	except Exception:
		return ""


def _raw_chat(
	prompt: str,
	model: str,
	host: str,
	system: Optional[str],
) -> str:
	payload = {
		"model": model,
		"messages": _raw_messages(prompt, system),
		"stream": False,
	}
	data = json.dumps(payload).encode("utf-8")
	req = urllib.request.Request(
		f"{host}/api/chat",
		data=data,
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	with urllib.request.urlopen(req, timeout=60) as resp:
		body = resp.read().decode("utf-8")
		obj = json.loads(body)
		return obj.get("message", {}).get("content", "")


def _raw_messages(prompt: str, system: Optional[str]) -> list[dict[str, str]]:
	messages: list[dict[str, str]] = []
	if system:
		messages.append({"role": "system", "content": system})
	messages.append({"role": "user", "content": prompt})
	return messages


def _raw_stream_chat(
	prompt: str,
	model: str,
	host: str,
	system: Optional[str],
) -> Iterable[str]:
	payload = {
		"model": model,
		"messages": _raw_messages(prompt, system),
		"stream": True,
	}
	data = json.dumps(payload).encode("utf-8")
	req = urllib.request.Request(
		f"{host}/api/chat",
		data=data,
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	with urllib.request.urlopen(req, timeout=60) as resp:
		for line in resp:
			if not line:
				continue
			obj = json.loads(line.decode("utf-8"))
			chunk = obj.get("message", {}).get("content")
			if chunk:
				yield chunk
			if obj.get("done"):
				break


if __name__ == "__main__":
	print(chat("Say hello in Chinese."))

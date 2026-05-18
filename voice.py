
from __future__ import annotations

import os
import random
import subprocess
import threading
import time
from typing import Optional


def _ps_escape(value: str) -> str:
	return value.replace("'", "''")


def speak(text: str, rate: int = 0, volume: int = 100, voice: Optional[str] = None) -> None:
	"""Speak text asynchronously using Windows SAPI via PowerShell.

	- rate: -10..10
	- volume: 0..100
	- voice: optional voice name (exact match)
	"""
	rate = max(-10, min(10, int(rate)))
	volume = max(0, min(100, int(volume)))
	safe_text = _ps_escape(text)

	voice_line = ""
	if voice:
		safe_voice = _ps_escape(voice)
		voice_line = f"$s.SelectVoice('{safe_voice}');"

	ps = (
		"Add-Type -AssemblyName System.Speech;"
		"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
		f"$s.Rate = {rate};"
		f"$s.Volume = {volume};"
		f"{voice_line}"
		f"$s.Speak('{safe_text}');"
	)

	subprocess.Popen(
		[
			"powershell",
			"-NoProfile",
			"-Command",
			ps,
		],
		stdin=subprocess.DEVNULL,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
	)


def list_wavs(directory: str) -> list[str]:
	if not os.path.isdir(directory):
		return []
	return [
		os.path.join(directory, name)
		for name in os.listdir(directory)
		if name.lower().endswith(".wav")
	]


def play_wav(path: str) -> None:
	import winsound

	winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)


def _random_wav_loop(directory: str, min_delay: float, max_delay: float, stop_event: threading.Event) -> None:
	min_delay = max(0.1, float(min_delay))
	max_delay = max(min_delay, float(max_delay))
	while not stop_event.is_set():
		wavs = list_wavs(directory)
		if wavs:
			play_wav(random.choice(wavs))
		delay = random.uniform(min_delay, max_delay)
		stop_event.wait(delay)


def start_random_wav_player(directory: str, min_delay: float = 10.0, max_delay: float = 30.0) -> threading.Event:
	stop_event = threading.Event()
	threading.Thread(
		target=_random_wav_loop,
		args=(directory, min_delay, max_delay, stop_event),
		daemon=True,
	).start()
	return stop_event


if __name__ == "__main__":
	speak("Hello, I am your desktop pet.")

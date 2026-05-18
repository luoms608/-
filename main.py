"""Entry point to run the pet and trigger voice."""

from __future__ import annotations

import threading

import voice
from pet import DesktopPet, PetConfig
import tkinter as tk


def _speak_on_start() -> None:
	wavs = voice.list_wavs("voices")
	if not wavs:
		voice.speak("你好，我是你的桌宠。", rate=0, volume=100)
		return
	import random
	voice.play_wav(random.choice(wavs))


def main() -> None:
	threading.Thread(target=_speak_on_start, daemon=True).start()
	voice.start_random_wav_player("voices", min_delay=20.0, max_delay=45.0)
	root = tk.Tk()
	config = PetConfig(
		scale=3.0,
		trigger_chance_per_second=0.06,
		trigger_cooldown_seconds=15.0,
		special_hold_seconds=10.0,
		gif_key_color="#000000",
		gif_key_tolerance=6,
	)
	DesktopPet(root, config=config)
	root.mainloop()


if __name__ == "__main__":
	main()

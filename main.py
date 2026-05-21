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
	voice.start_random_wav_player("voices", min_delay=180.0, max_delay=180.0)
	root = tk.Tk()
	config = PetConfig(
		scale=3.0,
		trigger_chance_per_second=0.06,
		trigger_cooldown_seconds=15.0,
		special_hold_seconds=10.0,
		gif_key_color="#000000",
		gif_key_tolerance=6,
		tts_enabled=True,
		tts_endpoint_url="http://127.0.0.1:9880/tts",
		tts_text_lang="ja",
		tts_ref_audio_path="",
		tts_prompt_lang="ja",
		tts_prompt_text="",
		tts_text_split_method="cut0",
		tts_batch_size=1,
		tts_split_bucket=False,
		tts_speed_factor=1.0,
		tts_auto_switch_weights=True,
		tts_gpt_weights_path=r"E:\gpt-sovits\GPT-SoVITS-v2pro-20250604\GPT_weights_v2Pro\www-e10.ckpt",
		tts_sovits_weights_path=r"E:\gpt-sovits\GPT-SoVITS-v2pro-20250604\SoVITS_weights_v2Pro\www_e4_s176.pth",
		tts_cooldown_seconds=0.0,
	)
	DesktopPet(root, config=config)
	root.mainloop()


if __name__ == "__main__":
	main()


from __future__ import annotations

import glob
import math
import os
import random
import threading
import time
import tkinter as tk
from tkinter import simpledialog
from dataclasses import dataclass
from typing import Optional

import chat


@dataclass
class PetConfig:
	size: int = 160
	scale: float = 1.0
	fps: int = 30
	move_speed: int = 3
	roam_vertical_amplitude: int = 18
	roam_vertical_period: float = 2.2
	idle_bob_px: int = 6
	idle_bob_period: float = 1.8
	assets_dir: str = "sources"
	idle_keyword: str = "Relax"
	move_keyword: str = "Move"
	special_move_keyword: str = "Special"
	special_hold_keywords: tuple[str, ...] = ("Sleep", "Sit")
	trigger_chance_per_second: float = 0.03
	trigger_cooldown_seconds: float = 5.0
	special_hold_seconds: float = 2.5
	special_move_speed: int = 2
	transparent_color: str = "#00ff00"
	gif_key_color: Optional[str] = None
	gif_key_tolerance: int = 10
	max_frames_per_gif: int = 80
	frame_step: int = 1
	preload_special_frames: bool = False


class Behavior:
	def __init__(self, pet: "DesktopPet") -> None:
		self.pet = pet

	def enter(self) -> None:
		pass

	def update(self, dt: float) -> None:
		pass


class IdleBehavior(Behavior):
	def enter(self) -> None:
		self._start = time.time()

	def update(self, dt: float) -> None:
		# Simple idle bob animation.
		t = time.time() - self._start
		offset = int(self.pet.config.idle_bob_px * (1 - (abs((t % self.pet.config.idle_bob_period) / (self.pet.config.idle_bob_period / 2) - 1))))
		self.pet.maybe_trigger_special(dt)
		self.pet.render_idle(offset)


class RoamBehavior(Behavior):
	def enter(self) -> None:
		self._direction = random.choice([-1, 1])
		x, y = self.pet.get_position()
		self._base_y = y
		self._phase = random.uniform(0.0, math.tau)

	def update(self, dt: float) -> None:
		x, y = self.pet.get_position()
		x += int(self._direction * self.pet.config.move_speed)
		period = max(0.1, self.pet.config.roam_vertical_period)
		self._phase += math.tau * dt / period
		amplitude = max(0, int(self.pet.config.roam_vertical_amplitude))
		y = int(self._base_y + math.sin(self._phase) * amplitude)
		y = self._clamp_vertical(y)
		self._base_y = y - int(math.sin(self._phase) * amplitude)
		self.pet.set_position(x, y)
		self.pet.render_idle(0)
		if not self.pet.is_on_screen():
			self._direction *= -1

	def _clamp_vertical(self, y: int) -> int:
		screen_h = self.pet.root.winfo_screenheight()
		max_y = max(0, screen_h - self.pet.render_size)
		return max(0, min(y, max_y))


class DesktopPet:
	def __init__(self, root: tk.Tk, config: Optional[PetConfig] = None) -> None:
		self.root = root
		self.config = config or PetConfig()
		self.render_size = max(1, int(self.config.size * self.config.scale))
		self._last_tick = time.time()
		self._behavior: Behavior = IdleBehavior(self)
		self._drag_start: Optional[tuple[int, int]] = None
		self._animations: dict[str, tuple[list[tk.PhotoImage], list[float]]] = {}
		self._animation_paths: dict[str, str] = {}
		self._special_keys: list[str] = []
		self._special_queue: list[str] = []
		self._idle_key: Optional[str] = None
		self._move_key: Optional[str] = None
		self._special_move_key: Optional[str] = None
		self._active_key: Optional[str] = None
		self._loop_active = True
		self._frame_index = 0
		self._frame_timer = 0.0
		self._cooldown_until = 0.0
		self._special_until = 0.0
		self._special_move_dir = 1
		self._bubble_items: list[int] = []

		self._setup_window()
		self._setup_canvas()
		self._load_gif_animations()
		self._setup_menu()

		self.set_behavior(self._behavior)
		self._loop()

	def _setup_window(self) -> None:
		self.root.overrideredirect(True)
		self.root.attributes("-topmost", True)
		self.root.attributes("-transparentcolor", self.config.transparent_color)
		self.root.geometry(f"{self.render_size}x{self.render_size}+200+200")

	def _setup_canvas(self) -> None:
		self.canvas = tk.Canvas(self.root, width=self.render_size, height=self.render_size, highlightthickness=0)
		self.canvas.pack(fill=tk.BOTH, expand=True)
		self.canvas.configure(bg=self.config.transparent_color)

		self.body = self.canvas.create_oval(30, 30, 130, 130, fill="#ffcc66", outline="#6b4b1f", width=3)
		self.eye_left = self.canvas.create_oval(60, 70, 75, 85, fill="#2b1d0e", outline="")
		self.eye_right = self.canvas.create_oval(90, 70, 105, 85, fill="#2b1d0e", outline="")
		self.mouth = self.canvas.create_line(70, 105, 95, 105, width=3, fill="#2b1d0e")

		self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
		self.canvas.bind("<B1-Motion>", self._on_drag_move)
		self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
		self.canvas.bind("<Button-3>", self._on_right_click)

	def _setup_menu(self) -> None:
		self.menu = tk.Menu(self.root, tearoff=0)
		self.menu.add_command(label="Idle", command=lambda: self.set_behavior(IdleBehavior(self)))
		self.menu.add_command(label="Roam", command=lambda: self.set_behavior(RoamBehavior(self)))
		self.menu.add_separator()
		self.menu.add_command(label="Chat", command=self._open_chat)
		self.menu.add_separator()
		self.menu.add_command(label="Size +", command=lambda: self._adjust_scale(0.1))
		self.menu.add_command(label="Size -", command=lambda: self._adjust_scale(-0.1))
		self.menu.add_separator()
		self.menu.add_command(label="Quit", command=self.root.destroy)

	def _loop(self) -> None:
		now = time.time()
		dt = now - self._last_tick
		self._last_tick = now
		self._advance_animation(dt)
		self._behavior.update(dt)
		self.root.after(int(1000 / self.config.fps), self._loop)

	def set_behavior(self, behavior: Behavior) -> None:
		self._behavior = behavior
		self._behavior.enter()
		self._special_until = 0.0
		if isinstance(behavior, RoamBehavior) and self._move_key:
			self._ensure_animation_loaded(self._move_key)
			self._set_active_animation(self._move_key, loop=True)
		elif isinstance(behavior, IdleBehavior) and self._idle_key:
			self._ensure_animation_loaded(self._idle_key)
			self._set_active_animation(self._idle_key, loop=True)

	def render_idle(self, bob_offset: int) -> None:
		if self._active_key and self._active_key in self._animations:
			self._render_animation(bob_offset)
			return
		self.canvas.coords(self.body, 30, 30 + bob_offset, 130, 130 + bob_offset)
		self.canvas.coords(self.eye_left, 60, 70 + bob_offset, 75, 85 + bob_offset)
		self.canvas.coords(self.eye_right, 90, 70 + bob_offset, 105, 85 + bob_offset)
		self.canvas.coords(self.mouth, 70, 105 + bob_offset, 95, 105 + bob_offset)

	def get_position(self) -> tuple[int, int]:
		geo = self.root.geometry()
		parts = geo.split("+")
		if len(parts) >= 3:
			x_str, y_str = parts[-2], parts[-1]
			return int(x_str), int(y_str)
		return 0, 0

	def set_position(self, x: int, y: int) -> None:
		self.root.geometry(f"{self.render_size}x{self.render_size}+{x}+{y}")

	def is_on_screen(self) -> bool:
		x, y = self.get_position()
		screen_w = self.root.winfo_screenwidth()
		return 0 <= x <= screen_w - self.render_size

	def _on_drag_start(self, event: tk.Event) -> None:
		self._drag_start = (event.x_root, event.y_root)

	def _on_drag_move(self, event: tk.Event) -> None:
		if not self._drag_start:
			return
		start_x, start_y = self._drag_start
		dx = event.x_root - start_x
		dy = event.y_root - start_y
		x, y = self.get_position()
		self.set_position(x + dx, y + dy)
		self._drag_start = (event.x_root, event.y_root)

	def _on_drag_end(self, event: tk.Event) -> None:
		self._drag_start = None

	def _on_right_click(self, event: tk.Event) -> None:
		self.menu.tk_popup(event.x_root, event.y_root)

	def _open_chat(self) -> None:
		prompt = simpledialog.askstring("Chat", "你想说什么？", parent=self.root)
		if not prompt:
			return
		self._show_bubble("...", hold_seconds=10.0)
		threading.Thread(target=self._chat_worker, args=(prompt,), daemon=True).start()

	def _chat_worker(self, prompt: str) -> None:
		try:
			reply = chat.chat(prompt)
			if not reply:
				reply = "(no response)"
		except Exception as exc:
			reply = f"Error: {exc}"
		self.root.after(0, lambda: self._show_reply(reply))

	def _show_reply(self, reply: str) -> None:
		chunks = self._split_text(reply, max_len=150)
		self._show_bubble_sequence(chunks, hold_seconds=3.0, gap_seconds=1.5)

	def _show_bubble_sequence(
		self,
		chunks: list[str],
		hold_seconds: float,
		gap_seconds: float,
	) -> None:
		if not chunks:
			return
		text = chunks.pop(0)
		self._show_bubble(text, hold_seconds=hold_seconds)
		if chunks:
			self.root.after(
				int((hold_seconds + gap_seconds) * 1000),
				lambda: self._show_bubble_sequence(chunks, hold_seconds, gap_seconds),
			)

	@staticmethod
	def _split_text(text: str, max_len: int = 150) -> list[str]:
		text = text.strip()
		if not text:
			return []
		if max_len <= 0:
			return [text]
		return [text[i : i + max_len] for i in range(0, len(text), max_len)]

	def _show_bubble(self, text: str, hold_seconds: float = 5.0) -> None:
		self._clear_bubble()
		font = ("Arial", 10)
		text_item = self.canvas.create_text(
			self.render_size // 2,
			12,
			text=text,
			fill="#111111",
			font=font,
			anchor="n",
			width=self.render_size - 12,
		)
		bbox = self.canvas.bbox(text_item)
		if not bbox:
			return
		x1, y1, x2, y2 = bbox
		pad = 6
		rect = self.canvas.create_rectangle(
			x1 - pad,
			y1 - pad,
			x2 + pad,
			y2 + pad,
			fill="#ffffff",
			outline="#111111",
			width=1,
		)
		self.canvas.tag_raise(text_item, rect)
		self._bubble_items = [rect, text_item]
		self.root.after(int(hold_seconds * 1000), self._clear_bubble)

	def _clear_bubble(self) -> None:
		for item in self._bubble_items:
			self.canvas.delete(item)
		self._bubble_items = []

	def _adjust_scale(self, delta: float) -> None:
		new_scale = max(0.3, min(3.0, self.config.scale + delta))
		if abs(new_scale - self.config.scale) < 1e-6:
			return
		self._apply_scale(new_scale)

	def _apply_scale(self, new_scale: float) -> None:
		x, y = self.get_position()
		self.config.scale = new_scale
		self.render_size = max(1, int(self.config.size * self.config.scale))
		self.root.geometry(f"{self.render_size}x{self.render_size}+{x}+{y}")
		self.canvas.config(width=self.render_size, height=self.render_size)
		if hasattr(self, "sprite"):
			self.canvas.delete(self.sprite)
			delattr(self, "sprite")
		self._animations = {}
		self._animation_paths = {}
		self._special_keys = []
		self._special_queue = []
		self._idle_key = None
		self._move_key = None
		self._special_move_key = None
		self._active_key = None
		self._frame_index = 0
		self._frame_timer = 0.0
		self._special_until = 0.0
		self._load_gif_animations()

	def maybe_trigger_special(self, dt: float) -> None:
		if not self._special_keys or not self._idle_key:
			return
		now = time.time()
		if now < self._cooldown_until:
			return
		if self._active_key != self._idle_key:
			return
		if random.random() < self.config.trigger_chance_per_second * dt:
			key = self._next_special_key()
			self._ensure_animation_loaded(key)
			self._set_active_animation(key, loop=False)
			if self._should_hold_special(key):
				self._special_until = -3.0
			else:
				self._special_until = 0.0
			self._special_move_dir = random.choice([-1, 1])
			self._cooldown_until = now + self.config.trigger_cooldown_seconds

	def _should_hold_special(self, key: str) -> bool:
		return any(word in key.lower() for word in self.config.special_hold_keywords)

	def _next_special_key(self) -> str:
		if not self._special_queue:
			self._special_queue = list(self._special_keys)
			random.shuffle(self._special_queue)
		return self._special_queue.pop(0)

	def _apply_special_motion(self) -> None:
		if not self._active_key or self._active_key != self._special_move_key:
			return
		x, y = self.get_position()
		x += int(self._special_move_dir * self.config.special_move_speed)
		self.set_position(x, y)
		if not self.is_on_screen():
			self._special_move_dir *= -1

	def _render_animation(self, bob_offset: int) -> None:
		frames, durations = self._animations[self._active_key]
		if not frames:
			return
		frame = frames[self._frame_index]
		self.canvas.itemconfigure(self.body, state="hidden")
		self.canvas.itemconfigure(self.eye_left, state="hidden")
		self.canvas.itemconfigure(self.eye_right, state="hidden")
		self.canvas.itemconfigure(self.mouth, state="hidden")
		if not hasattr(self, "sprite"):
			self.sprite = self.canvas.create_image(self.render_size // 2, self.render_size // 2, image=frame)
		else:
			self.canvas.itemconfigure(self.sprite, image=frame)
		self.canvas.coords(self.sprite, self.render_size // 2, self.render_size // 2 + bob_offset)

	def _advance_animation(self, dt: float) -> None:
		if not self._active_key:
			return
		frames, durations = self._animations[self._active_key]
		if not frames:
			return
		self._apply_special_motion()
		self._frame_timer += dt
		while self._frame_timer >= durations[self._frame_index]:
			self._frame_timer -= durations[self._frame_index]
			self._frame_index += 1
			if self._frame_index >= len(frames):
				if self._loop_active:
					self._frame_index = 0
				else:
					if self._active_key in self._special_keys and self._special_until < 0:
						self._special_until = time.time() + abs(self._special_until)
						self._set_active_animation(self._active_key, loop=True)
					else:
						self._set_active_animation(self._idle_key, loop=True)
					break
		now = time.time()
		if self._active_key in self._special_keys and self._special_until > 0 and now >= self._special_until:
			self._special_until = 0.0
			self._set_active_animation(self._idle_key, loop=True)

	def _set_active_animation(self, key: Optional[str], loop: bool) -> None:
		self._active_key = key
		self._loop_active = loop
		self._frame_index = 0
		self._frame_timer = 0.0

	def _load_gif_animations(self) -> None:
		assets_dir = os.path.join(os.path.dirname(__file__), self.config.assets_dir)
		paths = sorted(glob.glob(os.path.join(assets_dir, "*.gif")))
		if not paths:
			return
		try:
			from PIL import Image, ImageTk  # type: ignore
		except Exception:
			return
		for path in paths:
			key = os.path.splitext(os.path.basename(path))[0]
			self._animation_paths[key] = path
			if self.config.idle_keyword.lower() in key.lower():
				self._idle_key = key
			elif self.config.move_keyword.lower() in key.lower():
				self._move_key = key
			elif self.config.special_move_keyword.lower() in key.lower():
				self._special_move_key = key
				self._special_keys.append(key)
			else:
				self._special_keys.append(key)
		if not self._idle_key and self._animations:
			self._idle_key = next(iter(self._animations.keys()))
			self._special_keys = [k for k in self._animations.keys() if k != self._idle_key]
		if self._idle_key and self._idle_key in self._animation_paths:
			self._animations[self._idle_key] = self._load_gif_frames(self._animation_paths[self._idle_key])
		if self._move_key and self._move_key in self._animation_paths:
			self._animations[self._move_key] = self._load_gif_frames(self._animation_paths[self._move_key])
		if self.config.preload_special_frames:
			for key in self._special_keys:
				self._animations[key] = self._load_gif_frames(self._animation_paths[key], full_frames=True)
		self._special_queue = []
		self._set_active_animation(self._idle_key, loop=True)

	def _ensure_animation_loaded(self, key: str) -> None:
		if key in self._animations:
			return
		if key in self._animation_paths:
			full = key in self._special_keys
			self._animations[key] = self._load_gif_frames(self._animation_paths[key], full_frames=full)

	def _load_gif_frames(self, path: str, full_frames: bool = False) -> tuple[list[tk.PhotoImage], list[float]]:
		try:
			from PIL import Image, ImageTk  # type: ignore
		except Exception:
			return ([], [])
		frames: list[tk.PhotoImage] = []
		durations: list[float] = []
		with Image.open(path) as img:
			key_color = self._resolve_key_color(img)
			frame_count = getattr(img, "n_frames", 1)
			step = 1 if full_frames else max(1, self.config.frame_step)
			limit = frame_count if full_frames else max(1, self.config.max_frames_per_gif)
			selected = 0
			for i in range(0, frame_count, step):
				if selected >= limit:
					break
				img.seek(i)
				frame_img = img.copy().convert("RGBA")
				frame_img = frame_img.resize((self.render_size, self.render_size), Image.BILINEAR)
				if key_color is not None:
					frame_img = self._apply_chroma_key(frame_img, key_color)
				frame = ImageTk.PhotoImage(frame_img)
				duration_ms = img.info.get("duration", int(1000 / self.config.fps)) * step
				frames.append(frame)
				durations.append(max(0.01, duration_ms / 1000.0))
				selected += 1
		return (frames, durations)

	def _resolve_key_color(self, img: "Image.Image") -> Optional[tuple[int, int, int]]:
		if not self.config.gif_key_color:
			return None
		try:
			color = self.canvas.winfo_rgb(self.config.gif_key_color)
			return (color[0] // 256, color[1] // 256, color[2] // 256)
		except Exception:
			return None

	def _apply_chroma_key(self, img: "Image.Image", key_color: tuple[int, int, int]) -> "Image.Image":
		try:
			from PIL import Image, ImageChops  # type: ignore
		except Exception:
			return img
		img = img.convert("RGBA")
		kr, kg, kb = key_color
		key = Image.new("RGB", img.size, (kr, kg, kb))
		diff = ImageChops.difference(img.convert("RGB"), key).convert("L")
		tol = max(0, min(255, self.config.gif_key_tolerance))
		mask = diff.point(lambda v: 0 if v <= tol else 255)
		alpha = img.getchannel("A")
		new_alpha = ImageChops.multiply(alpha, mask)
		img.putalpha(new_alpha)
		return img


def main() -> None:
	root = tk.Tk()
	config = PetConfig(
		gif_key_color="#000000",
		gif_key_tolerance=6,
	)
	DesktopPet(root, config=config)
	root.mainloop()


if __name__ == "__main__":
	main()

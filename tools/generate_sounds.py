"""Generate dependency-free PCM WAV sounds used by the game."""

import math
import random
import struct
import wave
from pathlib import Path


RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def pulse(t: float, start: float, frequency: float, decay: float) -> float:
    age = t - start
    if age < 0:
        return 0.0
    envelope = math.exp(-age * decay)
    wood = math.sin(2 * math.pi * frequency * age) + 0.45 * math.sin(2 * math.pi * frequency * 2.7 * age)
    return envelope * wood


def write_sound(path: Path, duration: float, pulses: list[tuple[float, float, float]], seed: int, noise=.12) -> None:
    rng = random.Random(seed)
    frames = bytearray()
    for index in range(int(RATE * duration)):
        t = index / RATE
        sample = sum(pulse(t, *settings) for settings in pulses)
        sample += rng.uniform(-noise, noise) * math.exp(-t * 28)
        sample = max(-1.0, min(1.0, sample * 0.62))
        frames.extend(struct.pack("<h", int(sample * 32767)))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(frames)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_sound(OUT / "move.wav", .18, [(0.0, 620, 25)], 2026)
    write_sound(OUT / "capture.wav", .32, [(0.0, 430, 20), (.09, 300, 18)], 2027)
    write_sound(OUT / "check.wav", .48, [(0.0, 760, 9), (.15, 980, 10)], 2028, noise=.02)
    write_sound(OUT / "illegal.wav", .24, [(0.0, 145, 12), (0.0, 171, 12)], 2029, noise=.04)
    write_sound(OUT / "click.wav", .09, [(0.0, 920, 42)], 2030, noise=.05)
    print(f"Generated sounds in {OUT}")


if __name__ == "__main__":
    main()

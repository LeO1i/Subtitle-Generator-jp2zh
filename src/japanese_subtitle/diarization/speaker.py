from __future__ import annotations

import math
import wave

import numpy as np

from japanese_subtitle.domain.models import Segment, SpeakerWindow


def _read_mono_wav(audio_path):
    with wave.open(audio_path, "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())

    if sample_width != 2:
        raise ValueError("Speaker diarization expects 16-bit PCM WAV input.")

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, sample_rate


def _rms(samples):
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples)) + 1e-12))


def _vad_segments(audio, sample_rate, frame_seconds=0.5, hop_seconds=0.25):
    frame_size = max(1, int(frame_seconds * sample_rate))
    hop_size = max(1, int(hop_seconds * sample_rate))
    energies = []
    frames = []

    for start in range(0, max(1, len(audio) - frame_size + 1), hop_size):
        end = min(len(audio), start + frame_size)
        frame = audio[start:end]
        energy = _rms(frame)
        energies.append(energy)
        frames.append((start / sample_rate, end / sample_rate, energy))

    if not frames:
        return []

    energy_values = np.array(energies, dtype=np.float32)
    floor = float(np.percentile(energy_values, 30))
    ceiling = float(np.percentile(energy_values, 85))
    threshold = max(0.008, floor + (ceiling - floor) * 0.35)

    segments = []
    active_start = None
    active_end = None
    active_energies = []

    for start, end, energy in frames:
        if energy >= threshold:
            if active_start is None:
                active_start = start
            active_end = end
            active_energies.append(energy)
            continue

        if active_start is not None:
            if active_end - active_start >= 0.45:
                segments.append((active_start, active_end, float(np.mean(active_energies))))
            active_start = None
            active_end = None
            active_energies = []

    if active_start is not None and active_end - active_start >= 0.45:
        segments.append((active_start, active_end, float(np.mean(active_energies))))

    return _merge_close_segments(segments)


def _merge_close_segments(segments, max_gap=0.35):
    if not segments:
        return []
    merged = [list(segments[0])]
    for start, end, loudness in segments[1:]:
        previous = merged[-1]
        if start - previous[1] <= max_gap:
            previous[1] = max(previous[1], end)
            previous[2] = max(previous[2], loudness)
        else:
            merged.append([start, end, loudness])
    return [tuple(item) for item in merged]


def _cluster_with_resemblyzer(audio, sample_rate, speech_segments):
    try:
        from resemblyzer import VoiceEncoder
        from sklearn.cluster import AgglomerativeClustering
    except Exception:
        return None

    embeddings = []
    usable = []
    encoder = VoiceEncoder()
    for start, end, loudness in speech_segments:
        start_idx = max(0, int(start * sample_rate))
        end_idx = min(len(audio), int(end * sample_rate))
        clip = audio[start_idx:end_idx]
        if clip.size < int(0.75 * sample_rate):
            continue
        try:
            embeddings.append(encoder.embed_utterance(clip))
            usable.append((start, end, loudness))
        except Exception:
            continue

    if len(embeddings) < 2:
        return None

    matrix = np.vstack(embeddings)
    try:
        clusterer = AgglomerativeClustering(n_clusters=None, distance_threshold=0.75)
        labels = clusterer.fit_predict(matrix)
    except Exception:
        n_clusters = max(1, min(3, int(math.sqrt(len(embeddings))) or 1))
        labels = AgglomerativeClustering(n_clusters=n_clusters).fit_predict(matrix)

    return [(segment[0], segment[1], segment[2], int(label)) for segment, label in zip(usable, labels)]


def get_top_speaker_windows(audio_path, top_n=3) -> list[SpeakerWindow]:
    audio, sample_rate = _read_mono_wav(audio_path)
    speech_segments = _vad_segments(audio, sample_rate)
    if not speech_segments:
        return []

    clustered = _cluster_with_resemblyzer(audio, sample_rate, speech_segments)
    if clustered is None:
        clustered = [(start, end, loudness, 0) for start, end, loudness in speech_segments]

    speaker_energy: dict[int, float] = {}
    for start, end, loudness, label in clustered:
        duration = max(0.0, end - start)
        speaker_energy[label] = speaker_energy.get(label, 0.0) + loudness * duration

    ranked_labels = [
        label
        for label, _energy in sorted(speaker_energy.items(), key=lambda item: item[1], reverse=True)[:top_n]
    ]
    label_to_speaker = {label: f"Speaker{index + 1}" for index, label in enumerate(ranked_labels)}

    windows: list[SpeakerWindow] = []
    for start, end, loudness, label in clustered:
        speaker_id = label_to_speaker.get(label)
        if not speaker_id:
            continue
        windows.append(SpeakerWindow(start=start, end=end, speaker_id=speaker_id, loudness=loudness))

    return windows


def assign_speaker(segment: Segment | dict, speaker_windows: list[SpeakerWindow], min_overlap=0.05) -> str | None:
    if isinstance(segment, Segment):
        start = segment.start
        end = segment.end
    else:
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
    best_window = None
    best_overlap = 0.0

    for window in speaker_windows:
        overlap = max(0.0, min(end, window.end) - max(start, window.start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_window = window

    if not best_window or best_overlap < min_overlap:
        return None
    return best_window.speaker_id

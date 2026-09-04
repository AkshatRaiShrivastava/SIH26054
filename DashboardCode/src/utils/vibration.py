"""Vibration processing helpers.

Compute simple spectral features from a window of vibration samples.
The telemetry currently stores `vibration_g` per packet (single-value). For richer
vibration analysis, prefer raw accel traces; here we provide utilities for small windows.
"""
import numpy as np


def band_energies(signal: np.ndarray, fs: float = 1.0, bands=None):
    """Compute energy in frequency bands from a 1-D signal.

    Args:
        signal: 1-D numpy array of samples.
        fs: sample rate in Hz (packets per second). Default 1.0 if unknown.
        bands: list of (f_low, f_high) tuples in Hz.

    Returns:
        dict mapping band label to energy.
    """
    if bands is None:
        bands = [(0.1, 2), (2, 5), (5, 10), (10, fs/2 - 0.1)]

    n = len(signal)
    if n == 0:
        return {f"{lo}-{hi}Hz": 0.0 for lo, hi in bands}

    # Detrend
    x = signal - np.mean(signal)

    # FFT
    fft = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    power = np.abs(fft) ** 2

    energies = {}
    total = np.sum(power) + 1e-12
    for lo, hi in bands:
        mask = (freqs >= lo) & (freqs < hi)
        band_energy = np.sum(power[mask])
        energies[f"{lo}-{hi}Hz"] = float(band_energy / total)

    # Basic time-domain features
    energies["rms_g"] = float(np.sqrt(np.mean(signal ** 2)))
    energies["crest"] = float(np.max(np.abs(signal)) / (energies.get("rms_g", 1e-9)))

    return energies

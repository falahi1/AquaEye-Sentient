import matplotlib.pyplot as plt
from typing import List


def normalise_frequency_response(
    freqs_hz: List[float],
    levels_dbfs: List[float]
) -> List[float]:
    """
    Normalise frequency response to 0 dB at the 1 kHz reference point.
    Returns list of normalised levels in same order as input.
    Raises ValueError if lengths differ or if 1000 Hz is not in freqs_hz.
    """
    if len(freqs_hz) != len(levels_dbfs):
        raise ValueError(
            f"freqs_hz and levels_dbfs must have the same length "
            f"(got {len(freqs_hz)} and {len(levels_dbfs)})"
        )
    if 1000 not in freqs_hz:
        raise ValueError("1 kHz reference (1000 Hz) must be present in freqs_hz")
    ref_level = levels_dbfs[freqs_hz.index(1000)]
    return [level - ref_level for level in levels_dbfs]


def plot_frequency_response(
    freqs_hz: List[float],
    levels_dbfs: List[float],
    output_path: str
) -> None:
    """
    Plot relative frequency response normalised to 1 kHz.
    freqs_hz    : [1000, 2000, 5000, 10000, 20000]
    levels_dbfs : measured RMS dBFS at each frequency (same order)
    Saves PNG to output_path.
    """
    normalised = normalise_frequency_response(freqs_hz, levels_dbfs)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.semilogx(freqs_hz, normalised, marker='o', linewidth=2, color='steelblue')
    ax.axhline(0, color='gray', linestyle='--', linewidth=0.8, label='0 dB ref (1 kHz)')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Relative Level (dB re 1 kHz)')
    ax.set_title('HydroMoth Relative Frequency Response\n(single unit, 0.5 m, bucket)')
    ax.grid(True, which='both', alpha=0.3)
    ax.set_xticks(freqs_hz)
    ax.set_xticklabels([f'{int(f // 1000)}k' for f in freqs_hz])
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

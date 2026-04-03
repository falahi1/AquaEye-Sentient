import numpy as np
import matplotlib.pyplot as plt
from typing import Dict


def normalise_directivity(angle_to_level: Dict[float, float]) -> Dict[float, float]:
    """
    Normalise directivity data to 0 dB at the maximum level.
    Returns a new dict with levels shifted so the highest = 0 dB.
    """
    if not angle_to_level:
        raise ValueError("angle_to_level must not be empty")
    max_level = max(angle_to_level.values())
    return {angle: level - max_level for angle, level in angle_to_level.items()}


def combine_array_directivity(channels: list) -> Dict[float, float]:
    """
    Combine multiple HydroMoth channels by taking the maximum level at each angle.
    channels: list of dicts, each mapping angle_deg -> level_dbfs.
    All dicts must have identical angle sets.
    Returns {angle_deg: max_level_dbfs}.
    """
    if not channels:
        raise ValueError("channels list is empty")
    angles = sorted(channels[0].keys())
    for ch in channels[1:]:
        if sorted(ch.keys()) != angles:
            raise ValueError("All channels must have identical angle sets")
    return {angle: max(ch[angle] for ch in channels) for angle in angles}


def plot_directivity(configs: Dict[str, Dict[float, float]], output_path: str) -> None:
    """
    Plot overlaid normalised polar directivity for one or more configurations.

    configs: {'Config A': {0: -20.1, 45: -24.3, ...}, 'Config B': {...}, ...}
             angles in degrees (0 = front of hydrophone), levels in dBFS.
    Normalises each configuration independently before plotting.
    Saves PNG to output_path.
    """
    if not configs:
        raise ValueError("configs must not be empty")
    fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(8, 8))

    for label, data in configs.items():
        normalised = normalise_directivity(data)
        angles_deg = sorted(normalised.keys())
        levels = [normalised[a] for a in angles_deg]
        # Close the loop for polar plot
        angles_rad = [np.deg2rad(a) for a in angles_deg] + [np.deg2rad(angles_deg[0])]
        levels_closed = levels + [levels[0]]
        ax.plot(angles_rad, levels_closed, label=label, linewidth=2, marker='o', markersize=5)

    ax.set_theta_zero_location('N')    # 0° at top
    ax.set_theta_direction(-1)         # clockwise
    ax.set_rlim(-30, 0)
    ax.set_rticks([-30, -20, -10, 0])
    ax.set_rlabel_position(45)
    ax.legend(loc='lower right', bbox_to_anchor=(1.35, -0.05))
    ax.set_title(
        'HydroMoth Directivity Comparison\n(normalised, 10 kHz tone, 1 m distance)',
        pad=20
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

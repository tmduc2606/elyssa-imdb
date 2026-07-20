from pathlib import Path
import matplotlib.pyplot as plt


def save_figures(figures_dir: Path, prefix: str = "", dpi: int = 150):
    figures_dir.mkdir(parents=True, exist_ok=True)
    for i, fig in enumerate(plt.get_fignums()):
        f = plt.figure(fig)
        filename = f"{prefix}figure_{i}.png" if prefix else f"figure_{i}.png"
        f.savefig(figures_dir / filename, dpi=dpi, bbox_inches="tight")
        plt.close(fig)


def write_html(content: str, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

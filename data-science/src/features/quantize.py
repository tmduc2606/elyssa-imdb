import logging
from pathlib import Path
from typing import Optional

import torch

logger = logging.getLogger(__name__)


def quantize_embedding_encoder(
    model,
    tokenizer,
    save_dir: Path,
    dtype: torch.dtype = torch.qint8,
) -> Path:
    """Quantize a HuggingFace transformer encoder to INT8 (dynamic) and persist it.

    Uses PyTorch dynamic quantization (``torch.quantization.quantize_dynamic``),
    which converts ``nn.Linear`` layers to INT8 at runtime — the CPU-friendly
    equivalent of the blueprint's ONNX Runtime INT8 recommendation for the
    AMD Athlon 200GE reference rig (3-4x throughput on embedding stages).
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    quantized = torch.quantization.quantize_dynamic(
        model, {torch.nn.Linear}, dtype=dtype
    )
    quantized.eval()

    model_path = save_dir / "distilbert_int8.pt"
    torch.save(quantized, model_path)
    tokenizer.save_pretrained(str(save_dir / "tokenizer"))
    logger.info(f"INT8-quantized encoder saved to {model_path}")
    return model_path


def load_quantized_encoder(quantized_path: Path, device: str = "cpu"):
    model = torch.load(quantized_path, map_location=device)
    model.eval()
    logger.info(f"Loaded INT8-quantized encoder from {quantized_path}")
    return model


def try_load_quantized_encoder(quantized_path: Optional[Path], device: str = "cpu"):
    """Load a quantized encoder, falling back to None on any failure."""
    if quantized_path is None:
        return None
    quantized_path = Path(quantized_path)
    if not quantized_path.exists():
        logger.warning(f"Quantized encoder not found: {quantized_path}")
        return None
    try:
        return load_quantized_encoder(quantized_path, device)
    except Exception as e:
        logger.warning(f"Failed to load quantized encoder ({e}); falling back to float32")
        return None

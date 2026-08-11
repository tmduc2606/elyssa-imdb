import numpy as np
import pandas as pd
import torch
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

BATCH_SIZE = 128
EMBEDDING_DIM = 768


def load_text_encoder(
    model_name: str = "distilbert-base-uncased",
    device: Optional[str] = None,
    quantized_path: Optional[Path] = None,
):
    from transformers import DistilBertTokenizer, DistilBertModel

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = DistilBertTokenizer.from_pretrained(model_name)
    if quantized_path:
        from src.features.quantize import try_load_quantized_encoder
        quantized = try_load_quantized_encoder(quantized_path, device)
        if quantized is not None:
            logger.info(f"Using INT8-quantized encoder {model_name} on {device}")
            return tokenizer, quantized, device
        logger.warning(f"Quantized encoder unavailable ({quantized_path}); using float32")
    model = DistilBertModel.from_pretrained(model_name).to(device).eval()
    logger.info(f"Loaded {model_name} on {device}")
    return tokenizer, model, device


def embed_text_batch(
    texts: List[str],
    tokenizer,
    model,
    device: str,
    batch_size: int = BATCH_SIZE,
    max_length: int = 32,
) -> np.ndarray:
    all_embs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        inputs = tokenizer(
            batch, return_tensors="pt", padding=True,
            truncation=True, max_length=max_length
        ).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        cls_emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()
        all_embs.append(cls_emb)
    return np.vstack(all_embs)


def load_title_embeddings(processed_dir: Path) -> np.ndarray:
    single = processed_dir / "title_embeddings.npy"
    if single.exists():
        return np.load(single)
    shards = sorted(processed_dir.glob("title_embeddings_shard_*.npy"))
    if shards:
        return np.vstack([np.load(s) for s in shards])
    raise FileNotFoundError(f"No embeddings found in {processed_dir}")


def get_embeddings_for_split(
    mask: pd.Series,
    embeddings_array: np.ndarray,
) -> np.ndarray:
    return embeddings_array[mask.values, :]

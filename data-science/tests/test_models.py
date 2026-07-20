import torch
import numpy as np
from pathlib import Path
from src.models.genre.gmu import GatedMultimodalUnit, make_dataloaders


def test_gmu_forward_pass():
    model = GatedMultimodalUnit(
        dims_tab=17, dims_text=768, dims_kg=0, hidden_dim=128, output_dim=28
    )
    x_tab = torch.randn(4, 17)
    x_text = torch.randn(4, 768)
    output = model(x_tab, x_text)
    assert output.shape == (4, 28)
    assert output.requires_grad


def test_gmu_forward_kg():
    model = GatedMultimodalUnit(
        dims_tab=17, dims_text=768, dims_kg=64, hidden_dim=128, output_dim=28
    )
    x_tab = torch.randn(4, 17)
    x_text = torch.randn(4, 768)
    x_kg = torch.randn(4, 64)
    output = model(x_tab, x_text, x_kg)
    assert output.shape == (4, 28)


def test_gmu_use_kg_flag():
    model_no_kg = GatedMultimodalUnit(17, 768, 0, 128, 0.3, 28)
    model_kg = GatedMultimodalUnit(17, 768, 64, 128, 0.3, 28)
    assert not model_no_kg.use_kg
    assert model_kg.use_kg


def test_make_dataloaders():
    X_tab = np.random.randn(50, 17).astype(np.float32)
    X_text = np.random.randn(50, 768).astype(np.float32)
    y = np.random.randint(0, 2, (50, 28)).astype(np.float32)
    loader = make_dataloaders(X_tab, X_text, None, y, batch_size=16, use_kg=False)
    batch = next(iter(loader))
    assert len(batch) == 4
    assert batch[0].shape == (16, 17)
    assert batch[1].shape == (16, 768)
    assert batch[2].shape == (16, 1)
    assert batch[3].shape == (16, 28)


def test_gmu_different_hidden_dims():
    for hdim in [64, 128, 256]:
        model = GatedMultimodalUnit(
            dims_tab=17, dims_text=768, dims_kg=0,
            hidden_dim=hdim, output_dim=28
        )
        x_tab = torch.randn(2, 17)
        x_text = torch.randn(2, 768)
        output = model(x_tab, x_text)
        assert output.shape == (2, 28)
        assert model.classifier.in_features == hdim


def test_ncf_forward():
    from src.models.recommender.ncf_model import NCF
    model = NCF(num_users=100, num_items=1000, embedding_dim=64, layers=[64, 32, 16])
    user_ids = torch.randint(0, 100, (8,))
    item_ids = torch.randint(0, 1000, (8,))
    output = model(user_ids, item_ids)
    assert output.shape == (8,)


def test_ncf_embedding_dims():
    from src.models.recommender.ncf_model import NCF
    model = NCF(num_users=50, num_items=500, embedding_dim=32, layers=[32, 16])
    assert model.user_embedding.weight.shape == (50, 32)
    assert model.item_embedding.weight.shape == (500, 32)

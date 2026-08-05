import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from torch.utils.data import TensorDataset, DataLoader
from sklearn.metrics import f1_score
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class GatedMultimodalUnit(nn.Module):
    def __init__(self, dims_tab: int, dims_text: int, dims_kg: int = 0,
                 hidden_dim: int = 128, dropout: float = 0.3, output_dim: Optional[int] = None):
        super().__init__()
        self.use_kg = dims_kg > 0

        self.encoder_tab = nn.Sequential(
            nn.Linear(dims_tab, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.encoder_text = nn.Sequential(
            nn.Linear(dims_text, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        if self.use_kg:
            self.encoder_kg = nn.Sequential(
                nn.Linear(dims_kg, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            )

        gate_in = hidden_dim * (3 if self.use_kg else 2)
        self.gate = nn.Sequential(
            nn.Linear(gate_in, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 2 + (1 if self.use_kg else 0)),
            nn.Sigmoid(),
        )

        self.classifier = nn.Linear(hidden_dim, output_dim)

    def forward(self, tab, text, kg=None):
        h_tab = self.encoder_tab(tab)
        h_text = self.encoder_text(text)

        if self.use_kg:
            h_kg = self.encoder_kg(kg)
            concat = torch.cat([h_tab, h_text, h_kg], dim=1)
        else:
            concat = torch.cat([h_tab, h_text], dim=1)

        gates = self.gate(concat)

        if self.use_kg:
            g_tab, g_text, g_kg = gates[:, 0:1], gates[:, 1:2], gates[:, 2:3]
            fused = g_tab * h_tab + g_text * h_text + g_kg * h_kg
        else:
            g_tab, g_text = gates[:, 0:1], gates[:, 1:2]
            fused = g_tab * h_tab + g_text * h_text

        logits = self.classifier(fused)
        return logits


def make_dataloaders(
    X_tab: np.ndarray, X_text: np.ndarray, X_kg: Optional[np.ndarray],
    y: np.ndarray, batch_size: int = 64, use_kg: bool = False,
) -> DataLoader:
    tensors = [
        torch.tensor(X_tab, dtype=torch.float32),
        torch.tensor(X_text, dtype=torch.float32),
    ]
    if use_kg and X_kg is not None:
        tensors.append(torch.tensor(X_kg, dtype=torch.float32))
    else:
        tensors.append(torch.zeros((len(y), 1), dtype=torch.float32))
    tensors.append(torch.tensor(y, dtype=torch.float32))
    ds = TensorDataset(*tensors)
    return DataLoader(ds, batch_size=batch_size, shuffle=True)


def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss = 0
    for batch in loader:
        optimizer.zero_grad()
        tab, text, kg, y = [b.to(device) for b in batch]
        logits = model(tab, text, kg)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


def eval_model(model, loader, criterion, device):
    model.eval()
    total_loss = 0
    all_preds = []
    all_y = []
    with torch.no_grad():
        for batch in loader:
            tab, text, kg, y = [b.to(device) for b in batch]
            logits = model(tab, text, kg)
            loss = criterion(logits, y)
            total_loss += loss.item()
            preds = torch.sigmoid(logits).cpu().numpy()
            all_preds.append(preds)
            all_y.append(y.cpu().numpy())

    y_true = np.vstack(all_y)
    y_pred = np.vstack(all_preds)
    y_pred_bin = (y_pred > 0.5).astype(int)
    macro_f1 = f1_score(y_true, y_pred_bin, average="macro")
    return total_loss / len(loader), macro_f1


def train_gmu(
    model,
    train_loader,
    val_loader,
    test_loader,
    device,
    lr: float = 1e-3,
    max_epochs: int = 50,
    patience: int = 5,
) -> Tuple[nn.Module, dict]:
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()

    best_val_f1 = 0.0
    best_state = None
    no_improve = 0

    for epoch in range(max_epochs):
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_f1 = eval_model(model, val_loader, criterion, device)
        logger.info(f"Epoch {epoch+1}/{max_epochs}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}, val_f1={val_f1:.4f}")

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_state = model.state_dict().copy()
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    model.load_state_dict(best_state)
    _, test_f1 = eval_model(model, test_loader, criterion, device)
    logger.info(f"Test Macro F1: {test_f1:.4f}")

    return model, {"val_f1": best_val_f1, "test_f1": test_f1}


def ablation_experiment(
    modality_combo: Tuple[bool, bool, bool],
    X_train_tab, X_train_text, X_train_kg, y_train,
    X_val_tab, X_val_text, X_val_kg, y_val,
    num_tab: int, num_text: int, hidden_dim: int, dropout: float,
    device, lr: float = 1e-3, batch_size: int = 64, max_epochs: int = 15, patience: int = 5,
) -> float:
    use_tab, use_text, use_kg = modality_combo
    dims_kg = X_train_kg.shape[1] if (use_kg and X_train_kg is not None and X_train_kg.shape[1] > 0) else 0

    def prepare(X_tab, X_text, X_kg):
        n = len(X_tab)
        return (
            torch.tensor(X_tab if use_tab else np.zeros((n, num_tab), dtype=np.float32), dtype=torch.float32),
            torch.tensor(X_text if use_text else np.zeros((n, num_text), dtype=np.float32), dtype=torch.float32),
            torch.tensor(X_kg if (use_kg and X_kg is not None) else np.zeros((n, max(dims_kg, 1)), dtype=np.float32), dtype=torch.float32),
        )

    X_tr_t, X_tr_te, X_tr_k = prepare(X_train_tab, X_train_text, X_train_kg)
    X_va_t, X_va_te, X_va_k = prepare(X_val_tab, X_val_text, X_val_kg)

    model = GatedMultimodalUnit(
        dims_tab=num_tab if use_tab else 0,
        dims_text=num_text if use_text else 0,
        dims_kg=dims_kg,
        hidden_dim=hidden_dim, dropout=dropout, output_dim=y_train.shape[1],
    ).to(device)

    train_loader = make_dataloaders(X_tr_t, X_tr_te, X_tr_k, y_train, batch_size, use_kg)
    val_loader = make_dataloaders(X_va_t, X_va_te, X_va_k, y_val, 256, use_kg)

    _, metrics = train_gmu(model, train_loader, val_loader, None, device, lr, max_epochs, patience)
    return metrics["val_f1"]

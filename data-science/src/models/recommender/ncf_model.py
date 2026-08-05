import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from typing import List
import logging

logger = logging.getLogger(__name__)


class NCF(nn.Module):
    def __init__(self, num_users: int, num_items: int, embedding_dim: int = 64, layers: List[int] = None):
        super().__init__()
        if layers is None:
            layers = [64, 32, 16]
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)

        layers_dim = [2 * embedding_dim] + layers
        self.mlp = nn.Sequential()
        for i in range(len(layers_dim) - 1):
            self.mlp.add_module(f"linear{i}", nn.Linear(layers_dim[i], layers_dim[i + 1]))
            self.mlp.add_module(f"relu{i}", nn.ReLU())
        self.output = nn.Linear(layers_dim[-1], 1)

    def forward(self, user_indices, item_indices):
        user_emb = self.user_embedding(user_indices)
        item_emb = self.item_embedding(item_indices)
        x = torch.cat([user_emb, item_emb], dim=-1)
        x = self.mlp(x)
        return self.output(x).squeeze()


def train_ncf(
    model: NCF,
    train_loader: DataLoader,
    val_loader: DataLoader,
    lr: float = 1e-3,
    max_epochs: int = 20,
    patience: int = 5,
    device: str = "cpu",
) -> NCF:
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    best_loss = float("inf")
    no_improve = 0

    for epoch in range(max_epochs):
        model.train()
        total_loss = 0
        for user_ids, item_ids, ratings in train_loader:
            user_ids, item_ids, ratings = (
                user_ids.to(device), item_ids.to(device), ratings.to(device)
            )
            optimizer.zero_grad()
            preds = model(user_ids, item_ids)
            loss = criterion(preds, ratings)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        model.eval()
        val_loss = 0
        with torch.no_grad():
            for user_ids, item_ids, ratings in val_loader:
                user_ids, item_ids, ratings = (
                    user_ids.to(device), item_ids.to(device), ratings.to(device)
                )
                preds = model(user_ids, item_ids)
                val_loss += criterion(preds, ratings).item()

        train_loss = total_loss / len(train_loader)
        val_loss = val_loss / len(val_loader)
        logger.info(f"Epoch {epoch+1}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")

        if val_loss < best_loss:
            best_loss = val_loss
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    return model

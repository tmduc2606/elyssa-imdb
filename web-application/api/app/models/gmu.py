from __future__ import annotations

"""Gated Multimodal Unit (GMU) for multi-label genre classification.

Extracted from data-science/notebooks/phase_2_duke_manual_modeling.ipynb and
hardcoded to match the trained state dict dimensions in gmu_genre_best.pt.

Architecture (from notebook):
    encoder_tab  → Linear(26, 256) + ReLU + Dropout
    encoder_text → Linear(768, 256) + ReLU + Dropout
    gate         → Linear(512, 256) + ReLU + Dropout + Linear(256, 2) + Sigmoid
    classifier   → Linear(256, 28)
"""

import torch
import torch.nn as nn

# Hardcoded from the trained state dict shapes — no global lookup required
_DIMS_TAB = 26
_DIMS_TEXT = 768
_DIMS_KG = 0
_HIDDEN_DIM = 256
_OUTPUT_DIM = 28
_DROPOUT = 0.3


class GatedMultimodalUnit(nn.Module):
    """Gated Multimodal Unit for multi-label genre prediction.

    Fuses tabular and text modalities via learned gating weights.
    """

    def __init__(
        self,
        dims_tab: int = _DIMS_TAB,
        dims_text: int = _DIMS_TEXT,
        dims_kg: int = _DIMS_KG,
        hidden_dim: int = _HIDDEN_DIM,
        dropout: float = _DROPOUT,
        output_dim: int = _OUTPUT_DIM,
    ) -> None:
        super().__init__()
        self.use_kg = dims_kg > 0

        # Modality encoders
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

        # Gating network
        gate_in = hidden_dim * (3 if self.use_kg else 2)
        self.gate = nn.Sequential(
            nn.Linear(gate_in, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 2 + (1 if self.use_kg else 0)),
            nn.Sigmoid(),
        )

        # Final classifier
        self.classifier = nn.Linear(hidden_dim, output_dim)

    def forward(self, tab: torch.Tensor, text: torch.Tensor, kg: torch.Tensor | None = None) -> torch.Tensor:
        h_tab = self.encoder_tab(tab)
        h_text = self.encoder_text(text)

        if self.use_kg and kg is not None:
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

        return self.classifier(fused)


def load_gmu_from_state_dict(state_dict_path: str, *, device: str = "cpu") -> GatedMultimodalUnit:
    """Load a GatedMultimodalUnit from a saved state dict (.pt file).

    The DS notebook saved with ``torch.save(model.state_dict(), ...)``
    so we must instantiate the class first, then load the weights.
    Input/output dimensions are derived from the checkpoint itself so a
    retrained model with a different feature set loads without edits.
    """
    sd = torch.load(state_dict_path, map_location=device, weights_only=True)
    dims_tab = sd["encoder_tab.0.weight"].shape[1]
    dims_text = sd["encoder_text.0.weight"].shape[1]
    output_dim = sd["classifier.weight"].shape[0]
    model = GatedMultimodalUnit(
        dims_tab=int(dims_tab),
        dims_text=int(dims_text),
        output_dim=int(output_dim),
    )
    model.load_state_dict(sd)
    model.to(device)
    model.eval()
    return model

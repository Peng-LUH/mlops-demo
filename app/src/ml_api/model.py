import torch
from torch import nn


class SimpleModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(3, 1)

    def forward(self, x):
        return self.linear(x)


class ModelService:
    def __init__(self):
        self.model = SimpleModel()
        self.model.eval()
        self.ready = True

    def predict(self, features: list[float]) -> float:
        if len(features) != 3:
            raise ValueError("Exactly 3 features are required.")

        with torch.no_grad():
            x = torch.tensor([features], dtype=torch.float32)
            y = self.model(x)
            return float(y.item())

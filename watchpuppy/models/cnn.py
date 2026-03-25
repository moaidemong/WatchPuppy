from __future__ import annotations


def build_model(model_name: str = "simple_cnn", num_classes: int = 2):
    if model_name == "simple_cnn":
        return _build_simple_cnn(num_classes=num_classes)
    if model_name == "resnet18":
        return _build_resnet18(num_classes=num_classes)
    if model_name == "mobilenet_v3_small":
        return _build_mobilenet_v3_small(num_classes=num_classes)
    raise ValueError(f"unsupported model_name: {model_name}")


def _build_simple_cnn(num_classes: int = 2):
    import torch.nn as nn

    return nn.Sequential(
        nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(kernel_size=2),
        nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(kernel_size=2),
        nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(kernel_size=2),
        nn.AdaptiveAvgPool2d((1, 1)),
        nn.Flatten(),
        nn.Linear(64, 32),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.2),
        nn.Linear(32, num_classes),
    )


def _build_resnet18(num_classes: int = 2):
    import torch.nn as nn
    from torchvision.models import ResNet18_Weights, resnet18

    model = resnet18(weights=ResNet18_Weights.DEFAULT)
    in_features = model.fc.in_features
    model.fc = nn.Linear(in_features, num_classes)
    return model


def _build_mobilenet_v3_small(num_classes: int = 2):
    import torch.nn as nn
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model

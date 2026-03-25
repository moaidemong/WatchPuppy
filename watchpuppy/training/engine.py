from __future__ import annotations


def fit(
    model,
    train_loader,
    val_loader,
    device: str,
    epochs: int,
    learning_rate: float,
    class_weights: tuple[float, float] | None = None,
):
    import torch

    model.to(device)
    criterion = _build_criterion(class_weights, device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    history: list[dict[str, float]] = []
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        for images, labels, _event_ids in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * labels.size(0)
            train_correct += (logits.argmax(dim=1) == labels).sum().item()
            train_total += labels.size(0)

        val_metrics = evaluate_epoch(model, val_loader, device=device)
        history.append(
            {
                "epoch": float(epoch),
                "train_loss": train_loss / max(train_total, 1),
                "train_accuracy": train_correct / max(train_total, 1),
                "val_loss": val_metrics["loss"],
                "val_accuracy": val_metrics["accuracy"],
                "val_precision_failed_get_up_attempt": val_metrics["precision_failed_get_up_attempt"],
                "val_recall_failed_get_up_attempt": val_metrics["recall_failed_get_up_attempt"],
                "val_f1_failed_get_up_attempt": val_metrics["f1_failed_get_up_attempt"],
            }
        )
    return history


def evaluate_epoch(
    model,
    data_loader,
    device: str,
    class_weights: tuple[float, float] | None = None,
):
    import torch

    model.eval()
    criterion = _build_criterion(class_weights, device)
    total_loss = 0.0
    total_correct = 0
    total_rows = 0
    tp = 0
    tn = 0
    fp = 0
    fn = 0

    with torch.no_grad():
        for images, labels, _event_ids in data_loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            loss = criterion(logits, labels)
            preds = logits.argmax(dim=1)

            total_loss += loss.item() * labels.size(0)
            total_correct += (preds == labels).sum().item()
            total_rows += labels.size(0)
            tp += ((preds == 1) & (labels == 1)).sum().item()
            tn += ((preds == 0) & (labels == 0)).sum().item()
            fp += ((preds == 1) & (labels == 0)).sum().item()
            fn += ((preds == 0) & (labels == 1)).sum().item()

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "loss": total_loss / max(total_rows, 1),
        "accuracy": total_correct / max(total_rows, 1),
        "rows": total_rows,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision_failed_get_up_attempt": precision,
        "recall_failed_get_up_attempt": recall,
        "f1_failed_get_up_attempt": f1,
    }


def _build_criterion(class_weights: tuple[float, float] | None, device: str):
    import torch

    if class_weights is None:
        return torch.nn.CrossEntropyLoss()
    weight_tensor = torch.tensor(class_weights, dtype=torch.float32, device=device)
    return torch.nn.CrossEntropyLoss(weight=weight_tensor)

from __future__ import annotations


def fit(
    model,
    train_loader,
    val_loader,
    device: str,
    epochs: int,
    learning_rate: float,
):
    import torch

    model.to(device)
    criterion = torch.nn.CrossEntropyLoss()
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
            }
        )
    return history


def evaluate_epoch(model, data_loader, device: str):
    import torch

    model.eval()
    criterion = torch.nn.CrossEntropyLoss()
    total_loss = 0.0
    total_correct = 0
    total_rows = 0

    with torch.no_grad():
        for images, labels, _event_ids in data_loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            loss = criterion(logits, labels)

            total_loss += loss.item() * labels.size(0)
            total_correct += (logits.argmax(dim=1) == labels).sum().item()
            total_rows += labels.size(0)

    return {
        "loss": total_loss / max(total_rows, 1),
        "accuracy": total_correct / max(total_rows, 1),
        "rows": total_rows,
    }

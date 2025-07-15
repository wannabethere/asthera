import time

def checkpoint(title: str, last_checkpoint_time: float) -> float:
    """
    Record a checkpoint with the given title and log the elapsed time since the last checkpoint.
    """
    current_time = time.time()
    elapsed = current_time - last_checkpoint_time
    
    print(
        f"Checkpoint: {title} | Elapsed: {elapsed:.4f}s"
    )
    return current_time

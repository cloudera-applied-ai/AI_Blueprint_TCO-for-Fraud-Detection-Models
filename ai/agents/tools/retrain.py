"""Agent tools for data generation and model retraining."""

import os
import sys

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()

sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines"))


def generate_training_data(n_transactions: int = 10000) -> dict:
    """Generate synthetic transactions for retraining.

    Returns summary of generated data including counts and fraud rate.
    """
    if isinstance(n_transactions, str) and n_transactions.isdigit():
        n_transactions = int(n_transactions)
    if not isinstance(n_transactions, (int, float)):
        return {"error": f"n_transactions must be a number, got {type(n_transactions).__name__}"}
    n_transactions = int(n_transactions)
    n_transactions = max(1000, min(n_transactions, 500000))

    from model_training.experiment_runner import generate_additional_data
    return generate_additional_data(n_transactions=n_transactions)


def retrain_model(
    use_corrections: bool = True,
    use_generated_data: bool = True,
    description: str = "",
) -> dict:
    """Kick off a retraining experiment in the background.

    Returns an acknowledgement with the experiment_id.  The caller can
    mention that the experiment is running and the user can check progress
    in the Experiment Lab UI.
    """
    if isinstance(use_corrections, str):
        use_corrections = use_corrections.lower() in ("true", "1", "yes")
    if isinstance(use_generated_data, str):
        use_generated_data = use_generated_data.lower() in ("true", "1", "yes")
    if not isinstance(description, str):
        description = str(description)

    from model_training.experiment_runner import run_experiment_async
    return run_experiment_async(
        use_corrections=use_corrections,
        use_generated_data=use_generated_data,
        description=description,
    )

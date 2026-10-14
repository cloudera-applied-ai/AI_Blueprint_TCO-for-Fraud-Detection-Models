"""CML model endpoint for fraud scoring."""

import os
import sys

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
except NameError:
    sys.path.insert(0, os.path.join(os.getcwd(), "app", "backend", "model_serving"))
from model_utils import score_transaction, get_model, get_feature_names

get_model()
get_feature_names()


def predict(args):
    transaction = args.get("transaction", {})
    explain = args.get("explain", False)
    try:
        return score_transaction(transaction, explain=explain)
    except Exception as e:
        return {"error": str(e)}

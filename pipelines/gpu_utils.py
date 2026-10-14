"""GPU availability detection and library abstraction for RAPIDS integration.

Provides a single import point for GPU-accelerated or CPU-fallback libraries.
All pipeline files import from here instead of doing their own try/except.

Usage:
    from gpu_utils import GPU_ENABLED, pd, np, to_pandas, to_gpu, get_xgboost_gpu_params

Set FRAUD_DETECTION_FORCE_CPU=1 to force CPU mode even when GPU is available.
"""

import os
import logging

logger = logging.getLogger(__name__)

# --- Defaults: CPU libraries ---
import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler, LabelEncoder

GPU_ENABLED = False
HAS_CUDF = False
HAS_CUML = False
HAS_CUPY = False

# Allow forcing CPU mode via environment variable
_force_cpu = os.environ.get("FRAUD_DETECTION_FORCE_CPU", "").lower() in ("1", "true", "yes")

if not _force_cpu:
    try:
        import cudf  # noqa: F811
        HAS_CUDF = True
        logger.info("cuDF available - GPU-accelerated DataFrames enabled")
    except ImportError:
        pass

    try:
        import cupy  # noqa: F811
        HAS_CUPY = True
        logger.info("cuPy available - GPU-accelerated arrays enabled")
    except ImportError:
        pass

    try:
        from cuml.preprocessing import LabelEncoder as CuLabelEncoder  # noqa: F401
        from cuml.preprocessing import RobustScaler as CuRobustScaler  # noqa: F401
        HAS_CUML = True
        logger.info("cuML available - GPU-accelerated ML preprocessing enabled")
    except ImportError:
        pass

GPU_ENABLED = HAS_CUDF and not _force_cpu

if _force_cpu:
    logger.info("GPU forcibly disabled via FRAUD_DETECTION_FORCE_CPU")


# Result of the one-off XGBoost GPU probe below; None until first asked.
_xgb_gpu_probe = None


def xgboost_gpu_available():
    """Whether this XGBoost build can actually train on a local GPU.

    Covers both the CUDA build and AMD's ROCm/HIP build, which takes the same
    device="cuda" string. A tiny real train is the only reliable signal: a
    HIP-enabled binary on an uncompiled-for card (the R9700 / gfx1201 is not an
    official AMDGPU_TARGET) fails at train time, not at import.
    """
    global _xgb_gpu_probe
    if _xgb_gpu_probe is not None:
        return _xgb_gpu_probe

    if _force_cpu:
        _xgb_gpu_probe = False
        return _xgb_gpu_probe

    flavor = _xgboost_build_flavor()
    if flavor is None:
        logger.info("XGBoost has no GPU support compiled in — training on CPU")
        _xgb_gpu_probe = False
        return _xgb_gpu_probe

    try:
        import warnings
        import xgboost as xgb
        probe = xgb.DMatrix(np.zeros((8, 2)), label=np.array([0, 1] * 4))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            xgb.train(
                {"tree_method": "hist", "device": "cuda", "verbosity": 1},
                probe, num_boost_round=1,
            )
        # XGBoost does not raise when the device is missing or unusable — it
        # warns and quietly trains on the CPU. That warning is the real signal.
        downgraded = any(
            "changed from GPU to CPU" in str(w.message) for w in caught
        )
        _xgb_gpu_probe = not downgraded
        if downgraded:
            logger.info("XGBoost %s build found but no usable GPU — training on CPU", flavor)
        else:
            logger.info("XGBoost GPU training available (%s)", flavor)
    except Exception as exc:
        logger.info("XGBoost GPU unavailable, training on CPU: %s", exc)
        _xgb_gpu_probe = False

    return _xgb_gpu_probe


def _xgboost_build_flavor():
    """'CUDA', 'ROCm/HIP' or None, from XGBoost's compiled-in build info."""
    try:
        import xgboost as xgb
        info = xgb.build_info()
    except Exception:
        return None
    if info.get("USE_HIP"):
        return "ROCm/HIP"
    if info.get("USE_CUDA"):
        return "CUDA"
    return None


def gpu_info():
    """Return a summary string of GPU status."""
    if GPU_ENABLED:
        parts = ["GPU ENABLED"]
        if HAS_CUDF:
            parts.append("cuDF")
        if HAS_CUML:
            parts.append("cuML")
        if HAS_CUPY:
            parts.append("cuPy")
        return " | ".join(parts)

    # No RAPIDS, but XGBoost itself may still be GPU-capable — the usual case on
    # ROCm, where cuDF/cuML have no AMD build at all.
    if xgboost_gpu_available():
        flavor = _xgboost_build_flavor() or "GPU"
        return f"XGBoost GPU ({flavor}) | dataframes on CPU (no RAPIDS)"

    return "CPU mode (no RAPIDS)"


def to_pandas(df):
    """Convert a cuDF DataFrame to pandas, or return as-is if already pandas."""
    if HAS_CUDF:
        import cudf
        if isinstance(df, cudf.DataFrame):
            return df.to_pandas()
    return df


def to_gpu(df):
    """Convert a pandas DataFrame to cuDF if GPU is available."""
    if GPU_ENABLED:
        import cudf
        return cudf.from_pandas(df)
    return df


def read_csv(path, **kwargs):
    """Read CSV using cuDF (GPU) or pandas (CPU)."""
    if GPU_ENABLED:
        import cudf
        return cudf.read_csv(path, **kwargs)
    return pd.read_csv(path, **kwargs)


def get_dummies(df, columns, prefix, dtype=int):
    """GPU-aware get_dummies."""
    if GPU_ENABLED:
        import cudf
        # cuDF get_dummies has slightly different API
        result = cudf.get_dummies(df, columns=columns, prefix=prefix)
        return result
    return pd.get_dummies(df, columns=columns, prefix=prefix, dtype=dtype)


def get_label_encoder():
    """Return a GPU or CPU LabelEncoder."""
    if HAS_CUML:
        from cuml.preprocessing import LabelEncoder as CuLabelEncoder
        return CuLabelEncoder()
    return LabelEncoder()


def get_robust_scaler():
    """Return a GPU or CPU RobustScaler."""
    if HAS_CUML:
        from cuml.preprocessing import RobustScaler as CuRobustScaler
        return CuRobustScaler()
    return RobustScaler()


def _to_numpy(obj):
    """Safely convert a cuDF/cuPy/GPU object to a numpy array."""
    if hasattr(obj, 'to_numpy'):
        return obj.to_numpy()
    if hasattr(obj, 'get'):
        return obj.get()
    return np.array(obj)


def label_encoder_to_sklearn(le, classes=None):
    """Convert a cuML LabelEncoder to sklearn for pickle compatibility."""
    if HAS_CUML:
        from cuml.preprocessing import LabelEncoder as CuLabelEncoder
        if isinstance(le, CuLabelEncoder):
            sklearn_le = LabelEncoder()
            if classes is not None:
                sklearn_le.classes_ = classes if isinstance(classes, np.ndarray) else _to_numpy(classes)
            elif hasattr(le, 'classes_'):
                sklearn_le.classes_ = _to_numpy(le.classes_)
            return sklearn_le
    return le


def robust_scaler_to_sklearn(scaler):
    """Convert a cuML RobustScaler to sklearn for pickle compatibility."""
    if HAS_CUML:
        from cuml.preprocessing import RobustScaler as CuRobustScaler
        if isinstance(scaler, CuRobustScaler):
            sklearn_scaler = RobustScaler()
            sklearn_scaler.center_ = _to_numpy(scaler.center_)
            sklearn_scaler.scale_ = _to_numpy(scaler.scale_)
            sklearn_scaler.n_features_in_ = scaler.n_features_in_ if hasattr(scaler, 'n_features_in_') else 1
            return sklearn_scaler
    return scaler


def sin(series):
    """Compute sin on a DataFrame column (cuPy or numpy)."""
    if HAS_CUPY and GPU_ENABLED:
        import cupy
        try:
            return cupy.sin(cupy.asarray(series.values))
        except Exception:
            pass
    return np.sin(series.values)


def cos(series):
    """Compute cos on a DataFrame column (cuPy or numpy)."""
    if HAS_CUPY and GPU_ENABLED:
        import cupy
        try:
            return cupy.cos(cupy.asarray(series.values))
        except Exception:
            pass
    return np.cos(series.values)


def get_xgboost_gpu_params():
    """Return XGBoost params for GPU training if available.

    RAPIDS implies a working CUDA GPU. Without it, the probe decides — that is
    the ROCm path, where XGBoost can be GPU-backed while the dataframes stay on
    the CPU, and the path that silently falls back when the card can't do it.
    """
    if GPU_ENABLED or xgboost_gpu_available():
        return {"tree_method": "hist", "device": "cuda"}
    return {"tree_method": "hist"}

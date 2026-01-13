import pandas as pd

def coerce_cell_value(df, col_name, text):
    text = "" if text is None else str(text)
    try:
        dtype = df[col_name].dtype
    except Exception:
        dtype = object

    stripped = text.strip()
    if pd.api.types.is_integer_dtype(dtype):
        if stripped == "":
            return pd.NA
        return int(stripped)

    if pd.api.types.is_float_dtype(dtype):
        if stripped == "":
            return float("nan")
        return float(stripped)

    if pd.api.types.is_bool_dtype(dtype):
        if stripped == "":
            return pd.NA
        lowered = stripped.lower()
        if lowered in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "f", "no", "n", "off"}:
            return False
        raise ValueError(f"Cannot coerce '{text}' to boolean")

    if pd.api.types.is_datetime64_any_dtype(dtype):
        if stripped == "":
            return pd.NaT
        return pd.to_datetime(stripped, errors="raise")

    return text

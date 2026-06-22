import json
import sys


META_KEY = "__vixl_metadata__"


def fail(message):
    print(message, file=sys.stderr)
    return 1


def require_runtime():
    try:
        import pandas as pd
        import tables  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "HDF5 support requires the vixl-managed PyTables runtime. "
            "Run: bash install.sh from <vixl-source-path>"
        ) from exc
    return pd


def clean_value(value):
    if value is None:
        return ""
    return str(value)


def frame_rows(df, pd):
    df = df.astype(object).where(pd.notna(df), "")
    return [[clean_value(value) for value in row] for row in df.to_numpy().tolist()]


def load(path):
    pd = require_runtime()
    sheets = []
    active_sheet = 0
    with pd.HDFStore(path, mode="r") as store:
        keys = [key for key in store.keys() if key != "/" + META_KEY]
        if "/" + META_KEY in store.keys():
            try:
                meta_df = store.get(META_KEY)
                if not meta_df.empty and "active_sheet" in meta_df:
                    active_sheet = int(meta_df["active_sheet"].iloc[0])
            except Exception:
                active_sheet = 0
        for i, key in enumerate(keys):
            try:
                obj = store.get(key)
            except Exception:
                continue
            if not hasattr(obj, "columns"):
                continue
            name = key.lstrip("/") or f"Sheet{i + 1}"
            widths = []
            try:
                storer = store.get_storer(key)
                name = getattr(storer.attrs, "vixl_sheet_name", name)
                widths = list(getattr(storer.attrs, "vixl_column_widths", []))
            except Exception:
                pass
            sheets.append(
                {
                    "name": clean_value(name),
                    "columns": [clean_value(col) for col in obj.columns.tolist()],
                    "rows": frame_rows(obj, pd),
                    "column_widths": [int(width) for width in widths if int(width) >= 0],
                }
            )
    print(json.dumps({"active_sheet": active_sheet, "sheets": sheets}))
    return 0


def save(path):
    pd = require_runtime()
    payload = json.load(sys.stdin)
    sheets = payload.get("sheets") or []
    active_sheet = int(payload.get("active_sheet") or 0)
    with pd.HDFStore(path, mode="w") as store:
        for i, sheet in enumerate(sheets):
            key = f"sheet_{i + 1}"
            columns = [clean_value(col) for col in sheet.get("columns") or ["col_a"]]
            rows = sheet.get("rows") or []
            normalized_rows = []
            for row in rows:
                values = [clean_value(value) for value in row]
                if len(values) < len(columns):
                    values.extend([""] * (len(columns) - len(values)))
                normalized_rows.append(values[: len(columns)])
            if not normalized_rows:
                normalized_rows = [["" for _ in columns]]
            df = pd.DataFrame(normalized_rows, columns=columns)
            store.put(key, df, format="fixed")
            storer = store.get_storer(key)
            storer.attrs.vixl_sheet_name = clean_value(sheet.get("name") or f"Sheet{i + 1}")
            storer.attrs.vixl_column_widths = [
                int(width) for width in (sheet.get("column_widths") or []) if int(width) >= 0
            ]
        store.put(META_KEY, pd.DataFrame([{"active_sheet": active_sheet}]), format="fixed")
    return 0


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in {"load", "save"}:
        return fail("usage: hdf_bridge.py load|save <path>")
    try:
        if sys.argv[1] == "load":
            return load(sys.argv[2])
        return save(sys.argv[2])
    except Exception as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

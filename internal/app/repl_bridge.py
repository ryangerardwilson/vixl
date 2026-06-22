import code
import contextlib
import io
import json
import platform
import sys
import traceback


try:
    import numpy as np
    import pandas as pd
except Exception as exc:
    print(
        json.dumps(
            {
                "ready": False,
                "error": "Python REPL requires numpy and pandas: " + str(exc),
            }
        ),
        flush=True,
    )
    raise SystemExit(0)


console = code.InteractiveConsole(
    {
        "__name__": "__vixl_repl__",
        "np": np,
        "pd": pd,
        "df": pd.DataFrame(),
    }
)

print(
    json.dumps(
        {
            "ready": True,
            "banner": (
                "python "
                + platform.python_version()
                + "  np "
                + np.__version__
                + "  pd "
                + pd.__version__
            ),
        }
    ),
    flush=True,
)

for raw in sys.stdin:
    try:
        request = json.loads(raw)
        if "init_df" in request:
            frame = request.get("init_df") or {}
            columns = [str(column) for column in frame.get("columns") or []]
            rows = frame.get("rows") or []
            console.locals["df"] = pd.DataFrame(rows, columns=columns)
            print(
                json.dumps(
                    {
                        "output": "df loaded: "
                        + str(len(console.locals["df"]))
                        + " rows x "
                        + str(len(console.locals["df"].columns))
                        + " columns\n",
                        "more": False,
                    }
                ),
                flush=True,
            )
            continue
        source = str(request.get("code", ""))
    except Exception as exc:
        print(json.dumps({"output": "invalid repl request: " + str(exc), "more": False}), flush=True)
        continue

    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            more = console.push(source)
        output = stdout.getvalue() + stderr.getvalue()
        print(json.dumps({"output": output, "more": bool(more)}), flush=True)
    except Exception:
        print(json.dumps({"output": traceback.format_exc(), "more": False}), flush=True)

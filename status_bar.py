import os
import time


def render_status(context, width):
    """
    context keys: status_msg, status_until, focus, df_mode, df_shape, file_path,
                   page_total, page_index, page_start, page_end, total_rows
    """
    text = ""
    now = time.time()
    if context.get('status_msg') and now < context.get('status_until', 0):
        text = f" {context['status_msg']}"
    else:
        focus = context.get('focus', 0)
        df_mode = context.get('df_mode', 'normal')
        if focus == 0:
            if df_mode == 'cell_insert':
                mode = 'DF:CELL-INSERT'
            elif df_mode == 'cell_normal':
                mode = 'DF:CELL-NORMAL'
            else:
                mode = 'DF'
        elif focus == 1:
            mode = 'CMD'
        else:
            mode = 'DF'
        fname = context.get('file_path') or ''
        if fname:
            fname = os.path.basename(fname)
        shape = context.get('df_shape', '')
        page_total = context.get('page_total', 1)
        page_index = context.get('page_index', 1)
        page_start = context.get('page_start', 0)
        page_end = context.get('page_end', page_start)
        total_rows = context.get('total_rows', 0)
        page_info = f"Page {page_index}/{page_total} rows {page_start}-{max(page_start, page_end - 1)} of {total_rows}"
        text = f" {mode} | {fname} | {shape} | {page_info}"

    return text.ljust(width)[:width]

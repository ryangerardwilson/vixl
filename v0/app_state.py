class AppState:
    """
    Central mutable application state for v0.
    This class intentionally holds all state without enforcing abstractions yet.
    """

    def __init__(self):
        # Data
        self.df = None
        self.rows = 0
        self.cols = 0
        self.col_names = []
        self.index_name = ''
        self.index_values = []

        # Layout
        self.widths = []
        self.index_width = 0
        self.voffset = 0
        self.hoffset = 0

        # Cursor & modes
        self.curr_row = 0
        self.curr_col = 0
        self.mode = 'normal'
        self.header_mode = False

        # Cell editing
        self.cell_cursor = 0
        self.cell_hoffset = 0
        self.edited_value = ''

        # Clipboard / misc
        self.cut_buffer = None
        self.leader_active = False

        # File
        self.file_path = None

        # Transient status message
        self.status_message = None
        self.status_message_until = 0

        # Command mode
        self.command_buffer = ''
        self.command_output = None

        # Display toggles
        self.show_all_rows = False

        # Highlight mode: 'cell', 'row', or 'column'
        self.highlight_mode = 'cell'

        # Horizontal scroll
        self.col_offset = 0

package app

import (
	"regexp"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/ryangerardwilson/vixl/internal/sheet"
)

var ansiPattern = regexp.MustCompile(`\x1b\[[0-9;]*m`)

func TestViewFillsConfiguredHeightWithoutVirtualRows(t *testing.T) {
	m := model{
		sheet:  sheet.Sheet{Columns: []string{"A"}, Rows: rows(10), Path: "test.csv"},
		col:    0,
		status: "ready",
		width:  100,
		height: 18,
	}

	view := m.View()
	lines := strings.Split(view, "\n")
	if len(lines) != m.height {
		t.Fatalf("view height = %d, want %d\n%s", len(lines), m.height, view)
	}

	if strings.Contains(view, "hjkl move") {
		t.Fatalf("normal view should not show shortcut footer:\n%s", view)
	}
	if strings.Contains(view, "vixl test.csv") {
		t.Fatalf("normal view should not show title/path:\n%s", view)
	}
	if strings.Contains(view, "ready") {
		t.Fatalf("normal view should not show idle ready status:\n%s", view)
	}

	row10Line := lines[10]
	if !strings.HasPrefix(row10Line, "10  ") {
		t.Fatalf("row 10 line = %q, want row 10", row10Line)
	}
	firstBlankLine := lines[11]
	if firstBlankLine != "" {
		t.Fatalf("line after row 10 = %q, want blank", firstBlankLine)
	}
	if strings.Contains(view, "11  ") {
		t.Fatalf("normal view should not show virtual row 11:\n%s", view)
	}
	if len(m.sheet.Rows) != 10 {
		t.Fatalf("sheet rows mutated = %d, want 10", len(m.sheet.Rows))
	}
}

func TestColumnWindowKeepsFocusedCellVisible(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"A", "B", "C", "D", "E"},
			Rows:    [][]string{{"a1", "b1", "c1", "d1", "e1"}},
		},
		col:       4,
		colWidths: map[int]int{0: defaultColumnWidth, 1: defaultColumnWidth, 2: defaultColumnWidth, 3: defaultColumnWidth, 4: defaultColumnWidth},
		width:     rowNumberWidth + defaultColumnWidth*3,
		height:    10,
		status:    "ready",
	}

	start, end := m.columnWindow()
	if start != 2 || end != 5 {
		t.Fatalf("column window = %d:%d, want 2:5", start, end)
	}

	lines := strings.Split(m.View(), "\n")
	headerLine := lines[0]
	if strings.Contains(headerLine, "A") || strings.Contains(headerLine, "B") {
		t.Fatalf("header should scroll past hidden columns: %q", headerLine)
	}
	if !strings.Contains(headerLine, "C") || !strings.Contains(headerLine, "D") || !strings.Contains(headerLine, "E") {
		t.Fatalf("header should show focused column window: %q", headerLine)
	}
	if !strings.Contains(lines[1], "e1") {
		t.Fatalf("focused cell value should be visible: %q", lines[1])
	}
}

func TestColumnWidthKeysResizeFocusedColumn(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"A", "B"},
			Rows:    [][]string{{"a1", "b1"}},
		},
		col:    1,
		width:  100,
		height: 10,
		status: "saved",
	}

	startWidth := m.columnWidth(1)
	updated, _ := m.updateKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(">")})
	m = updated.(model)
	if got := m.columnWidth(1); got != startWidth+1 {
		t.Fatalf("> width = %d, want %d", got, startWidth+1)
	}
	if m.status != "" {
		t.Fatalf("resize status = %q, want hidden", m.status)
	}

	updated, _ = m.updateKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("<")})
	m = updated.(model)
	if got := m.columnWidth(1); got != startWidth {
		t.Fatalf("< width = %d, want %d", got, startWidth)
	}
}

func TestColumnWidthCannotShrinkBelowMinimum(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"A"},
			Rows:    [][]string{{"a1"}},
		},
		col: 0,
	}

	for range 20 {
		m.resizeFocusedColumn(-4)
	}
	if got := m.columnWidth(0); got != minColumnWidth {
		t.Fatalf("minimum width = %d, want %d", got, minColumnWidth)
	}
}

func TestColumnWidthSliceIncludesOnlyRuntimeWidths(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"A", "B"},
			Rows:    [][]string{{"a1", "b1"}},
		},
	}
	if widths := m.columnWidthSlice(); widths != nil {
		t.Fatalf("default width slice = %#v, want nil", widths)
	}

	m.colWidths = map[int]int{1: 20}
	widths := m.columnWidthSlice()
	if len(widths) != 2 || widths[0] != 0 || widths[1] != 20 {
		t.Fatalf("width slice = %#v, want [0 20]", widths)
	}
}

func TestColumnWindowUsesRuntimeColumnWidths(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"A", "B", "C"},
			Rows:    [][]string{{"a1", "b1", "c1"}},
		},
		col:       2,
		colWidths: map[int]int{1: 20, 2: 10},
		width:     rowNumberWidth + 30,
		height:    10,
		status:    "ready",
	}

	start, end := m.columnWindow()
	if start != 1 || end != 3 {
		t.Fatalf("column window = %d:%d, want 1:3", start, end)
	}

	headerLine := strings.Split(m.View(), "\n")[0]
	if strings.Contains(headerLine, "A") {
		t.Fatalf("header should not include column A: %q", headerLine)
	}
	if !strings.Contains(headerLine, "B") || !strings.Contains(headerLine, "C") {
		t.Fatalf("header should include resized focused window: %q", headerLine)
	}
}

func TestAutoColumnWidthsUseContent(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"name", "age", "city", "age3"},
			Rows: [][]string{
				{"John", "30", "New York", "303030"},
				{"Alice", "35", "San Francisco", "353535"},
			},
		},
	}

	if got := m.columnWidth(1); got != len("age")+autoColumnPadding {
		t.Fatalf("age width = %d, want compact header width %d", got, len("age")+autoColumnPadding)
	}
	if got := m.columnWidth(2); got <= m.columnWidth(1) {
		t.Fatalf("city width = %d, should be wider than age width %d", got, m.columnWidth(1))
	}
	if got := m.columnWidth(3); got != len("303030")+autoColumnPadding {
		t.Fatalf("age3 width = %d, want %d", got, len("303030")+autoColumnPadding)
	}
}

func TestShiftHLNavigatesSheets(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns:      []string{"name"},
			Rows:         [][]string{{"Ada"}},
			ColumnWidths: []int{8},
			Worksheets: []sheet.Worksheet{
				{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}, ColumnWidths: []int{8}},
				{Name: "Scores", Columns: []string{"score"}, Rows: [][]string{{"99"}}, ColumnWidths: []int{12}},
			},
		},
		colWidths: map[int]int{0: 9},
		width:     40,
		height:    8,
		status:    "ready",
	}

	m = pressRunes(m, "L")
	if m.sheet.SheetName() != "Scores" || m.sheet.Rows[0][0] != "99" {
		t.Fatalf("after L active=%q rows=%#v", m.sheet.SheetName(), m.sheet.Rows)
	}
	if got := m.colWidths[0]; got != 12 {
		t.Fatalf("scores width = %d, want 12", got)
	}
	if m.status != "" {
		t.Fatalf("sheet status = %q, want no repeated sheet status", m.status)
	}

	m = pressRunes(m, "H")
	if m.sheet.SheetName() != "People" || m.sheet.Rows[0][0] != "Ada" {
		t.Fatalf("after H active=%q rows=%#v", m.sheet.SheetName(), m.sheet.Rows)
	}
	if got := m.sheet.Worksheets[0].ColumnWidths[0]; got != 9 {
		t.Fatalf("people manual width persisted in model = %d, want 9", got)
	}
}

func TestSheetMenuAppearsForWorkbookFormats(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Path:        "book.xlsx",
			Columns:     []string{"name"},
			Rows:        [][]string{{"Ada"}},
			Worksheets:  []sheet.Worksheet{{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}}},
			ActiveSheet: 0,
		},
		width:  40,
		height: 8,
		status: "ready",
	}

	view := m.View()
	if !strings.Contains(view, "[People]") {
		t.Fatalf("workbook view should show sheet menu:\n%s", view)
	}
	if got := len(strings.Split(view, "\n")); got != m.height {
		t.Fatalf("view height = %d, want %d\n%s", got, m.height, view)
	}

	m.sheet.Path = "data.csv"
	view = m.View()
	if strings.Contains(view, "[People]") {
		t.Fatalf("csv view should not show sheet menu:\n%s", view)
	}
}

func TestSheetMenuIsCompact(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Path:    "book.xlsx",
			Columns: []string{"score"},
			Rows:    [][]string{{"99"}},
			Worksheets: []sheet.Worksheet{
				{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}},
				{Name: "Scores", Columns: []string{"score"}, Rows: [][]string{{"99"}}},
				{Name: "Archive", Columns: []string{"old"}, Rows: [][]string{{"1"}}},
			},
			ActiveSheet: 1,
		},
		width:  60,
		height: 8,
		status: "ready",
	}

	menu := m.renderSheetMenu()
	if !strings.Contains(menu, "[Scores] 2/3") {
		t.Fatalf("compact menu = %q, want active sheet and count", menu)
	}
	if strings.Contains(menu, "People") || strings.Contains(menu, "Archive") {
		t.Fatalf("compact menu should not repeat inactive sheet names: %q", menu)
	}
}

func TestLeaderNSAddsSheetForWorkbook(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Path:        "book.xlsx",
			Columns:     []string{"name"},
			Rows:        [][]string{{"Ada"}},
			Worksheets:  []sheet.Worksheet{{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}}},
			ActiveSheet: 0,
		},
		width:  40,
		height: 8,
		status: "ready",
	}

	m = pressRunes(m, ",ns")
	if m.sheet.SheetCount() != 2 || m.sheet.SheetName() != "Sheet1" {
		t.Fatalf("after ,ns sheet count/name = %d/%q", m.sheet.SheetCount(), m.sheet.SheetName())
	}
	if m.row != 0 || m.col != 0 {
		t.Fatalf("new sheet focus = row %d col %d, want 0/0", m.row, m.col)
	}
	if !strings.Contains(m.View(), "[Sheet1]") {
		t.Fatalf("new active sheet missing from menu:\n%s", m.View())
	}
	if m.status != "sheet added" {
		t.Fatalf(",ns status = %q, want sheet added", m.status)
	}
}

func TestSheetNotificationsUseSeparateTransientLine(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Path:        "book.xlsx",
			Columns:     []string{"name"},
			Rows:        [][]string{{"Ada"}},
			Worksheets:  []sheet.Worksheet{{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}}},
			ActiveSheet: 0,
		},
		width:  40,
		height: 8,
		status: "ready",
	}

	m = pressRunes(m, ",ns")
	lines := strings.Split(m.View(), "\n")
	statusLine := lines[len(lines)-2]
	sheetLine := lines[len(lines)-1]
	if !strings.Contains(statusLine, "sheet added") {
		t.Fatalf("status line = %q, want sheet added", statusLine)
	}
	if strings.Contains(sheetLine, "sheet added") {
		t.Fatalf("sheet indicator should not contain notification: %q", sheetLine)
	}
	if !strings.Contains(sheetLine, "[Sheet1] 2/2") {
		t.Fatalf("sheet indicator = %q, want [Sheet1] 2/2", sheetLine)
	}

	m = clearNotification(m)
	lines = strings.Split(m.View(), "\n")
	if lines[len(lines)-2] != "" {
		t.Fatalf("status line after timeout = %q, want blank", lines[len(lines)-2])
	}
	if !strings.Contains(lines[len(lines)-1], "[Sheet1] 2/2") {
		t.Fatalf("sheet indicator after timeout = %q", lines[len(lines)-1])
	}
}

func TestLeaderNSRejectsSingleSheetCSV(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Path:    "data.csv",
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
		},
		width:  40,
		height: 8,
		status: "ready",
	}

	m = pressRunes(m, ",ns")
	if m.sheet.SheetCount() != 1 {
		t.Fatalf("csv sheet count = %d, want 1", m.sheet.SheetCount())
	}
	if m.status != "current format is single-sheet" {
		t.Fatalf("csv ,ns status = %q", m.status)
	}
}

func TestInputModesUseBlinkingBlockCursor(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
		},
		width:  40,
		height: 8,
		status: "ready",
	}

	updated, cmd := m.updateKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(":")})
	m = updated.(model)
	if cmd == nil {
		t.Fatal("entering command input should start cursor blink")
	}
	if m.inputMode != "command" || !m.cursorOn || m.cursorID == 0 {
		t.Fatalf("input cursor state = mode %q cursorOn %v cursorID %d", m.inputMode, m.cursorOn, m.cursorID)
	}
	line := m.renderStatusLine()
	if got, want := lipgloss.Width(line), lipgloss.Width(": ")+1; got != want {
		t.Fatalf("prompt width = %d, want %d for prompt plus cursor", got, want)
	}

	m = blinkCursor(m)
	if m.cursorOn {
		t.Fatal("cursor should toggle off on blink")
	}
	hiddenLine := m.renderStatusLine()
	if lipgloss.Width(hiddenLine) != lipgloss.Width(line) {
		t.Fatalf("hidden cursor changed prompt width: %q vs %q", hiddenLine, line)
	}

	activeCursorID := m.cursorID
	m = pressEnter(m)
	if m.inputMode != "" || m.cursorOn {
		t.Fatalf("input should close and hide cursor, mode=%q cursorOn=%v", m.inputMode, m.cursorOn)
	}
	updated, _ = m.Update(blinkCursorMsg(activeCursorID))
	m = updated.(model)
	if m.cursorOn {
		t.Fatal("stale blink should not restore cursor after input closes")
	}
}

func TestFixedWidthInputCursorStaysAtEditPoint(t *testing.T) {
	m := model{
		inputMode: "rename_sheet",
		input:     "Sh",
		cursorOn:  true,
		width:     40,
		height:    8,
	}

	field := m.renderInputText(8, cellStyle)
	if got, want := lipgloss.Width(field), 8; got != want {
		t.Fatalf("field width = %d, want %d", got, want)
	}
	if plain := stripANSI(field); strings.Index(plain, "  ") != 2 {
		t.Fatalf("cursor placeholder should be directly after input in %q", plain)
	}

	repl := m.renderREPLPrompt(12)
	if got, want := lipgloss.Width(repl), 12; got != want {
		t.Fatalf("repl prompt width = %d, want %d", got, want)
	}
	if plain := stripANSI(repl); strings.Index(plain, "  ") != len(">>> Sh") {
		t.Fatalf("repl cursor placeholder should be directly after input in %q", plain)
	}
}

func TestLeaderRNSRenamesSheetForWorkbook(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Path:        "book.xlsx",
			Columns:     []string{"name"},
			Rows:        [][]string{{"Ada"}},
			Worksheets:  []sheet.Worksheet{{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}}},
			ActiveSheet: 0,
		},
		width:  40,
		height: 8,
		status: "ready",
	}

	m = pressRunes(m, ",rns")
	if m.inputMode != "rename_sheet" || m.input != "People" {
		t.Fatalf(",rns input mode/input = %q/%q, want rename_sheet/People", m.inputMode, m.input)
	}
	if !m.cursorOn {
		t.Fatal("rename sheet modal should start with visible cursor")
	}
	if !strings.Contains(m.prompt(), "rename sheet People") {
		t.Fatalf("rename prompt = %q", m.prompt())
	}
	modal := m.renderRenameSheetModal()
	m = blinkCursor(m)
	if m.cursorOn {
		t.Fatal("rename sheet modal cursor should toggle off on blink")
	}
	if lipgloss.Width(m.renderRenameSheetModal()) != lipgloss.Width(modal) {
		t.Fatal("rename sheet modal cursor blink should not change modal width")
	}
	view := m.View()
	if !strings.Contains(view, "rename sheet") || !strings.Contains(view, "People") {
		t.Fatalf("rename sheet modal missing title/input:\n%s", view)
	}
	lines := strings.Split(view, "\n")
	if strings.Contains(lines[len(lines)-2], "rename sheet") {
		t.Fatalf("rename sheet prompt should be modal, not footer status: %q", lines[len(lines)-2])
	}
	if !strings.Contains(lines[len(lines)-1], "[People]") {
		t.Fatalf("sheet indicator should stay anchored while modal is open: %q", lines[len(lines)-1])
	}

	m.input = "Metrics"
	m = pressEnter(m)
	if m.sheet.SheetName() != "Metrics" {
		t.Fatalf("renamed sheet = %q, want Metrics", m.sheet.SheetName())
	}
	if m.status != "renamed sheet" {
		t.Fatalf("rename sheet status = %q, want renamed sheet", m.status)
	}
	view = m.View()
	lines = strings.Split(view, "\n")
	if !strings.Contains(lines[len(lines)-2], "renamed sheet") {
		t.Fatalf("rename notification should render above sheet indicator:\n%s", view)
	}
	if !strings.Contains(lines[len(lines)-1], "[Metrics]") || strings.Contains(lines[len(lines)-1], "[People]") {
		t.Fatalf("renamed sheet indicator not updated:\n%s", view)
	}
}

func TestLeaderRNSRejectsSingleSheetCSV(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Path:    "data.csv",
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
		},
		width:  40,
		height: 8,
		status: "ready",
	}

	m = pressRunes(m, ",rns")
	if m.inputMode != "" {
		t.Fatalf("csv ,rns input mode = %q, want empty", m.inputMode)
	}
	if m.status != "current format is single-sheet" {
		t.Fatalf("csv ,rns status = %q", m.status)
	}
}

func TestLeaderREPLTogglesRightSidebar(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
			Path:    "data.csv",
		},
		width:  80,
		height: 10,
		status: "ready",
	}

	m = pressRunes(m, ",repl")
	if !m.replVisible || !m.replStarting || m.inputMode != "repl" || !m.cursorOn {
		t.Fatalf("repl state visible=%v starting=%v mode=%q cursor=%v", m.replVisible, m.replStarting, m.inputMode, m.cursorOn)
	}
	view := m.View()
	if got := len(strings.Split(view, "\n")); got != m.height {
		t.Fatalf("repl view height = %d, want %d\n%s", got, m.height, view)
	}
	plain := stripANSI(view)
	lines := strings.Split(plain, "\n")
	if !strings.Contains(lines[0], "|>>> ") {
		t.Fatalf("empty repl prompt should start the transcript:\n%s", plain)
	}
	if strings.Contains(plain, "| python  np  pd") || strings.Contains(plain, "starting python repl") {
		t.Fatalf("fresh repl sidebar should not show startup chrome:\n%s", plain)
	}

	updated, _ := m.updateKey(tea.KeyMsg{Type: tea.KeyEsc})
	m = updated.(model)
	if m.replVisible || m.inputMode != "" || m.cursorOn {
		t.Fatalf("esc should hide repl, visible=%v mode=%q cursor=%v", m.replVisible, m.inputMode, m.cursorOn)
	}
	if !m.replStarting {
		t.Fatal("hiding repl should preserve startup state")
	}
}

func TestREPLPromptFollowsHistoryLikeTerminal(t *testing.T) {
	m := model{
		inputMode: "repl",
		cursorOn:  true,
		input:     "df",
		replLines: []string{">>> df.columns", "Index(['name'], dtype='object')"},
	}

	sidebar := stripANSI(m.renderREPLSidebar(6, 32))
	lines := strings.Split(sidebar, "\n")
	if !strings.Contains(lines[0], "|>>> df.columns") {
		t.Fatalf("first repl line = %q, want history", lines[0])
	}
	if !strings.Contains(lines[1], "|Index(['name'], dtype='object')") {
		t.Fatalf("second repl line = %q, want output", lines[1])
	}
	if !strings.Contains(lines[2], "|>>> df") {
		t.Fatalf("prompt should follow history, sidebar:\n%s", sidebar)
	}
	if strings.Contains(lines[0], "|>>> df ") {
		t.Fatalf("live prompt should not be pinned to top:\n%s", sidebar)
	}
}

func TestREPLHidePreservesInputAndHistory(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
			Path:    "data.csv",
		},
		width:       80,
		height:      10,
		replVisible: true,
		inputMode:   "repl",
		cursorOn:    true,
		repl:        &replSession{},
		replLines:   []string{">>> df.columns", "Index(['name'], dtype='object')"},
	}

	updated, _ := m.updateKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'d'}})
	m = updated.(model)
	updated, _ = m.updateKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'f'}})
	m = updated.(model)
	updated, _ = m.updateKey(tea.KeyMsg{Type: tea.KeyEsc})
	m = updated.(model)

	if m.replVisible || m.inputMode != "" {
		t.Fatalf("esc should hide repl input, visible=%v mode=%q", m.replVisible, m.inputMode)
	}
	if m.repl == nil || len(m.replLines) != 2 || m.replInput != "df" {
		t.Fatalf("hidden repl state lost: repl=%v lines=%#v input=%q", m.repl, m.replLines, m.replInput)
	}

	_ = m.toggleREPL()
	if !m.replVisible || m.inputMode != "repl" || m.input != "df" {
		t.Fatalf("reopen repl state visible=%v mode=%q input=%q", m.replVisible, m.inputMode, m.input)
	}
}

func TestREPLCtrlLClearsScreenOnly(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
			Path:    "data.csv",
		},
		width:       80,
		height:      10,
		replVisible: true,
		inputMode:   "repl",
		cursorOn:    true,
		repl:        &replSession{},
		replLines:   []string{">>> df.columns", "Index(['name'], dtype='object')"},
		input:       "df",
		replInput:   "df",
	}

	updated, _ := m.updateKey(tea.KeyMsg{Type: tea.KeyCtrlL})
	m = updated.(model)
	if len(m.replLines) != 0 {
		t.Fatalf("ctrl+l should clear repl screen: %#v", m.replLines)
	}
	if m.repl == nil || !m.replVisible || m.input != "df" || m.replInput != "df" {
		t.Fatalf("ctrl+l should preserve session and input: repl=%v visible=%v input=%q saved=%q", m.repl, m.replVisible, m.input, m.replInput)
	}
}

func TestREPLResultUpdatesSidebarHistory(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
			Path:    "data.csv",
		},
		width:       80,
		height:      10,
		replVisible: true,
		inputMode:   "repl",
		cursorOn:    true,
		replBusy:    true,
		replLines:   []string{">>> np.arange(3).tolist()"},
	}

	m.handleREPLResult(replResultMsg{output: "[0, 1, 2]\n"})
	if m.replBusy || m.replMore {
		t.Fatalf("repl result state busy=%v more=%v", m.replBusy, m.replMore)
	}
	view := m.View()
	if !strings.Contains(view, "[0, 1, 2]") {
		t.Fatalf("repl result missing from sidebar:\n%s", view)
	}
}

func TestHiddenREPLMessagesPreserveState(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"name"},
			Rows:    [][]string{{"Ada"}},
			Path:    "data.csv",
		},
		width:        80,
		height:       10,
		replStarting: true,
	}

	m.handleREPLStarted(replStartedMsg{banner: "python ready", initOutput: "df loaded"})
	if m.replStarting || len(m.replLines) != 0 {
		t.Fatalf("hidden start should finish quietly: starting=%v lines=%#v", m.replStarting, m.replLines)
	}
	m.handleREPLResult(replResultMsg{output: "late output"})
	if len(m.replLines) != 1 || m.replLines[0] != "late output" {
		t.Fatalf("hidden result should preserve output: %#v", m.replLines)
	}
}

func TestREPLBridgePreloadsNumpyPandasAndDataFrame(t *testing.T) {
	frame := replDataFrame{
		Columns: []string{"exercise", "sets", "reps"},
		Rows: [][]string{
			{"Jumping jacks", "2", "15"},
			{"Arm circles", "2", "9"},
		},
	}
	session, banner, initOutput, err := startREPLSession(frame)
	if err != nil {
		t.Skipf("python repl runtime unavailable: %v", err)
	}
	defer session.Close()
	if !strings.Contains(banner, "np") || !strings.Contains(banner, "pd") {
		t.Fatalf("repl banner = %q, want numpy/pandas aliases", banner)
	}
	if !strings.Contains(initOutput, "df loaded: 2 rows x 3 columns") {
		t.Fatalf("repl init output = %q", initOutput)
	}
	output, more, err := session.Eval("np.arange(3).tolist()")
	if err != nil {
		t.Fatal(err)
	}
	if more || !strings.Contains(output, "[0, 1, 2]") {
		t.Fatalf("numpy eval output=%q more=%v", output, more)
	}
	output, more, err = session.Eval("pd.DataFrame({'a': [1]}).shape")
	if err != nil {
		t.Fatal(err)
	}
	if more || !strings.Contains(output, "(1, 1)") {
		t.Fatalf("pandas eval output=%q more=%v", output, more)
	}
	output, more, err = session.Eval("df.columns.tolist()")
	if err != nil {
		t.Fatal(err)
	}
	if more || !strings.Contains(output, "['exercise', 'sets', 'reps']") {
		t.Fatalf("df columns output=%q more=%v", output, more)
	}
	output, more, err = session.Eval("df.shape")
	if err != nil {
		t.Fatal(err)
	}
	if more || !strings.Contains(output, "(2, 3)") {
		t.Fatalf("df shape output=%q more=%v", output, more)
	}
}

func TestLeaderXARTogglesAllRowsExpanded(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"A", "B"},
			Rows:    [][]string{{"alpha beta gamma", "short"}},
		},
		colWidths: map[int]int{0: 6, 1: 6},
		width:     rowNumberWidth + 12,
		height:    8,
		status:    "ready",
	}

	view := m.View()
	if strings.Contains(view, "beta") {
		t.Fatalf("collapsed row should not show wrapped continuation:\n%s", view)
	}

	m = pressRunes(m, ",xar")
	if !m.expandAll {
		t.Fatal(",xar should enable all-row expansion")
	}
	if m.status != "all rows expanded" {
		t.Fatalf("status = %q, want all rows expanded", m.status)
	}
	view = m.View()
	if got := len(strings.Split(view, "\n")); got != m.height {
		t.Fatalf("expanded view height = %d, want %d\n%s", got, m.height, view)
	}
	if !strings.Contains(view, "beta") || !strings.Contains(view, "gamma") {
		t.Fatalf("expanded row should show wrapped continuation:\n%s", view)
	}

	m = pressRunes(m, ",xar")
	if m.expandAll {
		t.Fatal("second ,xar should collapse all rows")
	}
	if m.status != "all rows collapsed" {
		t.Fatalf("status = %q, want all rows collapsed", m.status)
	}
}

func TestExpandedRowsUseOffscreenColumnsForHeight(t *testing.T) {
	m := model{
		sheet: sheet.Sheet{
			Columns: []string{"A", "B", "C"},
			Rows: [][]string{
				{"a", "b", "one two three"},
				{"next", "row", ""},
			},
		},
		colWidths: map[int]int{0: 4, 1: 4, 2: 4},
		expandAll: true,
		width:     rowNumberWidth + 8,
		height:    10,
		status:    "ready",
	}

	lines := strings.Split(m.View(), "\n")
	if !strings.HasPrefix(lines[5], "2   ") {
		t.Fatalf("row 2 should render after off-screen column C height is reserved:\n%s", m.View())
	}
}

func TestGridColorRoles(t *testing.T) {
	tests := []struct {
		name string
		got  lipgloss.TerminalColor
		want lipgloss.TerminalColor
	}{
		{"row number foreground", rowNumberStyle.GetForeground(), lipgloss.Color("240")},
		{"column foreground", columnStyle.GetForeground(), lipgloss.Color("252")},
		{"cell foreground", cellStyle.GetForeground(), lipgloss.Color("245")},
		{"selected foreground", selectedStyle.GetForeground(), lipgloss.Color("15")},
		{"selected background", selectedStyle.GetBackground(), lipgloss.Color("238")},
	}
	for _, tt := range tests {
		if tt.got != tt.want {
			t.Fatalf("%s = %v, want %v", tt.name, tt.got, tt.want)
		}
	}
	if columnStyle.GetBackground() == selectedStyle.GetBackground() {
		t.Fatalf("column headers should not have selected background")
	}
}

func rows(count int) [][]string {
	out := make([][]string, count)
	for i := range out {
		out[i] = []string{""}
	}
	return out
}

func pressRunes(m model, keys string) model {
	for _, key := range keys {
		updated, _ := m.updateKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{key}})
		m = updated.(model)
	}
	return m
}

func pressEnter(m model) model {
	updated, _ := m.updateKey(tea.KeyMsg{Type: tea.KeyEnter})
	return updated.(model)
}

func clearNotification(m model) model {
	updated, _ := m.Update(clearStatusMsg(m.statusID))
	return updated.(model)
}

func blinkCursor(m model) model {
	updated, _ := m.Update(blinkCursorMsg(m.cursorID))
	return updated.(model)
}

func stripANSI(value string) string {
	return ansiPattern.ReplaceAllString(value, "")
}

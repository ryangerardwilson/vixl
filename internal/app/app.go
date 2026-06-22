package app

import (
	"fmt"
	"os"
	"strings"
	"time"
	"unicode/utf8"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/ryangerardwilson/vixl/internal/sheet"
)

type Config struct {
	Path string
}

type model struct {
	sheet sheet.Sheet
	row   int
	col   int

	inputMode string
	input     string
	leader    string
	status    string
	statusID  int
	cursorOn  bool
	cursorID  int
	showHelp  bool
	width     int
	height    int
	colWidths map[int]int
	expandAll bool

	replVisible  bool
	replStarting bool
	replBusy     bool
	replMore     bool
	repl         *replSession
	replLines    []string
	replInput    string
}

type clearStatusMsg int
type blinkCursorMsg int

var (
	titleStyle      = lipgloss.NewStyle().Bold(true)
	rowNumberStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))
	columnStyle     = lipgloss.NewStyle().Foreground(lipgloss.Color("252"))
	cellStyle       = lipgloss.NewStyle().Foreground(lipgloss.Color("245"))
	selectedStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("15")).Background(lipgloss.Color("238"))
	cursorStyle     = lipgloss.NewStyle().Foreground(lipgloss.Color("15")).Background(lipgloss.Color("252"))
	sheetMenuStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("245"))
	sheetChipStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("15")).Background(lipgloss.Color("238"))
	modalTitleStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("252")).Bold(true)
	statusStyle     = lipgloss.NewStyle().Foreground(lipgloss.Color("80"))
	errorStyle      = lipgloss.NewStyle().Foreground(lipgloss.Color("203"))
)

const (
	rowNumberWidth     = 4
	defaultColumnWidth = 14
	minColumnWidth     = 4
	maxAutoColumnWidth = 24
	autoColumnPadding  = 2
	notificationTTL    = 2 * time.Second
	cursorBlinkPeriod  = 500 * time.Millisecond
)

func Run(cfg Config) int {
	s, err := sheet.LoadOrCreate(cfg.Path)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	m := model{sheet: s, status: "ready", width: 100, height: 24, colWidths: columnWidthMap(s.ColumnWidths)}
	program := tea.NewProgram(m, tea.WithAltScreen())
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
	case tea.KeyMsg:
		return m.updateKey(msg)
	case clearStatusMsg:
		if int(msg) == m.statusID {
			m.status = ""
		}
	case blinkCursorMsg:
		if int(msg) == m.cursorID && m.inputMode != "" {
			m.cursorOn = !m.cursorOn
			return m, m.blinkCursor()
		}
	case replStartedMsg:
		return m, m.handleREPLStarted(msg)
	case replResultMsg:
		m.handleREPLResult(msg)
	}
	return m, nil
}

func (m model) updateKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.inputMode != "" {
		return m.updateInput(msg)
	}
	key := msg.String()
	if key == "ctrl+c" || key == "ctrl+q" || key == "q" {
		m.stopREPL()
		return m, tea.Quit
	}
	if key == "?" {
		m.showHelp = !m.showHelp
		return m, nil
	}
	if m.showHelp {
		return m, nil
	}
	if m.leader != "" {
		m.leader += key
		return m.handleLeader()
	}
	switch key {
	case "h", "left":
		m.col = max(0, m.col-1)
	case "l", "right":
		m.col = min(len(m.sheet.Columns)-1, m.col+1)
	case "H":
		m.switchSheet(-1)
	case "L":
		m.switchSheet(1)
	case "k", "up":
		m.row = max(0, m.row-1)
	case "j", "down":
		m.row = min(len(m.sheet.Rows)-1, m.row+1)
	case "ctrl+s":
		_, cmd := m.save()
		return m, cmd
	case "ctrl+t":
		saved, cmd := m.save()
		if saved {
			m.stopREPL()
			return m, tea.Quit
		}
		return m, cmd
	case ">":
		m.resizeFocusedColumn(1)
	case "<":
		m.resizeFocusedColumn(-1)
	case "i", "enter":
		return m, m.beginInput("cell", m.sheet.Rows[m.row][m.col], "edit cell")
	case "x":
		m.sheet.Set(m.row, m.col, "")
		return m, m.notify("cleared")
	case ":":
		return m, m.beginInput("command", "", "command")
	case ",":
		m.leader = ","
		m.setStatus("leader")
	}
	return m, nil
}

func (m model) updateInput(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.inputMode == "repl" {
		return m.updateREPLInput(msg)
	}
	switch msg.String() {
	case "esc", "ctrl+c":
		m.endInput()
		return m, m.notify("cancelled")
	case "enter":
		var cmd tea.Cmd
		input := m.input
		switch m.inputMode {
		case "cell":
			m.sheet.Set(m.row, m.col, input)
			cmd = m.notify("set")
		case "command":
			cmd = m.runCommand(input)
		case "rename_column":
			m.sheet.RenameColumn(m.col, input)
			cmd = m.notify("renamed")
		case "rename_sheet":
			if strings.TrimSpace(input) == "" {
				cmd = m.notify("sheet name required")
			} else {
				m.sheet.SetColumnWidths(m.columnWidthSlice())
				if m.sheet.RenameSheet(input) {
					cmd = m.notify("renamed sheet")
				} else {
					cmd = m.notify("current format is single-sheet")
				}
			}
		}
		m.endInput()
		return m, cmd
	case "backspace", "ctrl+h":
		m.input = trimLastRune(m.input)
	default:
		if len(msg.Runes) > 0 {
			m.input += string(msg.Runes)
		}
	}
	return m, nil
}

func (m model) handleLeader() (tea.Model, tea.Cmd) {
	switch m.leader {
	case ",ira":
		m.sheet.InsertRow(m.row)
		m.leader = ""
		return m, m.notify("inserted row above")
	case ",irb":
		m.sheet.InsertRow(m.row + 1)
		m.row++
		m.leader = ""
		return m, m.notify("inserted row below")
	case ",dr":
		m.sheet.DeleteRow(m.row)
		m.row = min(m.row, len(m.sheet.Rows)-1)
		m.leader = ""
		return m, m.notify("deleted row")
	case ",ica":
		m.sheet.InsertColumn(m.col, "")
		m.insertColumnWidth(m.col)
		m.leader = ""
		return m, m.notify("inserted column left")
	case ",icb":
		m.sheet.InsertColumn(m.col+1, "")
		m.insertColumnWidth(m.col + 1)
		m.col++
		m.leader = ""
		return m, m.notify("inserted column right")
	case ",dc":
		columnsBefore := len(m.sheet.Columns)
		m.sheet.DeleteColumn(m.col)
		if len(m.sheet.Columns) < columnsBefore {
			m.deleteColumnWidth(m.col)
		}
		m.col = min(m.col, len(m.sheet.Columns)-1)
		m.leader = ""
		return m, m.notify("deleted column")
	case ",rnc":
		m.leader = ""
		return m, m.beginInput("rename_column", m.sheet.Columns[m.col], "rename column")
	case ",rns":
		if !m.sheet.SupportsSheets() {
			m.leader = ""
			return m, m.notify("current format is single-sheet")
		}
		m.leader = ""
		return m, m.beginInput("rename_sheet", m.sheet.SheetName(), "rename sheet")
	case ",repl":
		m.leader = ""
		return m, m.toggleREPL()
	case ",ns":
		m.leader = ""
		return m, m.addSheet()
	case ",xar":
		m.expandAll = !m.expandAll
		m.leader = ""
		if m.expandAll {
			return m, m.notify("all rows expanded")
		}
		return m, m.notify("all rows collapsed")
	default:
		if !strings.HasPrefix(",ira", m.leader) &&
			!strings.HasPrefix(",irb", m.leader) &&
			!strings.HasPrefix(",dr", m.leader) &&
			!strings.HasPrefix(",ica", m.leader) &&
			!strings.HasPrefix(",icb", m.leader) &&
			!strings.HasPrefix(",dc", m.leader) &&
			!strings.HasPrefix(",rnc", m.leader) &&
			!strings.HasPrefix(",rns", m.leader) &&
			!strings.HasPrefix(",repl", m.leader) &&
			!strings.HasPrefix(",ns", m.leader) &&
			!strings.HasPrefix(",xar", m.leader) {
			m.leader = ""
			return m, m.notify("unknown leader")
		}
	}
	return m, nil
}

func (m *model) save() (bool, tea.Cmd) {
	if err := m.sheet.Save("", m.columnWidthSlice()); err != nil {
		return false, m.notify(err.Error())
	}
	return true, m.notify("saved")
}

func (m *model) runCommand(raw string) tea.Cmd {
	fields := strings.Fields(raw)
	if len(fields) == 0 {
		return nil
	}
	switch fields[0] {
	case "write", "w":
		if len(fields) > 1 {
			m.sheet.Path = fields[1]
		}
		_, cmd := m.save()
		return cmd
	case "set":
		if len(fields) >= 4 {
			m.sheet.Set(m.row, m.col, strings.Join(fields[3:], " "))
			return m.notify("set")
		}
		return m.notify("use: set row col value")
	default:
		return m.notify("unknown command")
	}
}

func (m model) View() string {
	if m.showHelp {
		return m.renderHelp()
	}
	var out strings.Builder
	out.WriteString(m.renderMain())
	out.WriteString(m.renderFooter())
	view := out.String()
	if m.inputMode == "rename_sheet" {
		return m.renderModal(view, m.renderRenameSheetModal())
	}
	return view
}

func (m model) renderFooter() string {
	lines := []string{m.renderStatusLine()}
	if menu := m.renderSheetMenu(); menu != "" {
		lines = append(lines, menu)
	}
	return strings.Join(lines, "\n")
}

func (m model) renderStatusLine() string {
	if m.inputMode == "rename_sheet" || m.inputMode == "repl" {
		return ""
	}
	if m.inputMode != "" {
		return m.renderPrompt()
	}
	if strings.HasPrefix(m.status, "Go vixl currently") || strings.Contains(m.status, "no save path") || strings.Contains(m.status, "not supported") || strings.Contains(m.status, "not available") || strings.Contains(m.status, "failed") {
		return errorStyle.Render(m.status)
	}
	if m.status == "" || m.status == "ready" {
		return ""
	}
	return statusStyle.Render(m.status)
}

func (m model) renderSheetMenu() string {
	if !m.sheet.SupportsSheets() {
		return ""
	}
	name := m.sheet.SheetName()
	count := m.sheet.SheetCount()
	active := min(max(m.sheet.ActiveSheet, 0), max(0, count-1))
	suffix := ""
	if count > 1 {
		suffix = fmt.Sprintf(" %d/%d", active+1, count)
	}
	maxNameWidth := max(1, m.width-len(suffix)-2)
	chip := "[" + truncate(name, maxNameWidth) + "]"
	if suffix == "" {
		return sheetChipStyle.Render(truncate(chip, m.width))
	}
	return sheetChipStyle.Render(chip) + sheetMenuStyle.Render(suffix)
}

func (m model) renderRenameSheetModal() string {
	innerWidth := min(max(22, displayWidth(m.input)+2), max(8, m.width-6))
	border := "+" + strings.Repeat("-", innerWidth+2) + "+"
	title := "| " + modalTitleStyle.Render(pad(truncate("rename sheet", innerWidth), innerWidth)) + " |"
	field := "| " + m.renderInputText(innerWidth, selectedStyle) + " |"
	return strings.Join([]string{border, title, field, border}, "\n")
}

func (m model) renderModal(view, modal string) string {
	lines := strings.Split(view, "\n")
	modalLines := strings.Split(modal, "\n")
	top := max(0, (len(lines)-len(modalLines))/2)
	for i, line := range modalLines {
		target := top + i
		if target >= len(lines) {
			break
		}
		left := max(0, (m.width-lipgloss.Width(line))/2)
		lines[target] = strings.Repeat(" ", left) + line
	}
	return strings.Join(lines, "\n")
}

func (m model) renderGrid() string {
	rowsVisible := m.visibleRows()
	startCol, endCol := m.columnWindow()
	start := m.firstVisibleRow(rowsVisible)
	var out strings.Builder
	out.WriteString(strings.Repeat(" ", rowNumberWidth))
	for c := startCol; c < endCol; c++ {
		width := m.columnWidth(c)
		cell := pad(truncate(m.sheet.Columns[c], width), width)
		out.WriteString(columnStyle.Render(cell))
	}
	out.WriteString("\n")
	linesUsed := 0
	for r := start; r < len(m.sheet.Rows) && linesUsed < rowsVisible; r++ {
		height := m.rowHeight(r)
		for line := 0; line < height && linesUsed < rowsVisible; line++ {
			if line == 0 {
				out.WriteString(rowNumberStyle.Render(pad(fmt.Sprintf("%d", r+1), rowNumberWidth)))
			} else {
				out.WriteString(strings.Repeat(" ", rowNumberWidth))
			}
			for c := startCol; c < endCol; c++ {
				width := m.columnWidth(c)
				value := ""
				if c < len(m.sheet.Rows[r]) {
					value = m.sheet.Rows[r][c]
				}
				segments := m.cellLines(value, width)
				cell := ""
				if line < len(segments) {
					cell = segments[line]
				}
				cell = pad(cell, width)
				if r == m.row && c == m.col {
					out.WriteString(selectedStyle.Render(cell))
				} else {
					out.WriteString(cellStyle.Render(cell))
				}
			}
			out.WriteString("\n")
			linesUsed++
		}
	}
	for linesUsed < rowsVisible {
		out.WriteString("\n")
		linesUsed++
	}
	return out.String()
}

func (m model) visibleRows() int {
	return max(1, m.height-1-m.footerRows())
}

func (m model) footerRows() int {
	if m.sheet.SupportsSheets() {
		return 2
	}
	return 1
}

func (m model) firstVisibleRow(rowsVisible int) int {
	if len(m.sheet.Rows) == 0 {
		return 0
	}
	focused := min(max(m.row, 0), len(m.sheet.Rows)-1)
	if !m.expandAll {
		if focused >= rowsVisible {
			return focused - rowsVisible + 1
		}
		return 0
	}
	used := 0
	start := focused
	for r := focused; r >= 0; r-- {
		height := m.rowHeight(r)
		if used+height > rowsVisible && r < focused {
			break
		}
		used += height
		start = r
	}
	return start
}

func (m model) columnWindow() (int, int) {
	if len(m.sheet.Columns) == 0 {
		return 0, 0
	}
	focused := min(max(m.col, 0), len(m.sheet.Columns)-1)
	available := max(1, m.width-rowNumberWidth)
	start := focused
	end := focused + 1
	used := m.columnWidth(focused)

	for start > 0 && used+m.columnWidth(start-1) <= available {
		start--
		used += m.columnWidth(start)
	}
	for end < len(m.sheet.Columns) && used+m.columnWidth(end) <= available {
		used += m.columnWidth(end)
		end++
	}
	return start, end
}

func (m model) columnWidth(index int) int {
	if m.colWidths != nil && m.colWidths[index] != 0 {
		return max(minColumnWidth, m.colWidths[index])
	}
	return m.autoColumnWidth(index)
}

func (m model) autoColumnWidth(index int) int {
	if index < 0 || index >= len(m.sheet.Columns) {
		return defaultColumnWidth
	}
	width := displayWidth(m.sheet.Columns[index])
	for _, row := range m.sheet.Rows {
		if index < len(row) {
			width = max(width, displayWidth(row[index]))
		}
	}
	return min(maxAutoColumnWidth, max(minColumnWidth, width+autoColumnPadding))
}

func (m model) rowHeight(row int) int {
	if !m.expandAll || row < 0 || row >= len(m.sheet.Rows) {
		return 1
	}
	height := 1
	for c := range m.sheet.Columns {
		value := ""
		if c < len(m.sheet.Rows[row]) {
			value = m.sheet.Rows[row][c]
		}
		height = max(height, len(wrapCell(value, m.columnWidth(c))))
	}
	return height
}

func (m model) cellLines(value string, width int) []string {
	if m.expandAll {
		return wrapCell(value, width)
	}
	return []string{truncate(value, width)}
}

func (m model) columnWidthSlice() []int {
	if len(m.colWidths) == 0 {
		return nil
	}
	widths := make([]int, len(m.sheet.Columns))
	for col := range m.colWidths {
		if col >= 0 && col < len(widths) {
			widths[col] = m.columnWidth(col)
		}
	}
	return widths
}

func columnWidthMap(widths []int) map[int]int {
	if len(widths) == 0 {
		return nil
	}
	out := make(map[int]int, len(widths))
	for i, width := range widths {
		if width > 0 {
			out[i] = width
		}
	}
	if len(out) == 0 {
		return nil
	}
	return out
}

func (m *model) resizeFocusedColumn(delta int) {
	if len(m.sheet.Columns) == 0 || m.col < 0 || m.col >= len(m.sheet.Columns) {
		return
	}
	if m.colWidths == nil {
		m.colWidths = make(map[int]int)
	}
	m.colWidths[m.col] = max(minColumnWidth, m.columnWidth(m.col)+delta)
	m.clearStatus()
}

func (m *model) switchSheet(delta int) {
	if m.sheet.SheetCount() <= 1 {
		m.clearStatus()
		return
	}
	m.sheet.SetColumnWidths(m.columnWidthSlice())
	if !m.sheet.SwitchSheet(delta) {
		return
	}
	m.row = min(m.row, len(m.sheet.Rows)-1)
	m.col = min(m.col, len(m.sheet.Columns)-1)
	m.row = max(0, m.row)
	m.col = max(0, m.col)
	m.colWidths = columnWidthMap(m.sheet.ColumnWidths)
	m.clearStatus()
}

func (m *model) addSheet() tea.Cmd {
	m.sheet.SetColumnWidths(m.columnWidthSlice())
	if !m.sheet.AddSheet() {
		return m.notify("current format is single-sheet")
	}
	m.row = 0
	m.col = 0
	m.colWidths = columnWidthMap(m.sheet.ColumnWidths)
	m.expandAll = false
	return m.notify("sheet added")
}

func (m *model) insertColumnWidth(index int) {
	if m.colWidths == nil {
		return
	}
	shifted := make(map[int]int, len(m.colWidths))
	for col, width := range m.colWidths {
		if col >= index {
			shifted[col+1] = width
		} else {
			shifted[col] = width
		}
	}
	m.colWidths = shifted
}

func (m *model) deleteColumnWidth(index int) {
	if m.colWidths == nil {
		return
	}
	shifted := make(map[int]int, len(m.colWidths))
	for col, width := range m.colWidths {
		switch {
		case col < index:
			shifted[col] = width
		case col > index:
			shifted[col-1] = width
		}
	}
	m.colWidths = shifted
}

func (m *model) notify(status string) tea.Cmd {
	m.setStatus(status)
	id := m.statusID
	return tea.Tick(notificationTTL, func(time.Time) tea.Msg {
		return clearStatusMsg(id)
	})
}

func (m *model) beginInput(mode, input, status string) tea.Cmd {
	m.inputMode = mode
	m.input = input
	m.cursorOn = true
	m.cursorID++
	m.setStatus(status)
	return m.blinkCursor()
}

func (m *model) endInput() {
	m.inputMode = ""
	m.input = ""
	m.cursorOn = false
	m.cursorID++
}

func (m model) blinkCursor() tea.Cmd {
	id := m.cursorID
	return tea.Tick(cursorBlinkPeriod, func(time.Time) tea.Msg {
		return blinkCursorMsg(id)
	})
}

func (m *model) setStatus(status string) {
	m.status = status
	m.statusID++
}

func (m *model) clearStatus() {
	m.setStatus("")
}

func (m model) renderHelp() string {
	return strings.Join([]string{
		titleStyle.Render("vixl help"),
		"",
		"hjkl/arrows       move",
		"i/enter           edit focused cell",
		"x                 clear focused cell",
		"H / L             previous/next sheet",
		"ctrl+s            save",
		"ctrl+t            save and quit",
		":w [path]         save, optionally to path",
		",ira / ,irb       insert row above/below",
		",dr               delete row",
		",ica / ,icb       insert column left/right",
		",dc               delete column",
		",rnc              rename current column",
		",rns              rename current sheet",
		",repl             toggle python repl",
		",ns               new sheet",
		",xar              expand/collapse all rows",
		"> / <             widen/narrow current column",
		"?                 toggle help",
		"q                 quit",
	}, "\n")
}

func (m model) prompt() string {
	return m.promptPrefix() + m.input
}

func (m model) renderPrompt() string {
	return statusStyle.Render(m.prompt()) + m.renderCursor(statusStyle)
}

func (m model) renderInputText(width int, style lipgloss.Style) string {
	if width <= 0 {
		return ""
	}
	valueWidth := width - 1
	if valueWidth <= 0 {
		return m.renderCursor(style)
	}
	value := truncate(m.input, valueWidth)
	padding := max(0, valueWidth-lipgloss.Width(value))
	return style.Render(value) + m.renderCursor(style) + style.Render(strings.Repeat(" ", padding))
}

func (m model) renderCursor(base lipgloss.Style) string {
	if m.cursorOn {
		return cursorStyle.Render(" ")
	}
	return base.Render(" ")
}

func (m model) promptPrefix() string {
	switch m.inputMode {
	case "command":
		return ": "
	case "rename_column":
		return "rename column "
	case "rename_sheet":
		return "rename sheet "
	case "repl":
		return m.replPromptText()
	default:
		return "cell "
	}
}

func trimLastRune(value string) string {
	if value == "" {
		return value
	}
	_, size := utf8.DecodeLastRuneInString(value)
	return value[:len(value)-size]
}

func pad(value string, width int) string {
	if len(value) >= width {
		return value[:width]
	}
	return value + strings.Repeat(" ", width-len(value))
}

func truncate(value string, width int) string {
	if width <= 0 || len(value) <= width {
		return value
	}
	return value[:max(0, width-3)] + "..."
}

func displayWidth(value string) int {
	width := 0
	for _, line := range strings.Split(value, "\n") {
		width = max(width, len(line))
	}
	return width
}

func wrapCell(value string, width int) []string {
	if width <= 0 || value == "" {
		return []string{""}
	}
	var lines []string
	for _, paragraph := range strings.Split(value, "\n") {
		wrapped := wrapParagraph(paragraph, width)
		lines = append(lines, wrapped...)
	}
	if len(lines) == 0 {
		return []string{""}
	}
	return lines
}

func wrapParagraph(value string, width int) []string {
	words := strings.Fields(value)
	if len(words) == 0 {
		return []string{""}
	}
	var lines []string
	current := ""
	for _, word := range words {
		for len(word) > width {
			if current != "" {
				lines = append(lines, current)
				current = ""
			}
			lines = append(lines, word[:width])
			word = word[width:]
		}
		if word == "" {
			continue
		}
		if current == "" {
			current = word
			continue
		}
		if len(current)+1+len(word) <= width {
			current += " " + word
			continue
		}
		lines = append(lines, current)
		current = word
	}
	if current != "" {
		lines = append(lines, current)
	}
	if len(lines) == 0 {
		return []string{""}
	}
	return lines
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

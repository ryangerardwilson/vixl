package app

import (
	"fmt"
	"os"
	"strings"
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
	showHelp  bool
	width     int
	height    int
}

var (
	titleStyle    = lipgloss.NewStyle().Bold(true)
	mutedStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("241"))
	selectedStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("229")).Background(lipgloss.Color("238"))
	statusStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("80"))
	errorStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("203"))
)

func Run(cfg Config) int {
	s, err := sheet.LoadOrCreate(cfg.Path)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	m := model{sheet: s, status: "ready", width: 100, height: 24}
	program := tea.NewProgram(m)
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
	}
	return m, nil
}

func (m model) updateKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.inputMode != "" {
		return m.updateInput(msg)
	}
	key := msg.String()
	if key == "ctrl+c" || key == "ctrl+q" || key == "q" {
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
	case "k", "up":
		m.row = max(0, m.row-1)
	case "j", "down":
		m.row = min(len(m.sheet.Rows)-1, m.row+1)
	case "ctrl+s":
		m.save()
	case "ctrl+t":
		if m.save() {
			return m, tea.Quit
		}
	case "i", "enter":
		m.inputMode = "cell"
		m.input = m.sheet.Rows[m.row][m.col]
		m.status = "edit cell"
	case "x":
		m.sheet.Set(m.row, m.col, "")
		m.status = "cleared"
	case ":":
		m.inputMode = "command"
		m.input = ""
		m.status = "command"
	case ",":
		m.leader = ","
		m.status = "leader"
	}
	return m, nil
}

func (m model) updateInput(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "esc", "ctrl+c":
		m.inputMode = ""
		m.input = ""
		m.status = "cancelled"
	case "enter":
		switch m.inputMode {
		case "cell":
			m.sheet.Set(m.row, m.col, m.input)
			m.status = "set"
		case "command":
			m.runCommand(m.input)
		case "rename":
			m.sheet.RenameColumn(m.col, m.input)
			m.status = "renamed"
		}
		m.inputMode = ""
		m.input = ""
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
		m.status = "inserted row above"
		m.leader = ""
	case ",irb":
		m.sheet.InsertRow(m.row + 1)
		m.row++
		m.status = "inserted row below"
		m.leader = ""
	case ",dr":
		m.sheet.DeleteRow(m.row)
		m.row = min(m.row, len(m.sheet.Rows)-1)
		m.status = "deleted row"
		m.leader = ""
	case ",ica":
		m.sheet.InsertColumn(m.col, "")
		m.status = "inserted column left"
		m.leader = ""
	case ",icb":
		m.sheet.InsertColumn(m.col+1, "")
		m.col++
		m.status = "inserted column right"
		m.leader = ""
	case ",dc":
		m.sheet.DeleteColumn(m.col)
		m.col = min(m.col, len(m.sheet.Columns)-1)
		m.status = "deleted column"
		m.leader = ""
	case ",rnc":
		m.inputMode = "rename"
		m.input = m.sheet.Columns[m.col]
		m.status = "rename column"
		m.leader = ""
	default:
		if !strings.HasPrefix(",ira", m.leader) &&
			!strings.HasPrefix(",irb", m.leader) &&
			!strings.HasPrefix(",dr", m.leader) &&
			!strings.HasPrefix(",ica", m.leader) &&
			!strings.HasPrefix(",icb", m.leader) &&
			!strings.HasPrefix(",dc", m.leader) &&
			!strings.HasPrefix(",rnc", m.leader) {
			m.status = "unknown leader"
			m.leader = ""
		}
	}
	return m, nil
}

func (m *model) save() bool {
	if err := m.sheet.Save(""); err != nil {
		m.status = err.Error()
		return false
	}
	m.status = "saved"
	return true
}

func (m *model) runCommand(raw string) {
	fields := strings.Fields(raw)
	if len(fields) == 0 {
		return
	}
	switch fields[0] {
	case "write", "w":
		if len(fields) > 1 {
			m.sheet.Path = fields[1]
		}
		m.save()
	case "set":
		if len(fields) >= 4 {
			m.sheet.Set(m.row, m.col, strings.Join(fields[3:], " "))
			m.status = "set"
		} else {
			m.status = "use: set row col value"
		}
	default:
		m.status = "unknown command"
	}
}

func (m model) View() string {
	if m.showHelp {
		return m.renderHelp()
	}
	var out strings.Builder
	title := "vixl"
	if m.sheet.Path != "" {
		title += " " + m.sheet.Path
	}
	out.WriteString(titleStyle.Render(truncate(title, m.width)))
	out.WriteString("\n\n")
	out.WriteString(m.renderGrid())
	out.WriteString("\n")
	if m.inputMode != "" {
		out.WriteString(statusStyle.Render(m.prompt()))
	} else if strings.HasPrefix(m.status, "Go vixl currently") || strings.Contains(m.status, "no save path") {
		out.WriteString(errorStyle.Render(m.status))
	} else {
		out.WriteString(statusStyle.Render(m.status))
	}
	out.WriteString("\n")
	out.WriteString(mutedStyle.Render("hjkl move  i edit  x clear  : command  ctrl+s save  ctrl+t save+quit  ,ira/,irb row  ,ica/,icb col  ,rnc rename  ? help"))
	return out.String()
}

func (m model) renderGrid() string {
	rowsVisible := max(4, m.height-7)
	start := 0
	if m.row >= rowsVisible {
		start = m.row - rowsVisible + 1
	}
	end := min(len(m.sheet.Rows), start+rowsVisible)
	width := 14
	var out strings.Builder
	out.WriteString("    ")
	for c, name := range m.sheet.Columns {
		cell := pad(truncate(name, width), width)
		if c == m.col {
			out.WriteString(selectedStyle.Render(cell))
		} else {
			out.WriteString(cell)
		}
	}
	out.WriteString("\n")
	for r := start; r < end; r++ {
		out.WriteString(pad(fmt.Sprintf("%d", r+1), 4))
		for c := range m.sheet.Columns {
			value := ""
			if c < len(m.sheet.Rows[r]) {
				value = m.sheet.Rows[r][c]
			}
			cell := pad(truncate(value, width), width)
			if r == m.row && c == m.col {
				out.WriteString(selectedStyle.Render(cell))
			} else {
				out.WriteString(cell)
			}
		}
		out.WriteString("\n")
	}
	return out.String()
}

func (m model) renderHelp() string {
	return strings.Join([]string{
		titleStyle.Render("vixl help"),
		"",
		"hjkl/arrows       move",
		"i/enter           edit focused cell",
		"x                 clear focused cell",
		"ctrl+s            save",
		"ctrl+t            save and quit",
		":w [path]         save, optionally to path",
		",ira / ,irb       insert row above/below",
		",dr               delete row",
		",ica / ,icb       insert column left/right",
		",dc               delete column",
		",rnc              rename current column",
		"?                 toggle help",
		"q                 quit",
	}, "\n")
}

func (m model) prompt() string {
	switch m.inputMode {
	case "command":
		return ": " + m.input
	case "rename":
		return "rename " + m.input
	default:
		return "cell " + m.input
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

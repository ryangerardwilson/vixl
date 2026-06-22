package app

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	_ "embed"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

//go:embed repl_bridge.py
var replBridgeSource string

type replStartedMsg struct {
	session    *replSession
	banner     string
	initOutput string
	err        error
}

type replResultMsg struct {
	output string
	more   bool
	err    error
}

type replSession struct {
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	scanner *bufio.Scanner
	closed  bool
}

type replReadyResponse struct {
	Ready  bool   `json:"ready"`
	Banner string `json:"banner"`
	Error  string `json:"error"`
}

type replEvalResponse struct {
	Output string `json:"output"`
	More   bool   `json:"more"`
}

type replDataFrame struct {
	Columns []string   `json:"columns"`
	Rows    [][]string `json:"rows"`
}

func startREPLSession(frame replDataFrame) (*replSession, string, string, error) {
	python, err := replPythonPath()
	if err != nil {
		return nil, "", "", err
	}
	cmd := exec.Command(python, "-u", "-c", replBridgeSource)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, "", "", err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, "", "", err
	}
	var stderr strings.Builder
	cmd.Stderr = &stderr
	if err := cmd.Start(); err != nil {
		return nil, "", "", err
	}
	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 1024), 1024*1024)
	if !scanner.Scan() {
		_ = cmd.Wait()
		if message := strings.TrimSpace(stderr.String()); message != "" {
			return nil, "", "", errors.New(message)
		}
		if err := scanner.Err(); err != nil {
			return nil, "", "", err
		}
		return nil, "", "", errors.New("python repl failed to start")
	}
	var ready replReadyResponse
	if err := json.Unmarshal(scanner.Bytes(), &ready); err != nil {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
		return nil, "", "", fmt.Errorf("invalid python repl startup response: %w", err)
	}
	if !ready.Ready {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
		if ready.Error == "" {
			ready.Error = "python repl failed to preload numpy and pandas"
		}
		return nil, "", "", errors.New(ready.Error)
	}
	session := &replSession{cmd: cmd, stdin: stdin, scanner: scanner}
	initOutput, _, err := session.send(map[string]replDataFrame{"init_df": frame})
	if err != nil {
		session.Close()
		return nil, "", "", err
	}
	return session, ready.Banner, strings.TrimSpace(initOutput), nil
}

func (r *replSession) Eval(source string) (string, bool, error) {
	if r == nil || r.closed {
		return "", false, errors.New("python repl is not running")
	}
	return r.send(map[string]string{"code": source})
}

func (r *replSession) send(payload any) (string, bool, error) {
	if r == nil || r.closed {
		return "", false, errors.New("python repl is not running")
	}
	request, err := json.Marshal(payload)
	if err != nil {
		return "", false, err
	}
	if _, err := r.stdin.Write(append(request, '\n')); err != nil {
		return "", false, err
	}
	if !r.scanner.Scan() {
		if err := r.scanner.Err(); err != nil {
			return "", false, err
		}
		return "", false, errors.New("python repl stopped")
	}
	var response replEvalResponse
	if err := json.Unmarshal(r.scanner.Bytes(), &response); err != nil {
		return "", false, err
	}
	return response.Output, response.More, nil
}

func (r *replSession) Close() {
	if r == nil || r.closed {
		return
	}
	r.closed = true
	_ = r.stdin.Close()
	if r.cmd != nil && r.cmd.Process != nil {
		_ = r.cmd.Process.Kill()
	}
	if r.cmd != nil {
		_ = r.cmd.Wait()
	}
}

func replPythonPath() (string, error) {
	if path := strings.TrimSpace(os.Getenv("VIXL_REPL_PYTHON")); path != "" {
		return path, nil
	}
	if path := strings.TrimSpace(os.Getenv("VIXL_HDF_PYTHON")); path != "" {
		return path, nil
	}
	if home, err := os.UserHomeDir(); err == nil {
		managed := filepath.Join(home, ".vixl", "hdf", "bin", "python")
		if replIsExecutable(managed) {
			return managed, nil
		}
	}
	for _, candidate := range []string{"python3", "python"} {
		path, err := exec.LookPath(candidate)
		if err == nil {
			return path, nil
		}
	}
	return "", errors.New("Python REPL requires python with numpy and pandas; run: bash install.sh from <vixl-source-path>")
}

func replIsExecutable(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir() && info.Mode()&0o111 != 0
}

func (m model) renderMain() string {
	if !m.replVisible {
		return m.renderGrid()
	}
	gridWidth, sidebarWidth := m.replLayoutWidths()
	gridModel := m
	gridModel.width = gridWidth
	grid := strings.TrimSuffix(gridModel.renderGrid(), "\n")
	gridLines := strings.Split(grid, "\n")
	sidebarLines := strings.Split(m.renderREPLSidebar(len(gridLines), sidebarWidth), "\n")
	lines := make([]string, len(gridLines))
	for i := range gridLines {
		sidebar := ""
		if i < len(sidebarLines) {
			sidebar = sidebarLines[i]
		}
		lines[i] = padVisual(gridLines[i], gridWidth) + " " + sidebar
	}
	return strings.Join(lines, "\n") + "\n"
}

func (m model) replLayoutWidths() (int, int) {
	sidebar := min(48, max(32, m.width/3))
	if m.width < 72 {
		sidebar = max(20, m.width/2)
	}
	minGrid := rowNumberWidth + minColumnWidth
	if sidebar > m.width-minGrid-1 {
		sidebar = max(12, m.width-minGrid-1)
	}
	if sidebar < 12 {
		sidebar = max(1, m.width/2)
	}
	grid := max(1, m.width-sidebar-1)
	return grid, sidebar
}

func (m model) renderREPLSidebar(height, width int) string {
	if height <= 0 {
		return ""
	}
	contentWidth := max(1, width-1)
	lines := make([]string, 0, height)
	body := m.visibleREPLLines(max(0, height-1), contentWidth)
	for _, line := range body {
		lines = append(lines, replSidebarLine(line, width))
	}
	lines = append(lines, "|"+m.renderREPLPrompt(contentWidth))
	for len(lines) < height {
		lines = append(lines, replSidebarLine("", width))
	}
	return strings.Join(lines[:height], "\n")
}

func (m model) visibleREPLLines(height, width int) []string {
	if height <= 0 {
		return nil
	}
	lines := m.replLines
	if len(lines) == 0 {
		return nil
	}
	var out []string
	for _, line := range lines {
		wrapped := wrapPlain(line, width)
		out = append(out, wrapped...)
	}
	if len(out) > height {
		out = out[len(out)-height:]
	}
	return out
}

func (m model) renderREPLPrompt(width int) string {
	prefix := ">>> "
	if m.replMore {
		prefix = "... "
	}
	if width <= 1 {
		return m.renderCursor(cellStyle)
	}
	if len(prefix)+1 >= width {
		return cellStyle.Render(truncate(prefix, width-1)) + m.renderCursor(cellStyle)
	}
	inputWidth := width - len(prefix) - 1
	input := truncate(m.input, inputWidth)
	padding := max(0, inputWidth-lipgloss.Width(input))
	return cellStyle.Render(prefix) + cellStyle.Render(input) + m.renderCursor(cellStyle) + cellStyle.Render(strings.Repeat(" ", padding))
}

func replSidebarLine(content string, width int) string {
	if width <= 0 {
		return ""
	}
	return "|" + pad(truncate(content, width-1), width-1)
}

func padVisual(value string, width int) string {
	used := lipgloss.Width(value)
	if used >= width {
		return value
	}
	return value + strings.Repeat(" ", width-used)
}

func wrapPlain(value string, width int) []string {
	if width <= 0 {
		return []string{""}
	}
	if value == "" {
		return []string{""}
	}
	var lines []string
	for _, line := range strings.Split(value, "\n") {
		if line == "" {
			lines = append(lines, "")
			continue
		}
		for len(line) > width {
			lines = append(lines, line[:width])
			line = line[width:]
		}
		lines = append(lines, line)
	}
	return lines
}

func (m *model) toggleREPL() tea.Cmd {
	if m.replVisible {
		m.hideREPL()
		return nil
	}
	m.replVisible = true
	blink := m.beginInput("repl", m.replInput, "repl")
	if m.repl != nil || m.replStarting {
		return blink
	}
	m.replStarting = true
	return tea.Batch(blink, m.startREPL())
}

func (m *model) startREPL() tea.Cmd {
	frame := m.replDataFrame()
	return func() tea.Msg {
		session, banner, initOutput, err := startREPLSession(frame)
		return replStartedMsg{session: session, banner: banner, initOutput: initOutput, err: err}
	}
}

func (m *model) hideREPL() {
	m.replVisible = false
	if m.inputMode == "repl" {
		m.replInput = m.input
		m.endInput()
	}
}

func (m *model) stopREPL() {
	if m.repl != nil {
		m.repl.Close()
	}
	m.repl = nil
	m.replVisible = false
	m.replStarting = false
	m.replBusy = false
	m.replMore = false
	m.replLines = nil
	m.replInput = ""
	if m.inputMode == "repl" {
		m.endInput()
	}
}

func (m *model) handleREPLStarted(msg replStartedMsg) tea.Cmd {
	m.replStarting = false
	if msg.err != nil {
		m.replLines = []string{msg.err.Error()}
		if !m.replVisible {
			return nil
		}
		return m.notify("repl unavailable")
	}
	m.repl = msg.session
	return nil
}

func (m *model) handleREPLResult(msg replResultMsg) {
	m.replBusy = false
	if msg.err != nil {
		m.appendREPLText(msg.err.Error())
		m.replMore = false
		return
	}
	m.replMore = msg.more
	m.appendREPLText(strings.TrimRight(msg.output, "\n"))
}

func (m model) updateREPLInput(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "esc", "ctrl+c":
		m.hideREPL()
		return m, nil
	case "ctrl+l":
		m.replLines = nil
		return m, nil
	case "enter":
		source := m.input
		if strings.TrimSpace(source) == "" && !m.replMore {
			m.input = ""
			m.replInput = ""
			return m, nil
		}
		if m.replStarting {
			return m, m.notify("repl starting")
		}
		if m.replBusy {
			return m, m.notify("repl busy")
		}
		m.input = ""
		m.replInput = ""
		m.appendREPLText(m.replPromptText() + source)
		if m.repl == nil {
			m.appendREPLText("python repl is not running")
			return m, nil
		}
		m.replBusy = true
		session := m.repl
		return m, func() tea.Msg {
			output, more, err := session.Eval(source)
			return replResultMsg{output: output, more: more, err: err}
		}
	case "backspace", "ctrl+h":
		m.input = trimLastRune(m.input)
		m.replInput = m.input
	default:
		if len(msg.Runes) > 0 {
			m.input += string(msg.Runes)
			m.replInput = m.input
		}
	}
	return m, nil
}

func (m model) replPromptText() string {
	if m.replMore {
		return "... "
	}
	return ">>> "
}

func (m *model) appendREPLText(text string) {
	if text == "" {
		return
	}
	for _, line := range strings.Split(text, "\n") {
		m.replLines = append(m.replLines, line)
	}
	const maxREPLLines = 300
	if len(m.replLines) > maxREPLLines {
		m.replLines = m.replLines[len(m.replLines)-maxREPLLines:]
	}
}

func (m model) replDataFrame() replDataFrame {
	frame := replDataFrame{
		Columns: append([]string(nil), m.sheet.Columns...),
		Rows:    make([][]string, len(m.sheet.Rows)),
	}
	for r, row := range m.sheet.Rows {
		frame.Rows[r] = make([]string, len(frame.Columns))
		copy(frame.Rows[r], row)
	}
	return frame
}

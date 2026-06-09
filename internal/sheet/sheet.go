package sheet

import (
	"encoding/csv"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Sheet struct {
	Columns []string
	Rows    [][]string
	Path    string
}

func Default() Sheet {
	return Sheet{
		Columns: []string{"col_a", "col_b", "col_c"},
		Rows: [][]string{
			{"", "", ""},
			{"", "", ""},
			{"", "", ""},
		},
	}
}

func LoadOrCreate(path string) (Sheet, error) {
	if path == "" {
		return Default(), nil
	}
	ext := strings.ToLower(filepath.Ext(path))
	if ext != "" && ext != ".csv" && ext != ".tsv" {
		return Sheet{}, errors.New("Go vixl currently supports .csv and .tsv files")
	}
	if _, err := os.Stat(path); os.IsNotExist(err) {
		s := Default()
		s.Path = path
		return s, nil
	}
	file, err := os.Open(path)
	if err != nil {
		return Sheet{}, err
	}
	defer file.Close()
	reader := csv.NewReader(file)
	if ext == ".tsv" {
		reader.Comma = '\t'
	}
	records, err := reader.ReadAll()
	if err != nil {
		return Sheet{}, err
	}
	if len(records) == 0 {
		s := Default()
		s.Path = path
		return s, nil
	}
	s := Sheet{Columns: normalizeColumns(records[0]), Path: path}
	for _, record := range records[1:] {
		row := make([]string, len(s.Columns))
		copy(row, record)
		s.Rows = append(s.Rows, row)
	}
	s.ensureShape()
	return s, nil
}

func (s *Sheet) Save(path string) error {
	if path == "" {
		path = s.Path
	}
	if path == "" {
		return errors.New("no save path")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	writer := csv.NewWriter(file)
	if strings.ToLower(filepath.Ext(path)) == ".tsv" {
		writer.Comma = '\t'
	}
	if err := writer.Write(s.Columns); err != nil {
		return err
	}
	for _, row := range s.Rows {
		out := make([]string, len(s.Columns))
		copy(out, row)
		if err := writer.Write(out); err != nil {
			return err
		}
	}
	writer.Flush()
	if err := writer.Error(); err != nil {
		return err
	}
	s.Path = path
	return nil
}

func (s *Sheet) Set(row, col int, value string) {
	s.ensureShape()
	if row >= 0 && row < len(s.Rows) && col >= 0 && col < len(s.Columns) {
		s.Rows[row][col] = value
	}
}

func (s *Sheet) InsertRow(index int) {
	s.ensureShape()
	index = clamp(index, 0, len(s.Rows))
	row := make([]string, len(s.Columns))
	s.Rows = append(s.Rows[:index], append([][]string{row}, s.Rows[index:]...)...)
}

func (s *Sheet) DeleteRow(index int) {
	if len(s.Rows) <= 1 || index < 0 || index >= len(s.Rows) {
		return
	}
	s.Rows = append(s.Rows[:index], s.Rows[index+1:]...)
}

func (s *Sheet) InsertColumn(index int, name string) {
	s.ensureShape()
	index = clamp(index, 0, len(s.Columns))
	if strings.TrimSpace(name) == "" {
		name = "col_" + strconv.Itoa(len(s.Columns)+1)
	}
	s.Columns = append(s.Columns[:index], append([]string{name}, s.Columns[index:]...)...)
	for i := range s.Rows {
		s.Rows[i] = append(s.Rows[i][:index], append([]string{""}, s.Rows[i][index:]...)...)
	}
}

func (s *Sheet) DeleteColumn(index int) {
	if len(s.Columns) <= 1 || index < 0 || index >= len(s.Columns) {
		return
	}
	s.Columns = append(s.Columns[:index], s.Columns[index+1:]...)
	for i := range s.Rows {
		s.Rows[i] = append(s.Rows[i][:index], s.Rows[i][index+1:]...)
	}
}

func (s *Sheet) RenameColumn(index int, name string) {
	if index >= 0 && index < len(s.Columns) && strings.TrimSpace(name) != "" {
		s.Columns[index] = strings.TrimSpace(name)
	}
}

func (s *Sheet) ensureShape() {
	if len(s.Columns) == 0 {
		s.Columns = []string{"col_a"}
	}
	if len(s.Rows) == 0 {
		s.Rows = [][]string{make([]string, len(s.Columns))}
	}
	for i := range s.Rows {
		if len(s.Rows[i]) < len(s.Columns) {
			s.Rows[i] = append(s.Rows[i], make([]string, len(s.Columns)-len(s.Rows[i]))...)
		}
		if len(s.Rows[i]) > len(s.Columns) {
			s.Rows[i] = s.Rows[i][:len(s.Columns)]
		}
	}
}

func normalizeColumns(cols []string) []string {
	if len(cols) == 0 {
		return []string{"col_a"}
	}
	out := make([]string, len(cols))
	for i, col := range cols {
		col = strings.TrimSpace(col)
		if col == "" {
			col = "col_" + strconv.Itoa(i+1)
		}
		out[i] = col
	}
	return out
}

func clamp(value, low, high int) int {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}

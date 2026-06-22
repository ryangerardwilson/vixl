package sheet

import (
	"bytes"
	_ "embed"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/extrame/xls"
	parquet "github.com/parquet-go/parquet-go"
	"github.com/xuri/excelize/v2"
)

const vixlMetadataKey = "vixl.ui.v1"
const vixlWorkbookMetadataKey = "vixl.workbook.v1"

//go:embed hdf_bridge.py
var hdfBridgeSource string

type Sheet struct {
	Columns      []string
	Rows         [][]string
	Path         string
	ColumnWidths []int
	Worksheets   []Worksheet
	ActiveSheet  int
}

type Worksheet struct {
	Name         string
	Columns      []string
	Rows         [][]string
	ColumnWidths []int
}

type fileMetadata struct {
	Columns      []string       `json:"columns,omitempty"`
	ColumnWidths map[string]int `json:"column_widths,omitempty"`
}

type workbookMetadata struct {
	ActiveSheet int                 `json:"active_sheet"`
	Sheets      []workbookSheetMeta `json:"sheets"`
}

type workbookSheetMeta struct {
	Name         string   `json:"name"`
	Columns      []string `json:"columns"`
	ColumnWidths []int    `json:"column_widths,omitempty"`
}

type workbookCellRecord struct {
	SheetIndex  int64  `parquet:"sheet_index"`
	RowIndex    int64  `parquet:"row_index"`
	ColumnIndex int64  `parquet:"column_index"`
	Value       string `parquet:"value"`
}

type hdfPayload struct {
	ActiveSheet int        `json:"active_sheet"`
	Sheets      []hdfSheet `json:"sheets"`
}

type hdfSheet struct {
	Name         string     `json:"name"`
	Columns      []string   `json:"columns"`
	Rows         [][]string `json:"rows"`
	ColumnWidths []int      `json:"column_widths,omitempty"`
}

func Default() Sheet {
	s := Sheet{
		Columns: []string{"col_a", "col_b", "col_c"},
		Rows: [][]string{
			{"", "", ""},
			{"", "", ""},
			{"", "", ""},
		},
	}
	s.ensureShape()
	return s
}

func LoadOrCreate(path string) (Sheet, error) {
	if path == "" {
		return Default(), nil
	}
	ext := strings.ToLower(filepath.Ext(path))
	if !supportedLoadExt(ext) {
		return Sheet{}, errors.New("Go vixl currently supports .csv, .tsv, .parquet, .xlsx, .h5/.hdf/.hdf5, and read-only .xls files")
	}
	if _, err := os.Stat(path); os.IsNotExist(err) {
		if ext == ".xls" {
			return Sheet{}, errors.New("creating .xls files is not supported; use .xlsx or .parquet")
		}
		s := Default()
		s.Path = path
		return s, nil
	}
	switch ext {
	case ".parquet":
		return loadParquet(path)
	case ".xlsx":
		return loadXLSX(path)
	case ".xls":
		return loadXLS(path)
	case ".h5", ".hdf", ".hdf5":
		return loadHDF(path)
	default:
		return loadDelimited(path, ext)
	}
}

func (s *Sheet) Save(path string, widths ...[]int) error {
	if path == "" {
		path = s.Path
	}
	if path == "" {
		return errors.New("no save path")
	}
	ext := strings.ToLower(filepath.Ext(path))
	if !supportedSaveExt(ext) {
		if ext == ".xls" {
			return errors.New("saving .xls is not supported; use :w <path>.xlsx, :w <path>.parquet, or :w <path>.h5")
		}
		return errors.New("Go vixl currently saves .csv, .tsv, .parquet, .xlsx, and .h5/.hdf/.hdf5 files")
	}
	if singleSheetExt(ext) && s.SheetCount() > 1 {
		return errors.New("saving multiple sheets to a single-table format is not supported; use .xlsx, .parquet, or .h5")
	}
	columnWidths := s.ColumnWidths
	if len(widths) > 0 {
		columnWidths = widths[0]
	}
	s.SetColumnWidths(columnWidths)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	var err error
	switch ext {
	case ".parquet":
		err = s.saveParquet(path, columnWidths)
	case ".xlsx":
		err = s.saveXLSX(path, columnWidths)
	case ".h5", ".hdf", ".hdf5":
		err = s.saveHDF(path, columnWidths)
	default:
		err = s.saveDelimited(path, ext)
	}
	if err != nil {
		return err
	}
	s.Path = path
	s.SetColumnWidths(columnWidths)
	return nil
}

func (s *Sheet) Set(row, col int, value string) {
	s.ensureShape()
	if row >= 0 && row < len(s.Rows) && col >= 0 && col < len(s.Columns) {
		s.Rows[row][col] = value
	}
	s.syncActiveToWorkbook()
}

func (s *Sheet) InsertRow(index int) {
	s.ensureShape()
	index = clamp(index, 0, len(s.Rows))
	row := make([]string, len(s.Columns))
	s.Rows = append(s.Rows[:index], append([][]string{row}, s.Rows[index:]...)...)
	s.syncActiveToWorkbook()
}

func (s *Sheet) DeleteRow(index int) {
	s.ensureShape()
	if len(s.Rows) <= 1 || index < 0 || index >= len(s.Rows) {
		return
	}
	s.Rows = append(s.Rows[:index], s.Rows[index+1:]...)
	s.syncActiveToWorkbook()
}

func (s *Sheet) InsertColumn(index int, name string) {
	s.ensureShape()
	index = clamp(index, 0, len(s.Columns))
	if strings.TrimSpace(name) == "" {
		name = "col_" + strconv.Itoa(len(s.Columns)+1)
	}
	s.Columns = append(s.Columns[:index], append([]string{name}, s.Columns[index:]...)...)
	if len(s.ColumnWidths) > 0 {
		s.ColumnWidths = append(s.ColumnWidths[:index], append([]int{0}, s.ColumnWidths[index:]...)...)
	}
	for i := range s.Rows {
		s.Rows[i] = append(s.Rows[i][:index], append([]string{""}, s.Rows[i][index:]...)...)
	}
	s.syncActiveToWorkbook()
}

func (s *Sheet) DeleteColumn(index int) {
	s.ensureShape()
	if len(s.Columns) <= 1 || index < 0 || index >= len(s.Columns) {
		return
	}
	s.Columns = append(s.Columns[:index], s.Columns[index+1:]...)
	if index < len(s.ColumnWidths) {
		s.ColumnWidths = append(s.ColumnWidths[:index], s.ColumnWidths[index+1:]...)
	}
	for i := range s.Rows {
		s.Rows[i] = append(s.Rows[i][:index], s.Rows[i][index+1:]...)
	}
	s.syncActiveToWorkbook()
}

func (s *Sheet) RenameColumn(index int, name string) {
	s.ensureShape()
	if index >= 0 && index < len(s.Columns) && strings.TrimSpace(name) != "" {
		s.Columns[index] = strings.TrimSpace(name)
	}
	s.syncActiveToWorkbook()
}

func (s *Sheet) SetColumnWidths(widths []int) {
	s.ensureShape()
	s.ColumnWidths = normalizeWidths(widths, len(s.Columns))
	s.syncActiveToWorkbook()
}

func (s *Sheet) SheetCount() int {
	if len(s.Worksheets) == 0 {
		return 1
	}
	return len(s.Worksheets)
}

func (s *Sheet) SheetName() string {
	if len(s.Worksheets) > 0 {
		index := clamp(s.ActiveSheet, 0, len(s.Worksheets)-1)
		if name := strings.TrimSpace(s.Worksheets[index].Name); name != "" {
			return name
		}
	}
	return "Sheet1"
}

func (s *Sheet) SheetNames() []string {
	if len(s.Worksheets) == 0 {
		return []string{s.SheetName()}
	}
	names := make([]string, len(s.Worksheets))
	for i, ws := range s.Worksheets {
		names[i] = worksheetName(ws.Name, i)
	}
	return names
}

func (s *Sheet) SwitchSheet(delta int) bool {
	s.ensureShape()
	if len(s.Worksheets) <= 1 {
		return false
	}
	s.syncActiveToWorkbook()
	s.ActiveSheet = (s.ActiveSheet + delta) % len(s.Worksheets)
	if s.ActiveSheet < 0 {
		s.ActiveSheet += len(s.Worksheets)
	}
	s.syncActiveFromWorkbook()
	return true
}

func (s *Sheet) SupportsSheets() bool {
	if s.Path == "" {
		return true
	}
	return !singleSheetExt(strings.ToLower(filepath.Ext(s.Path)))
}

func (s *Sheet) AddSheet() bool {
	if !s.SupportsSheets() {
		return false
	}
	s.ensureShape()
	s.syncActiveToWorkbook()
	name := s.nextSheetName()
	ws := defaultWorksheet(name, len(s.Worksheets))
	s.Worksheets = append(s.Worksheets, ws)
	s.ActiveSheet = len(s.Worksheets) - 1
	s.syncActiveFromWorkbook()
	return true
}

func (s *Sheet) RenameSheet(name string) bool {
	name = strings.TrimSpace(name)
	if name == "" || !s.SupportsSheets() {
		return false
	}
	s.ensureShape()
	s.syncActiveToWorkbook()
	s.ActiveSheet = clamp(s.ActiveSheet, 0, len(s.Worksheets)-1)
	s.Worksheets[s.ActiveSheet].Name = name
	s.syncActiveFromWorkbook()
	return true
}

func loadDelimited(path, ext string) (Sheet, error) {
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

func loadXLSX(path string) (Sheet, error) {
	file, err := excelize.OpenFile(path)
	if err != nil {
		return Sheet{}, err
	}
	defer file.Close()
	sheets := file.GetSheetList()
	if len(sheets) == 0 {
		s := Default()
		s.Path = path
		return s, nil
	}
	worksheets := make([]Worksheet, 0, len(sheets))
	for i, name := range sheets {
		ws, err := loadXLSXWorksheet(file, name, i)
		if err != nil {
			return Sheet{}, err
		}
		worksheets = append(worksheets, ws)
	}
	active := clamp(file.GetActiveSheetIndex(), 0, len(worksheets)-1)
	s := Sheet{Path: path, Worksheets: worksheets, ActiveSheet: active}
	s.syncActiveFromWorkbook()
	return s, nil
}

func loadXLSXWorksheet(file *excelize.File, name string, index int) (Worksheet, error) {
	rows, err := file.GetRows(name)
	if err != nil {
		return Worksheet{}, err
	}
	if len(rows) == 0 {
		ws := defaultWorksheet(name, index)
		normalizeWorksheet(&ws)
		return ws, nil
	}
	ws := Worksheet{Name: worksheetName(name, index), Columns: normalizeColumns(rows[0])}
	for _, record := range rows[1:] {
		row := make([]string, len(ws.Columns))
		copy(row, record)
		ws.Rows = append(ws.Rows, row)
	}
	ws.ColumnWidths = loadXLSXColumnWidths(file, name, len(ws.Columns))
	normalizeWorksheet(&ws)
	return ws, nil
}

func loadXLS(path string) (Sheet, error) {
	book, err := xls.Open(path, "utf-8")
	if err != nil {
		return Sheet{}, err
	}
	if book.NumSheets() == 0 {
		s := Default()
		s.Path = path
		return s, nil
	}
	worksheets := make([]Worksheet, 0, book.NumSheets())
	for i := 0; i < book.NumSheets(); i++ {
		worksheet := book.GetSheet(i)
		if worksheet == nil {
			continue
		}
		worksheets = append(worksheets, loadXLSWorksheet(worksheet, i))
	}
	if len(worksheets) == 0 {
		s := Default()
		s.Path = path
		return s, nil
	}
	s := Sheet{Path: path, Worksheets: worksheets}
	s.syncActiveFromWorkbook()
	return s, nil
}

func loadXLSWorksheet(worksheet *xls.WorkSheet, index int) Worksheet {
	header := safeXLSRow(worksheet, 0)
	if header == nil {
		ws := defaultWorksheet(worksheet.Name, index)
		normalizeWorksheet(&ws)
		return ws
	}
	ws := Worksheet{Name: worksheetName(worksheet.Name, index), Columns: normalizeColumns(xlsRowValues(header))}
	for i := 1; i <= int(worksheet.MaxRow); i++ {
		rowData := make([]string, len(ws.Columns))
		if row := safeXLSRow(worksheet, i); row != nil {
			copy(rowData, xlsRowValues(row))
		}
		ws.Rows = append(ws.Rows, rowData)
	}
	normalizeWorksheet(&ws)
	return ws
}

func loadHDF(path string) (Sheet, error) {
	out, err := runHDFBridge("load", path, nil)
	if err != nil {
		return Sheet{}, err
	}
	var payload hdfPayload
	if err := json.Unmarshal(out, &payload); err != nil {
		return Sheet{}, fmt.Errorf("invalid HDF5 bridge payload: %w", err)
	}
	if len(payload.Sheets) == 0 {
		s := Default()
		s.Path = path
		return s, nil
	}
	worksheets := make([]Worksheet, len(payload.Sheets))
	for i, hdfSheet := range payload.Sheets {
		worksheets[i] = Worksheet{
			Name:         worksheetName(hdfSheet.Name, i),
			Columns:      normalizeColumns(hdfSheet.Columns),
			Rows:         cloneRows(hdfSheet.Rows),
			ColumnWidths: normalizeWidths(hdfSheet.ColumnWidths, len(hdfSheet.Columns)),
		}
		normalizeWorksheet(&worksheets[i])
	}
	s := Sheet{Path: path, Worksheets: worksheets, ActiveSheet: clamp(payload.ActiveSheet, 0, len(worksheets)-1)}
	s.syncActiveFromWorkbook()
	return s, nil
}

func (s *Sheet) saveHDF(path string, widths []int) error {
	s.SetColumnWidths(widths)
	worksheets := s.worksheetsForSave()
	payload := hdfPayload{
		ActiveSheet: clamp(s.ActiveSheet, 0, len(worksheets)-1),
		Sheets:      make([]hdfSheet, len(worksheets)),
	}
	for i, ws := range worksheets {
		normalizeWorksheet(&ws)
		payload.Sheets[i] = hdfSheet{
			Name:         worksheetName(ws.Name, i),
			Columns:      cloneStrings(ws.Columns),
			Rows:         cloneRows(ws.Rows),
			ColumnWidths: normalizeWidths(ws.ColumnWidths, len(ws.Columns)),
		}
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = runHDFBridge("save", path, body)
	return err
}

func loadParquet(path string) (Sheet, error) {
	file, err := os.Open(path)
	if err != nil {
		return Sheet{}, err
	}
	stat, err := file.Stat()
	if err != nil {
		file.Close()
		return Sheet{}, err
	}
	pfile, err := parquet.OpenFile(file, stat.Size())
	file.Close()
	if err != nil {
		return Sheet{}, err
	}
	if raw, ok := pfile.Lookup(vixlWorkbookMetadataKey); ok && strings.TrimSpace(raw) != "" {
		return loadParquetWorkbook(path, raw)
	}
	meta := readMetadata(pfile)
	columns := parquetColumns(pfile.Schema(), meta.Columns)
	if len(columns) == 0 {
		s := Default()
		s.Path = path
		return s, nil
	}
	records, err := parquet.ReadFile[any](path)
	if err != nil {
		return Sheet{}, err
	}
	s := Sheet{Columns: normalizeColumns(columns), Path: path}
	for _, record := range records {
		row := make([]string, len(s.Columns))
		if values, ok := record.(map[string]any); ok {
			for c, col := range columns {
				row[c] = cellString(values[col])
			}
		}
		s.Rows = append(s.Rows, row)
	}
	s.ColumnWidths = metadataColumnWidths(meta, s.Columns)
	s.ensureShape()
	return s, nil
}

func loadParquetWorkbook(path, rawMeta string) (Sheet, error) {
	var meta workbookMetadata
	if err := json.Unmarshal([]byte(rawMeta), &meta); err != nil {
		return Sheet{}, fmt.Errorf("invalid %s parquet metadata: %w", vixlWorkbookMetadataKey, err)
	}
	if len(meta.Sheets) == 0 {
		s := Default()
		s.Path = path
		return s, nil
	}
	records, err := parquet.ReadFile[workbookCellRecord](path)
	if err != nil {
		return Sheet{}, err
	}
	worksheets := make([]Worksheet, len(meta.Sheets))
	for i, sheetMeta := range meta.Sheets {
		worksheets[i] = Worksheet{
			Name:         worksheetName(sheetMeta.Name, i),
			Columns:      normalizeColumns(sheetMeta.Columns),
			ColumnWidths: normalizeWidths(sheetMeta.ColumnWidths, len(sheetMeta.Columns)),
		}
	}
	for _, record := range records {
		sheetIndex := int(record.SheetIndex)
		rowIndex := int(record.RowIndex)
		columnIndex := int(record.ColumnIndex)
		if sheetIndex < 0 || sheetIndex >= len(worksheets) || rowIndex < 0 || columnIndex < 0 {
			continue
		}
		ws := &worksheets[sheetIndex]
		if columnIndex >= len(ws.Columns) {
			continue
		}
		for len(ws.Rows) <= rowIndex {
			ws.Rows = append(ws.Rows, make([]string, len(ws.Columns)))
		}
		ws.Rows[rowIndex][columnIndex] = record.Value
	}
	for i := range worksheets {
		normalizeWorksheet(&worksheets[i])
	}
	s := Sheet{Path: path, Worksheets: worksheets, ActiveSheet: clamp(meta.ActiveSheet, 0, len(worksheets)-1)}
	s.syncActiveFromWorkbook()
	return s, nil
}

func (s *Sheet) saveDelimited(path, ext string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	writer := csv.NewWriter(file)
	if ext == ".tsv" {
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
	return writer.Error()
}

func (s *Sheet) saveXLSX(path string, widths []int) error {
	s.SetColumnWidths(widths)
	file := excelize.NewFile()
	defer file.Close()
	worksheets := s.worksheetsForSave()
	usedNames := map[string]bool{}
	for i, ws := range worksheets {
		sheetName := xlsxSafeSheetName(ws.Name, i, usedNames)
		if i == 0 {
			if err := file.SetSheetName(file.GetSheetName(0), sheetName); err != nil {
				return err
			}
		} else if _, err := file.NewSheet(sheetName); err != nil {
			return err
		}
		if err := writeXLSXWorksheet(file, sheetName, ws); err != nil {
			return err
		}
	}
	if len(worksheets) > 0 {
		file.SetActiveSheet(clamp(s.ActiveSheet, 0, len(worksheets)-1))
	}
	return file.SaveAs(path)
}

func writeXLSXWorksheet(file *excelize.File, sheetName string, ws Worksheet) error {
	normalizeWorksheet(&ws)
	for c, name := range ws.Columns {
		cell, err := excelize.CoordinatesToCellName(c+1, 1)
		if err != nil {
			return err
		}
		if err := file.SetCellStr(sheetName, cell, name); err != nil {
			return err
		}
		if c < len(ws.ColumnWidths) && ws.ColumnWidths[c] > 0 {
			colName, err := excelize.ColumnNumberToName(c + 1)
			if err != nil {
				return err
			}
			if err := file.SetColWidth(sheetName, colName, colName, float64(ws.ColumnWidths[c])); err != nil {
				return err
			}
		}
	}
	for r, row := range ws.Rows {
		for c := range ws.Columns {
			cell, err := excelize.CoordinatesToCellName(c+1, r+2)
			if err != nil {
				return err
			}
			value := ""
			if c < len(row) {
				value = row[c]
			}
			if err := file.SetCellStr(sheetName, cell, value); err != nil {
				return err
			}
		}
	}
	return nil
}

func (s *Sheet) saveParquet(path string, widths []int) error {
	s.SetColumnWidths(widths)
	if s.SheetCount() > 1 {
		return s.saveParquetWorkbook(path)
	}
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	fieldNames := parquetFieldNames(s.Columns)
	group := parquet.Group{}
	for _, name := range fieldNames {
		group[name] = parquet.Optional(parquet.String())
	}
	schema := parquet.NewSchema("vixl", group)
	writer := parquet.NewGenericWriter[any](file, schema)
	if metadata := writeMetadata(s.Columns, fieldNames, widths); metadata != "" {
		writer.SetKeyValueMetadata(vixlMetadataKey, metadata)
	}
	rows := make([]any, len(s.Rows))
	for r, row := range s.Rows {
		record := make(map[string]any, len(fieldNames))
		for c, name := range fieldNames {
			value := ""
			if c < len(row) {
				value = row[c]
			}
			record[name] = value
		}
		rows[r] = record
	}
	if len(rows) > 0 {
		if _, err := writer.Write(rows); err != nil {
			writer.Close()
			return err
		}
	}
	return writer.Close()
}

func (s *Sheet) saveParquetWorkbook(path string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	worksheets := s.worksheetsForSave()
	schema := parquet.NewSchema("vixl_workbook", parquet.Group{
		"sheet_index":  parquet.Int(64),
		"row_index":    parquet.Int(64),
		"column_index": parquet.Int(64),
		"value":        parquet.Optional(parquet.String()),
	})
	writer := parquet.NewGenericWriter[workbookCellRecord](file, schema)
	if metadata := writeWorkbookMetadata(worksheets, s.ActiveSheet); metadata != "" {
		writer.SetKeyValueMetadata(vixlWorkbookMetadataKey, metadata)
	}
	var records []workbookCellRecord
	for sheetIndex, ws := range worksheets {
		for rowIndex, row := range ws.Rows {
			for columnIndex := range ws.Columns {
				value := ""
				if columnIndex < len(row) {
					value = row[columnIndex]
				}
				records = append(records, workbookCellRecord{
					SheetIndex:  int64(sheetIndex),
					RowIndex:    int64(rowIndex),
					ColumnIndex: int64(columnIndex),
					Value:       value,
				})
			}
		}
	}
	if len(records) > 0 {
		if _, err := writer.Write(records); err != nil {
			writer.Close()
			return err
		}
	}
	return writer.Close()
}

func (s *Sheet) ensureShape() {
	if len(s.Columns) == 0 && len(s.Rows) == 0 && len(s.Worksheets) > 0 {
		s.syncActiveFromWorkbook()
		return
	}
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
	s.ColumnWidths = normalizeWidths(s.ColumnWidths, len(s.Columns))
	s.syncActiveToWorkbook()
}

func (s *Sheet) syncActiveToWorkbook() {
	if len(s.Worksheets) == 0 {
		s.Worksheets = []Worksheet{{Name: "Sheet1"}}
		s.ActiveSheet = 0
	}
	s.ActiveSheet = clamp(s.ActiveSheet, 0, len(s.Worksheets)-1)
	name := worksheetName(s.Worksheets[s.ActiveSheet].Name, s.ActiveSheet)
	s.Worksheets[s.ActiveSheet] = Worksheet{
		Name:         name,
		Columns:      cloneStrings(s.Columns),
		Rows:         cloneRows(s.Rows),
		ColumnWidths: normalizeWidths(s.ColumnWidths, len(s.Columns)),
	}
}

func (s *Sheet) syncActiveFromWorkbook() {
	if len(s.Worksheets) == 0 {
		s.ensureShape()
		return
	}
	s.ActiveSheet = clamp(s.ActiveSheet, 0, len(s.Worksheets)-1)
	ws := s.Worksheets[s.ActiveSheet]
	normalizeWorksheet(&ws)
	s.Worksheets[s.ActiveSheet] = ws
	s.Columns = cloneStrings(ws.Columns)
	s.Rows = cloneRows(ws.Rows)
	s.ColumnWidths = normalizeWidths(ws.ColumnWidths, len(ws.Columns))
}

func (s *Sheet) worksheetsForSave() []Worksheet {
	s.ensureShape()
	out := make([]Worksheet, len(s.Worksheets))
	for i, ws := range s.Worksheets {
		normalizeWorksheet(&ws)
		out[i] = ws
	}
	if len(out) == 0 {
		ws := Worksheet{
			Name:         "Sheet1",
			Columns:      cloneStrings(s.Columns),
			Rows:         cloneRows(s.Rows),
			ColumnWidths: normalizeWidths(s.ColumnWidths, len(s.Columns)),
		}
		normalizeWorksheet(&ws)
		return []Worksheet{ws}
	}
	return out
}

func normalizeWorksheet(ws *Worksheet) {
	if strings.TrimSpace(ws.Name) == "" {
		ws.Name = "Sheet1"
	}
	ws.Columns = normalizeColumns(ws.Columns)
	if len(ws.Rows) == 0 {
		ws.Rows = [][]string{make([]string, len(ws.Columns))}
	}
	for i := range ws.Rows {
		if len(ws.Rows[i]) < len(ws.Columns) {
			ws.Rows[i] = append(ws.Rows[i], make([]string, len(ws.Columns)-len(ws.Rows[i]))...)
		}
		if len(ws.Rows[i]) > len(ws.Columns) {
			ws.Rows[i] = ws.Rows[i][:len(ws.Columns)]
		}
	}
	ws.ColumnWidths = normalizeWidths(ws.ColumnWidths, len(ws.Columns))
}

func defaultWorksheet(name string, index int) Worksheet {
	base := Default()
	return Worksheet{
		Name:         worksheetName(name, index),
		Columns:      cloneStrings(base.Columns),
		Rows:         cloneRows(base.Rows),
		ColumnWidths: normalizeWidths(base.ColumnWidths, len(base.Columns)),
	}
}

func worksheetName(name string, index int) string {
	name = strings.TrimSpace(name)
	if name == "" {
		return "Sheet" + strconv.Itoa(index+1)
	}
	return name
}

func (s *Sheet) nextSheetName() string {
	seen := map[string]bool{}
	for _, name := range s.SheetNames() {
		seen[strings.ToLower(name)] = true
	}
	for i := 1; ; i++ {
		name := "Sheet" + strconv.Itoa(i)
		if !seen[strings.ToLower(name)] {
			return name
		}
	}
}

func supportedLoadExt(ext string) bool {
	switch ext {
	case "", ".csv", ".tsv", ".parquet", ".xlsx", ".xls", ".h5", ".hdf", ".hdf5":
		return true
	default:
		return false
	}
}

func supportedSaveExt(ext string) bool {
	switch ext {
	case "", ".csv", ".tsv", ".parquet", ".xlsx", ".h5", ".hdf", ".hdf5":
		return true
	default:
		return false
	}
}

func singleSheetExt(ext string) bool {
	switch ext {
	case "", ".csv", ".tsv":
		return true
	default:
		return false
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

func normalizeWidths(widths []int, count int) []int {
	if count == 0 || len(widths) == 0 {
		return nil
	}
	out := make([]int, count)
	copy(out, widths)
	for i := range out {
		if out[i] < 0 {
			out[i] = 0
		}
	}
	return out
}

func cloneStrings(values []string) []string {
	if len(values) == 0 {
		return nil
	}
	return append([]string(nil), values...)
}

func cloneRows(rows [][]string) [][]string {
	if len(rows) == 0 {
		return nil
	}
	out := make([][]string, len(rows))
	for i, row := range rows {
		out[i] = cloneStrings(row)
	}
	return out
}

func xlsxSafeSheetName(name string, index int, used map[string]bool) string {
	name = strings.TrimSpace(name)
	if name == "" {
		name = "Sheet" + strconv.Itoa(index+1)
	}
	replacer := strings.NewReplacer(":", "_", "\\", "_", "/", "_", "?", "_", "*", "_", "[", "_", "]", "_")
	name = replacer.Replace(name)
	name = strings.TrimSpace(name)
	if name == "" {
		name = "Sheet" + strconv.Itoa(index+1)
	}
	name = trimSheetName(name, 31)
	base := name
	suffix := 2
	for used[strings.ToLower(name)] {
		extra := "_" + strconv.Itoa(suffix)
		name = trimSheetName(base, 31-len(extra)) + extra
		suffix++
	}
	used[strings.ToLower(name)] = true
	return name
}

func trimSheetName(name string, limit int) string {
	if limit <= 0 {
		return ""
	}
	runes := []rune(name)
	if len(runes) <= limit {
		return name
	}
	return string(runes[:limit])
}

func runHDFBridge(action, path string, input []byte) ([]byte, error) {
	python, err := hdfPythonPath()
	if err != nil {
		return nil, err
	}
	cmd := exec.Command(python, "-c", hdfBridgeSource, action, path)
	if input != nil {
		cmd.Stdin = bytes.NewReader(input)
	}
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		message := strings.TrimSpace(stderr.String())
		if message == "" {
			message = err.Error()
		}
		return nil, fmt.Errorf("HDF5 %s failed: %s", action, message)
	}
	return stdout.Bytes(), nil
}

func hdfPythonPath() (string, error) {
	if path := strings.TrimSpace(os.Getenv("VIXL_HDF_PYTHON")); path != "" {
		return path, nil
	}
	if home, err := os.UserHomeDir(); err == nil {
		managed := filepath.Join(home, ".vixl", "hdf", "bin", "python")
		if isExecutable(managed) {
			return managed, nil
		}
	}
	for _, candidate := range []string{"python3", "python"} {
		path, err := exec.LookPath(candidate)
		if err != nil {
			continue
		}
		if pythonHasPyTables(path) {
			return path, nil
		}
	}
	return "", errors.New("HDF5 support requires the vixl-managed PyTables runtime; run: bash install.sh from <vixl-source-path>")
}

func isExecutable(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir() && info.Mode()&0o111 != 0
}

func pythonHasPyTables(path string) bool {
	cmd := exec.Command(path, "-c", "import pandas, tables")
	return cmd.Run() == nil
}

func loadXLSXColumnWidths(file *excelize.File, sheet string, count int) []int {
	widths := make([]int, count)
	defaultWidth := 9.140625
	if props, err := file.GetSheetProps(sheet); err == nil && props.DefaultColWidth != nil && *props.DefaultColWidth > 0 {
		defaultWidth = *props.DefaultColWidth
	}
	for c := 0; c < count; c++ {
		name, err := excelize.ColumnNumberToName(c + 1)
		if err != nil {
			continue
		}
		width, err := file.GetColWidth(sheet, name)
		if err != nil {
			continue
		}
		if width > 0 && math.Abs(width-defaultWidth) > 0.25 {
			widths[c] = int(math.Round(width))
		}
	}
	return normalizeWidths(widths, count)
}

func safeXLSRow(sheet *xls.WorkSheet, index int) (row *xls.Row) {
	defer func() {
		if recover() != nil {
			row = nil
		}
	}()
	return sheet.Row(index)
}

func xlsRowValues(row *xls.Row) []string {
	if row == nil {
		return nil
	}
	values := make([]string, row.LastCol())
	for c := 0; c < row.LastCol(); c++ {
		values[c] = row.Col(c)
	}
	return values
}

func parquetColumns(schema *parquet.Schema, preferred []string) []string {
	if len(preferred) > 0 {
		return append([]string(nil), preferred...)
	}
	fields := schema.Fields()
	columns := make([]string, len(fields))
	for i, field := range fields {
		columns[i] = field.Name()
	}
	return columns
}

func parquetFieldNames(columns []string) []string {
	names := make([]string, len(columns))
	seen := map[string]int{}
	for i, column := range columns {
		name := strings.TrimSpace(column)
		if name == "" {
			name = "col_" + strconv.Itoa(i+1)
		}
		if seen[name] > 0 {
			name = name + "_" + strconv.Itoa(seen[name]+1)
		}
		seen[name]++
		names[i] = name
	}
	return names
}

func readMetadata(file *parquet.File) fileMetadata {
	raw, ok := file.Lookup(vixlMetadataKey)
	if !ok || strings.TrimSpace(raw) == "" {
		return fileMetadata{}
	}
	var meta fileMetadata
	if err := json.Unmarshal([]byte(raw), &meta); err != nil {
		return fileMetadata{}
	}
	return meta
}

func writeMetadata(columns, fieldNames []string, widths []int) string {
	meta := fileMetadata{
		Columns:      fieldNames,
		ColumnWidths: map[string]int{},
	}
	for i, width := range widths {
		if i < len(fieldNames) && width > 0 {
			meta.ColumnWidths[fieldNames[i]] = width
		}
	}
	if len(meta.ColumnWidths) == 0 {
		meta.ColumnWidths = nil
	}
	for i, column := range columns {
		if i < len(fieldNames) && column != fieldNames[i] {
			meta.Columns = fieldNames
			break
		}
	}
	body, err := json.Marshal(meta)
	if err != nil {
		return ""
	}
	return string(body)
}

func writeWorkbookMetadata(worksheets []Worksheet, active int) string {
	if len(worksheets) == 0 {
		return ""
	}
	active = clamp(active, 0, len(worksheets)-1)
	meta := workbookMetadata{
		ActiveSheet: active,
		Sheets:      make([]workbookSheetMeta, len(worksheets)),
	}
	for i, ws := range worksheets {
		normalizeWorksheet(&ws)
		meta.Sheets[i] = workbookSheetMeta{
			Name:         worksheetName(ws.Name, i),
			Columns:      cloneStrings(ws.Columns),
			ColumnWidths: normalizeWidths(ws.ColumnWidths, len(ws.Columns)),
		}
	}
	body, err := json.Marshal(meta)
	if err != nil {
		return ""
	}
	return string(body)
}

func metadataColumnWidths(meta fileMetadata, columns []string) []int {
	if len(meta.ColumnWidths) == 0 {
		return nil
	}
	widths := make([]int, len(columns))
	for i, column := range columns {
		widths[i] = meta.ColumnWidths[column]
	}
	return normalizeWidths(widths, len(columns))
}

func cellString(value any) string {
	switch value := value.(type) {
	case nil:
		return ""
	case string:
		return value
	case []byte:
		return string(value)
	default:
		return fmt.Sprint(value)
	}
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

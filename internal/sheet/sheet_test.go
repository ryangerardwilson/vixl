package sheet

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	parquet "github.com/parquet-go/parquet-go"
	"github.com/xuri/excelize/v2"
)

func TestLoadSaveCSV(t *testing.T) {
	path := filepath.Join(t.TempDir(), "data.csv")
	if err := os.WriteFile(path, []byte("a,b\n1,2\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	s, err := LoadOrCreate(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(s.Columns) != 2 || s.Rows[0][0] != "1" {
		t.Fatalf("unexpected sheet: %#v", s)
	}
	s.Set(0, 1, "3")
	if err := s.Save(""); err != nil {
		t.Fatal(err)
	}
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "a,b\n1,3\n" {
		t.Fatalf("saved body = %q", string(body))
	}
}

func TestUnsupportedTypeFails(t *testing.T) {
	if _, err := LoadOrCreate("data.sqlite"); err == nil {
		t.Fatal("expected unsupported type error")
	}
}

func TestLoadSaveXLSXWithColumnWidths(t *testing.T) {
	path := filepath.Join(t.TempDir(), "data.xlsx")
	s := Sheet{
		Columns: []string{"name", "amount"},
		Rows:    [][]string{{"Ada", "42"}},
	}
	if err := s.Save(path, []int{18, 11}); err != nil {
		t.Fatal(err)
	}

	loaded, err := LoadOrCreate(path)
	if err != nil {
		t.Fatal(err)
	}
	if loaded.Columns[0] != "name" || loaded.Rows[0][1] != "42" {
		t.Fatalf("unexpected xlsx sheet: %#v", loaded)
	}
	if len(loaded.ColumnWidths) != 2 || loaded.ColumnWidths[0] != 18 || loaded.ColumnWidths[1] != 11 {
		t.Fatalf("xlsx widths = %#v, want [18 11]", loaded.ColumnWidths)
	}
}

func TestLoadSaveXLSXPreservesMultipleSheets(t *testing.T) {
	path := filepath.Join(t.TempDir(), "book.xlsx")
	file := excelize.NewFile()
	defer file.Close()
	if err := file.SetSheetName("Sheet1", "People"); err != nil {
		t.Fatal(err)
	}
	citiesIndex, err := file.NewSheet("Cities")
	if err != nil {
		t.Fatal(err)
	}
	file.SetActiveSheet(citiesIndex)
	if err := file.SetCellStr("People", "A1", "name"); err != nil {
		t.Fatal(err)
	}
	if err := file.SetCellStr("People", "A2", "Ada"); err != nil {
		t.Fatal(err)
	}
	if err := file.SetColWidth("People", "A", "A", 18); err != nil {
		t.Fatal(err)
	}
	if err := file.SetCellStr("Cities", "A1", "city"); err != nil {
		t.Fatal(err)
	}
	if err := file.SetCellStr("Cities", "A2", "Delhi"); err != nil {
		t.Fatal(err)
	}
	if err := file.SetColWidth("Cities", "A", "A", 15); err != nil {
		t.Fatal(err)
	}
	if err := file.SaveAs(path); err != nil {
		t.Fatal(err)
	}

	s, err := LoadOrCreate(path)
	if err != nil {
		t.Fatal(err)
	}
	if s.SheetCount() != 2 {
		t.Fatalf("sheet count = %d, want 2", s.SheetCount())
	}
	if s.SheetName() != "Cities" {
		t.Fatalf("active sheet = %q, want Cities", s.SheetName())
	}
	if s.Rows[0][0] != "Delhi" {
		t.Fatalf("active sheet row = %#v, want Cities data", s.Rows[0])
	}
	if !s.SwitchSheet(-1) || s.SheetName() != "People" {
		t.Fatalf("switch to people failed: active=%q", s.SheetName())
	}
	s.Set(0, 0, "Grace")
	if err := s.Save(path); err != nil {
		t.Fatal(err)
	}

	reopened, err := excelize.OpenFile(path)
	if err != nil {
		t.Fatal(err)
	}
	defer reopened.Close()
	if got := reopened.GetSheetList(); len(got) != 2 || got[0] != "People" || got[1] != "Cities" {
		t.Fatalf("saved sheets = %#v, want People/Cities", got)
	}
	peopleName, err := reopened.GetCellValue("People", "A2")
	if err != nil {
		t.Fatal(err)
	}
	cityName, err := reopened.GetCellValue("Cities", "A2")
	if err != nil {
		t.Fatal(err)
	}
	if peopleName != "Grace" || cityName != "Delhi" {
		t.Fatalf("saved values people=%q city=%q", peopleName, cityName)
	}
	width, err := reopened.GetColWidth("People", "A")
	if err != nil {
		t.Fatal(err)
	}
	if int(width+0.5) != 18 {
		t.Fatalf("people width = %.2f, want 18", width)
	}
}

func TestLoadSaveParquetWithVixlMetadata(t *testing.T) {
	path := filepath.Join(t.TempDir(), "data.parquet")
	s := Sheet{
		Columns: []string{"name", "amount"},
		Rows:    [][]string{{"Ada", "42"}},
	}
	if err := s.Save(path, []int{18, 9}); err != nil {
		t.Fatal(err)
	}

	file, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	stat, err := file.Stat()
	if err != nil {
		t.Fatal(err)
	}
	pfile, err := parquet.OpenFile(file, stat.Size())
	file.Close()
	if err != nil {
		t.Fatal(err)
	}
	if raw, ok := pfile.Lookup(vixlMetadataKey); !ok || !strings.Contains(raw, `"amount":9`) {
		t.Fatalf("missing parquet vixl metadata: ok=%v raw=%q", ok, raw)
	}

	loaded, err := LoadOrCreate(path)
	if err != nil {
		t.Fatal(err)
	}
	if loaded.Columns[0] != "name" || loaded.Rows[0][1] != "42" {
		t.Fatalf("unexpected parquet sheet: %#v", loaded)
	}
	if len(loaded.ColumnWidths) != 2 || loaded.ColumnWidths[0] != 18 || loaded.ColumnWidths[1] != 9 {
		t.Fatalf("parquet widths = %#v, want [18 9]", loaded.ColumnWidths)
	}
}

func TestLoadSaveParquetPreservesMultipleSheetsAsVixlWorkbook(t *testing.T) {
	path := filepath.Join(t.TempDir(), "book.parquet")
	s := Sheet{
		Columns:      []string{"score"},
		Rows:         [][]string{{"99"}},
		ColumnWidths: []int{8},
		Worksheets: []Worksheet{
			{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}, ColumnWidths: []int{12}},
			{Name: "Scores", Columns: []string{"score"}, Rows: [][]string{{"99"}}, ColumnWidths: []int{8}},
		},
		ActiveSheet: 1,
	}
	if err := s.Save(path); err != nil {
		t.Fatal(err)
	}

	file, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	stat, err := file.Stat()
	if err != nil {
		t.Fatal(err)
	}
	pfile, err := parquet.OpenFile(file, stat.Size())
	file.Close()
	if err != nil {
		t.Fatal(err)
	}
	if raw, ok := pfile.Lookup(vixlWorkbookMetadataKey); !ok || !strings.Contains(raw, `"Scores"`) {
		t.Fatalf("missing parquet workbook metadata: ok=%v raw=%q", ok, raw)
	}

	loaded, err := LoadOrCreate(path)
	if err != nil {
		t.Fatal(err)
	}
	if loaded.SheetCount() != 2 || loaded.SheetName() != "Scores" {
		t.Fatalf("loaded sheet count/name = %d/%q", loaded.SheetCount(), loaded.SheetName())
	}
	if loaded.Rows[0][0] != "99" {
		t.Fatalf("active rows = %#v, want Scores data", loaded.Rows)
	}
	if !loaded.SwitchSheet(-1) || loaded.SheetName() != "People" || loaded.Rows[0][0] != "Ada" {
		t.Fatalf("people sheet not restored: active=%q rows=%#v", loaded.SheetName(), loaded.Rows)
	}
	if len(loaded.ColumnWidths) != 1 || loaded.ColumnWidths[0] != 12 {
		t.Fatalf("people widths = %#v, want [12]", loaded.ColumnWidths)
	}
}

func TestSaveXLSIsUnsupported(t *testing.T) {
	s := Sheet{
		Columns: []string{"name"},
		Rows:    [][]string{{"Ada"}},
	}
	err := s.Save(filepath.Join(t.TempDir(), "data.xls"))
	if err == nil || !strings.Contains(err.Error(), "saving .xls is not supported") {
		t.Fatalf("xls save error = %v", err)
	}
}

func TestAddSheetOnlyForWorkbookFormats(t *testing.T) {
	workbook := Default()
	workbook.Path = filepath.Join(t.TempDir(), "book.xlsx")
	if !workbook.SupportsSheets() {
		t.Fatal("xlsx should support sheets")
	}
	if !workbook.AddSheet() {
		t.Fatal("expected xlsx AddSheet to succeed")
	}
	if workbook.SheetCount() != 2 || workbook.SheetName() != "Sheet2" {
		t.Fatalf("workbook sheets = %d active=%q", workbook.SheetCount(), workbook.SheetName())
	}

	csvSheet := Default()
	csvSheet.Path = filepath.Join(t.TempDir(), "data.csv")
	if csvSheet.SupportsSheets() {
		t.Fatal("csv should be single-sheet")
	}
	if csvSheet.AddSheet() {
		t.Fatal("expected csv AddSheet to fail")
	}
	if csvSheet.SheetCount() != 1 {
		t.Fatalf("csv sheet count = %d, want 1", csvSheet.SheetCount())
	}
}

func TestRenameSheetOnlyForWorkbookFormats(t *testing.T) {
	workbook := Default()
	workbook.Path = filepath.Join(t.TempDir(), "book.xlsx")
	if !workbook.RenameSheet(" Metrics ") {
		t.Fatal("expected xlsx RenameSheet to succeed")
	}
	if workbook.SheetName() != "Metrics" {
		t.Fatalf("sheet name = %q, want Metrics", workbook.SheetName())
	}
	if workbook.RenameSheet("   ") {
		t.Fatal("expected blank RenameSheet to fail")
	}
	if workbook.SheetName() != "Metrics" {
		t.Fatalf("blank rename changed sheet name to %q", workbook.SheetName())
	}

	csvSheet := Default()
	csvSheet.Path = filepath.Join(t.TempDir(), "data.csv")
	if csvSheet.RenameSheet("Metrics") {
		t.Fatal("expected csv RenameSheet to fail")
	}
	if csvSheet.SheetName() != "Sheet1" {
		t.Fatalf("csv sheet name = %q, want Sheet1", csvSheet.SheetName())
	}
}

func TestSaveMultipleSheetsToSingleTableFormatFails(t *testing.T) {
	s := Default()
	if !s.AddSheet() {
		t.Fatal("expected default workbook AddSheet to succeed")
	}
	err := s.Save(filepath.Join(t.TempDir(), "data.csv"))
	if err == nil || !strings.Contains(err.Error(), "single-table format") {
		t.Fatalf("multi-sheet csv save error = %v", err)
	}
}

func TestHDF5MissingFilesCreateWritableWorkbook(t *testing.T) {
	for _, ext := range []string{".h5", ".hdf", ".hdf5"} {
		path := filepath.Join(t.TempDir(), "data"+ext)
		loaded, err := LoadOrCreate(path)
		if err != nil {
			t.Fatalf("load %s error = %v", ext, err)
		}
		if loaded.Path != path || loaded.SheetName() != "Sheet1" {
			t.Fatalf("new hdf workbook = %#v", loaded)
		}
	}
}

func TestLoadSaveHDF5WithPyTables(t *testing.T) {
	python, ok := testHDFPython()
	if !ok {
		t.Skip("PyTables runtime unavailable")
	}
	t.Setenv("VIXL_HDF_PYTHON", python)
	path := filepath.Join(t.TempDir(), "book.h5")
	s := Sheet{
		Columns:      []string{"score"},
		Rows:         [][]string{{"99"}},
		ColumnWidths: []int{8},
		Worksheets: []Worksheet{
			{Name: "People", Columns: []string{"name"}, Rows: [][]string{{"Ada"}}, ColumnWidths: []int{12}},
			{Name: "Scores", Columns: []string{"score"}, Rows: [][]string{{"99"}}, ColumnWidths: []int{8}},
		},
		ActiveSheet: 1,
	}
	if err := s.Save(path); err != nil {
		t.Fatal(err)
	}
	loaded, err := LoadOrCreate(path)
	if err != nil {
		t.Fatal(err)
	}
	if loaded.SheetCount() != 2 || loaded.SheetName() != "Scores" || loaded.Rows[0][0] != "99" {
		t.Fatalf("loaded hdf workbook = %#v", loaded)
	}
	if !loaded.SwitchSheet(-1) || loaded.SheetName() != "People" || loaded.Rows[0][0] != "Ada" {
		t.Fatalf("people hdf sheet not restored: active=%q rows=%#v", loaded.SheetName(), loaded.Rows)
	}
}

func testHDFPython() (string, bool) {
	if path := strings.TrimSpace(os.Getenv("VIXL_HDF_PYTHON")); path != "" {
		return path, true
	}
	if home, err := os.UserHomeDir(); err == nil {
		path := filepath.Join(home, ".vixl", "hdf", "bin", "python")
		if info, err := os.Stat(path); err == nil && !info.IsDir() && info.Mode()&0o111 != 0 {
			return path, true
		}
	}
	return "", false
}

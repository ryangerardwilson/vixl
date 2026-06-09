package sheet

import (
	"os"
	"path/filepath"
	"testing"
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
	if _, err := LoadOrCreate("data.parquet"); err == nil {
		t.Fatal("expected unsupported type error")
	}
}

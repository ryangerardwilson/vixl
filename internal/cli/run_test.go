package cli

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ryangerardwilson/vixl/internal/app"
)

func TestHelpVersionAndOpenDispatch(t *testing.T) {
	called := false
	restore := SetRunAppForTest(func(cfg app.Config) int {
		called = true
		if cfg.Path != "data.csv" {
			t.Fatalf("Path = %q", cfg.Path)
		}
		return 0
	})
	defer restore()

	var stdout, stderr bytes.Buffer
	if code := Main([]string{"help"}, &stdout, &stderr); code != 0 {
		t.Fatalf("help exit = %d", code)
	}
	if !strings.Contains(stdout.String(), "vixl open data.csv") {
		t.Fatalf("help output = %s", stdout.String())
	}
	stdout.Reset()
	if code := Main([]string{"version"}, &stdout, &stderr); code != 0 || strings.TrimSpace(stdout.String()) == "" {
		t.Fatalf("bad version exit/output")
	}
	if code := Main([]string{"open", "data.csv"}, &stdout, &stderr); code != 0 || !called {
		t.Fatalf("open did not dispatch")
	}
}

func TestConfigCreatesRealConfig(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", tmp)
	t.Setenv("VISUAL", "true")
	var stdout, stderr bytes.Buffer
	if code := Main([]string{"config"}, &stdout, &stderr); code != 0 {
		t.Fatalf("config exit = %d, stderr = %s", code, stderr.String())
	}
	if _, err := os.Stat(filepath.Join(tmp, "vixl", "config.json")); err != nil {
		t.Fatalf("config missing: %v", err)
	}
}

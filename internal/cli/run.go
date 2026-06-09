package cli

import (
	"fmt"
	"io"
	"os"
	"os/exec"

	"github.com/ryangerardwilson/vixl/internal/app"
	"github.com/ryangerardwilson/vixl/internal/config"
	"github.com/ryangerardwilson/vixl/internal/version"
)

const installScriptURL = "https://raw.githubusercontent.com/ryangerardwilson/vixl/main/install.sh"

var runApp = app.Run

func Main(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 || sameArgs(args, "help") {
		fmt.Fprint(stdout, HelpText)
		return 0
	}
	if sameArgs(args, "version") {
		fmt.Fprintln(stdout, version.Version)
		return 0
	}
	if sameArgs(args, "upgrade") {
		return upgrade(stdout, stderr)
	}
	if args[0] == "config" {
		if len(args) != 1 {
			fmt.Fprintln(stderr, "Usage: vixl config")
			return 1
		}
		return openConfig(stderr)
	}
	if args[0] == "open" {
		if len(args) > 2 {
			fmt.Fprintln(stderr, "Usage: vixl open [path]")
			return 1
		}
		path := ""
		if len(args) == 2 {
			path = args[1]
		}
		return runApp(app.Config{Path: path})
	}
	if args[0][0] == '-' {
		fmt.Fprintln(stderr, "Use declarative commands. Run: vixl help")
		return 1
	}
	fmt.Fprintln(stderr, "Usage: vixl open [path]")
	return 1
}

func openConfig(stderr io.Writer) int {
	if err := config.Ensure(); err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	editor := os.Getenv("VISUAL")
	if editor == "" {
		editor = os.Getenv("EDITOR")
	}
	if editor == "" {
		editor = "vim"
	}
	cmd := exec.Command(editor, config.Path())
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			return exitErr.ExitCode()
		}
		fmt.Fprintln(stderr, err)
		return 1
	}
	return 0
}

func upgrade(stdout, stderr io.Writer) int {
	cmd := exec.Command("bash", "-c", "curl -fsSL "+installScriptURL+" | bash -s -- upgrade")
	cmd.Stdin = os.Stdin
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	if err := cmd.Run(); err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			return exitErr.ExitCode()
		}
		fmt.Fprintln(stderr, err)
		return 1
	}
	return 0
}

func sameArgs(args []string, values ...string) bool {
	if len(args) != len(values) {
		return false
	}
	for i := range args {
		if args[i] != values[i] {
			return false
		}
	}
	return true
}

func SetRunAppForTest(fn func(app.Config) int) func() {
	previous := runApp
	runApp = fn
	return func() {
		runApp = previous
	}
}

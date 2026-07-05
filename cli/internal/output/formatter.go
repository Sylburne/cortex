package output

import (
	"encoding/json"
	"fmt"
	"os"
)

func JSON(v interface{}) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(v)
}

func Text(format string, args ...interface{}) {
	fmt.Printf(format, args...)
}

func Error(msg string) {
	fmt.Fprintln(os.Stderr, "Error:", msg)
	os.Exit(1)
}

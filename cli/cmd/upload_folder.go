package cmd

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"

	"github.com/spf13/cobra"
)

var uploadFolderCmd = &cobra.Command{
	Use:   "upload-folder <path>",
	Short: "Upload an entire folder to a notebook",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		concurrency, _ := cmd.Flags().GetInt("concurrency")
		extensions, _ := cmd.Flags().GetString("extensions")

		if nbID == "" {
			return fmt.Errorf("--nb flag is required")
		}

		rootDir := args[0]
		absRoot, _ := filepath.Abs(rootDir)

		// Scan files
		type fileInfo struct {
			path     string
			relPath  string
			relDir   string
			size     int64
			hash     string
		}
		var files []fileInfo
		extMap := map[string]bool{}
		if extensions != "" {
			for _, ext := range splitExts(extensions) {
				extMap[ext] = true
			}
		}

		err = filepath.Walk(absRoot, func(path string, info os.FileInfo, walkErr error) error {
			if walkErr != nil || info.IsDir() {
				return nil
			}
			ext := filepath.Ext(path)
			if len(extMap) > 0 && !extMap[ext] {
				return nil
			}
			rel, _ := filepath.Rel(absRoot, path)
			relDir := filepath.Dir(rel)
			if relDir == "." {
				relDir = ""
			}

			// Compute hash
			f, _ := os.Open(path)
			defer f.Close()
			h := sha256.New()
			io.Copy(h, f)
			hash := fmt.Sprintf("%x", h.Sum(nil))

			files = append(files, fileInfo{
				path: path, relPath: filepath.Base(rel),
				relDir: relDir, size: info.Size(), hash: hash,
			})
			return nil
		})
		if err != nil {
			return fmt.Errorf("scan failed: %w", err)
		}

		fmt.Printf("Found %d files to upload\n", len(files))

		// Upload with concurrency
		var wg sync.WaitGroup
		sem := make(chan struct{}, concurrency)
		var mu sync.Mutex
		uploaded, failed, skipped := 0, 0, 0

		for _, f := range files {
			wg.Add(1)
			go func(fi fileInfo) {
				defer wg.Done()
				sem <- struct{}{}
				defer func() { <-sem }()

				apiPath := fmt.Sprintf("/api/v1/notebooks/%s/sources", nbID)
				_, uploadErr := client.UploadFile(apiPath, fi.path, fi.relDir)
				mu.Lock()
				defer mu.Unlock()
				if uploadErr != nil {
					failed++
					if verbose {
						fmt.Printf("  [fail] %s: %s\n", fi.relPath, uploadErr)
					}
				} else {
					uploaded++
					if verbose {
						fmt.Printf("  [ok] %s\n", fi.relPath)
					}
				}
			}(f)
		}
		wg.Wait()

		result := map[string]int{
			"files_uploaded": uploaded,
			"files_failed":   failed,
			"files_skipped":  skipped,
			"total":          len(files),
		}
		if output == "json" {
			enc, _ := json.MarshalIndent(result, "", "  ")
			fmt.Println(string(enc))
		} else {
			fmt.Printf("Upload complete: %d uploaded, %d failed, %d skipped (total: %d)\n",
				uploaded, failed, skipped, len(files))
		}
		return nil
	},
}

func splitExts(s string) []string {
	var exts []string
	for _, e := range splitStr(s, ",") {
		e = trimStr(e)
		if e != "" {
			exts = append(exts, e)
		}
	}
	return exts
}

func splitStr(s, sep string) []string {
	var parts []string
	for _, p := range splitByRune(s, sep[0]) {
		parts = append(parts, p)
	}
	return parts
}

func splitByRune(s string, r byte) []string {
	var parts []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == r {
			parts = append(parts, s[start:i])
			start = i + 1
		}
	}
	parts = append(parts, s[start:])
	return parts
}

func trimStr(s string) string {
	for len(s) > 0 && (s[0] == ' ' || s[0] == '\t') {
		s = s[1:]
	}
	for len(s) > 0 && (s[len(s)-1] == ' ' || s[len(s)-1] == '\t') {
		s = s[:len(s)-1]
	}
	return s
}

func init() {
	uploadFolderCmd.Flags().String("nb", "", "Notebook ID (required)")
	uploadFolderCmd.Flags().Int("concurrency", 5, "Parallel uploads")
	uploadFolderCmd.Flags().String("extensions", ".md,.mdx,.pdf,.txt,.docx,.pptx", "File extensions")
	rootCmd.AddCommand(uploadFolderCmd)
}

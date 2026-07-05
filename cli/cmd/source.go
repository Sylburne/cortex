package cmd

import (
	"encoding/json"
	"fmt"

	"github.com/qmind/cli/internal/output"
	"github.com/spf13/cobra"
)

var sourceCmd = &cobra.Command{
	Use:   "source",
	Short: "Manage sources (files)",
}

var sourceListCmd = &cobra.Command{
	Use:   "list",
	Short: "List sources in a notebook",
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		page, _ := cmd.Flags().GetInt("page")
		pageSize, _ := cmd.Flags().GetInt("page-size")
		path := fmt.Sprintf("/api/v1/notebooks/%s/sources?page=%d&page_size=%d", nbID, page, pageSize)
		data, err := client.Get(path)
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				Sources []struct {
					ID       string `json:"id"`
					Filename string `json:"filename"`
					Path     string `json:"path"`
					Status   string `json:"status"`
					FileType string `json:"file_type"`
					IsDir    bool   `json:"is_dir"`
				} `json:"sources"`
				Total int `json:"total"`
			}
			json.Unmarshal(data, &result)
			fmt.Printf("Total: %d sources\n", result.Total)
			for _, s := range result.Sources {
				dir := ""
				if s.IsDir {
					dir = "[DIR] "
				}
				fmt.Printf("%-40s %s%s (%s)\n", s.ID, dir, s.Filename, s.Status)
			}
		}
		return nil
	},
}

var sourceDeleteCmd = &cobra.Command{
	Use:   "delete <source-id>",
	Short: "Delete a source",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		_, err = client.Delete(fmt.Sprintf("/api/v1/notebooks/%s/sources/%s", nbID, args[0]))
		if err != nil {
			return err
		}
		fmt.Println("Source deleted.")
		return nil
	},
}

var sourceContentCmd = &cobra.Command{
	Use:   "content <source-id>",
	Short: "Get source content",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		data, err := client.Get(fmt.Sprintf("/api/v1/notebooks/%s/sources/%s/content", nbID, args[0]))
		if err != nil {
			return err
		}
		var result struct {
			Content  string `json:"content"`
			Filename string `json:"filename"`
		}
		json.Unmarshal(data, &result)
		fmt.Println(result.Content)
		return nil
	},
}

func init() {
	sourceListCmd.Flags().String("nb", "", "Notebook ID (required)")
	sourceListCmd.MarkFlagRequired("nb")
	sourceListCmd.Flags().Int("page", 1, "Page number")
	sourceListCmd.Flags().Int("page-size", 100, "Page size")

	sourceDeleteCmd.Flags().String("nb", "", "Notebook ID (required)")
	sourceDeleteCmd.MarkFlagRequired("nb")

	sourceContentCmd.Flags().String("nb", "", "Notebook ID (required)")
	sourceContentCmd.MarkFlagRequired("nb")

	sourceCmd.AddCommand(sourceListCmd, sourceDeleteCmd, sourceContentCmd)
	rootCmd.AddCommand(sourceCmd)
}

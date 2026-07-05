package cmd

import (
	"encoding/json"
	"fmt"

	"github.com/qmind/cli/internal/output"
	"github.com/qmind/cli/pkg/version"
	"github.com/spf13/cobra"
)

var compileCmd = &cobra.Command{
	Use:   "compile",
	Short: "Compile sources into knowledge cards",
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		cardType, _ := cmd.Flags().GetString("type")

		body := map[string]string{"card_type": cardType}
		data, err := client.Post(fmt.Sprintf("/api/v1/notebooks/%s/compile", nbID), body)
		if err != nil {
			return err
		}
		var result struct {
			JobID  string `json:"job_id"`
			Status string `json:"status"`
		}
		json.Unmarshal(data, &result)
		if output == "json" {
			var r map[string]interface{}
			json.Unmarshal(data, &r)
			output.JSON(r)
		} else {
			fmt.Printf("Compilation triggered. Job ID: %s (status: %s)\n", result.JobID, result.Status)
			fmt.Println("Use 'qmind list --nb <id> --type card' to check compiled cards later.")
		}
		return nil
	},
}

var lintCmd = &cobra.Command{
	Use:   "lint",
	Short: "Lint compiled knowledge cards",
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")

		body := map[string]interface{}{}
		data, err := client.Post(fmt.Sprintf("/api/v1/notebooks/%s/lint", nbID), body)
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				TotalCards   int `json:"total_cards"`
				CardsChecked int `json:"cards_checked"`
				Issues       []struct {
					Type     string `json:"type"`
					Severity string `json:"severity"`
					Message  string `json:"message"`
				} `json:"issues"`
			}
			json.Unmarshal(data, &result)
			fmt.Printf("Lint: %d cards checked, %d issues found\n", result.CardsChecked, len(result.Issues))
			for _, issue := range result.Issues {
				fmt.Printf("  [%s] %s: %s\n", issue.Severity, issue.Type, issue.Message)
			}
		}
		return nil
	},
}

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print version",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("qmind %s (%s)\n", version.Version, version.Commit)
	},
}

func init() {
	compileCmd.Flags().String("nb", "", "Notebook ID (required)")
	compileCmd.MarkFlagRequired("nb")
	compileCmd.Flags().String("type", "concept", "Card type: concept, summary, comparison, glossary")

	lintCmd.Flags().String("nb", "", "Notebook ID (required)")
	lintCmd.MarkFlagRequired("nb")

	rootCmd.AddCommand(compileCmd, lintCmd, versionCmd)
}

package cmd

import (
	"encoding/json"
	"fmt"

	"github.com/qmind/cli/internal/output"
	"github.com/spf13/cobra"
)

var searchCmd = &cobra.Command{
	Use:   "search <query>",
	Short: "Search knowledge base",
	Args:  cobra.MinimumNArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		topK, _ := cmd.Flags().GetInt("top-k")
		query := joinArgs(args)

		body := map[string]interface{}{"query": query, "top_k": topK}
		data, err := client.Post(fmt.Sprintf("/api/v1/notebooks/%s/search", nbID), body)
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				Results []struct {
					SourceFilename string  `json:"source_filename"`
					Content        string  `json:"content"`
					Score          float64 `json:"score"`
				} `json:"results"`
			}
			json.Unmarshal(data, &result)
			for i, r := range result.Results {
				fmt.Printf("[%d] %s (score: %.2f)\n", i+1, r.SourceFilename, r.Score)
				content := r.Content
				if len(content) > 200 {
					content = content[:200] + "..."
				}
				fmt.Printf("    %s\n\n", content)
			}
		}
		return nil
	},
}

var retrieveCmd = &cobra.Command{
	Use:   "retrieve <query>",
	Short: "Retrieve chunks grouped by source",
	Args:  cobra.MinimumNArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		topK, _ := cmd.Flags().GetInt("top-k")
		query := joinArgs(args)

		body := map[string]interface{}{"query": query, "top_k": topK}
		data, err := client.Post(fmt.Sprintf("/api/v1/notebooks/%s/retrieve", nbID), body)
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				Groups []struct {
					SourceFilename string  `json:"source_filename"`
					MaxScore       float64 `json:"max_score"`
					Chunks         []struct {
						Content string `json:"content"`
					} `json:"chunks"`
				} `json:"groups"`
			}
			json.Unmarshal(data, &result)
			for i, g := range result.Groups {
				fmt.Printf("[%d] %s (max score: %.2f, %d chunks)\n", i+1, g.SourceFilename, g.MaxScore, len(g.Chunks))
			}
		}
		return nil
	},
}

var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List sources or cards",
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		typeFilter, _ := cmd.Flags().GetString("type")
		data, err := client.Get(fmt.Sprintf("/api/v1/notebooks/%s/list?type_filter=%s", nbID, typeFilter))
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				Items []map[string]interface{} `json:"items"`
			}
			json.Unmarshal(data, &result)
			for _, item := range result.Items {
				fmt.Printf("%v\n", item)
			}
		}
		return nil
	},
}

func joinArgs(args []string) string {
	s := ""
	for i, a := range args {
		if i > 0 {
			s += " "
		}
		s += a
	}
	return s
}

func init() {
	searchCmd.Flags().String("nb", "", "Notebook ID (required)")
	searchCmd.MarkFlagRequired("nb")
	searchCmd.Flags().Int("top-k", 5, "Number of results")

	retrieveCmd.Flags().String("nb", "", "Notebook ID (required)")
	retrieveCmd.MarkFlagRequired("nb")
	retrieveCmd.Flags().Int("top-k", 5, "Number of source groups")

	listCmd.Flags().String("nb", "", "Notebook ID (required)")
	listCmd.MarkFlagRequired("nb")
	listCmd.Flags().String("type", "source", "Type: source or card")

	rootCmd.AddCommand(searchCmd, retrieveCmd, listCmd)
}

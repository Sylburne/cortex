package cmd

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

var ragCmd = &cobra.Command{
	Use:   "rag",
	Short: "Interactive RAG Q&A session",
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		nbID, _ := cmd.Flags().GetString("nb")
		provider, _ := cmd.Flags().GetString("provider")
		model, _ := cmd.Flags().GetString("model")

		// Create session
		body := map[string]string{
			"provider": provider,
			"model":    model,
		}
		data, err := client.Post(fmt.Sprintf("/api/v1/notebooks/%s/rag/sessions", nbID), body)
		if err != nil {
			return fmt.Errorf("failed to create session: %w", err)
		}

		var session struct {
			ID       string `json:"id"`
			Provider string `json:"provider"`
			Model    string `json:"model"`
		}
		json.Unmarshal(data, &session)
		fmt.Printf("RAG session started (%s / %s). Type /exit to quit.\n\n", session.Provider, session.Model)

		scanner := bufio.NewScanner(os.Stdin)
		for {
			fmt.Print("> ")
			if !scanner.Scan() {
				break
			}
			question := strings.TrimSpace(scanner.Text())
			if question == "" || question == "/exit" {
				break
			}

			msgBody := map[string]string{"content": question}
			msgData, err := client.Post(
				fmt.Sprintf("/api/v1/notebooks/%s/rag/sessions/%s/messages", nbID, session.ID),
				msgBody,
			)
			if err != nil {
				fmt.Printf("Error: %s\n\n", err)
				continue
			}

			var resp struct {
				Content   string `json:"content"`
				Citations []struct {
					SourceFilename string  `json:"source_filename"`
					Score          float64 `json:"score"`
				} `json:"citations"`
			}
			json.Unmarshal(msgData, &resp)
			fmt.Println(resp.Content)
			if len(resp.Citations) > 0 {
				fmt.Println("\nSources:")
				for _, c := range resp.Citations {
					fmt.Printf("  - %s (score: %.2f)\n", c.SourceFilename, c.Score)
				}
			}
			fmt.Println()
		}
		fmt.Println("Session ended.")
		return nil
	},
}

func init() {
	ragCmd.Flags().String("nb", "", "Notebook ID (required)")
	ragCmd.MarkFlagRequired("nb")
	ragCmd.Flags().String("provider", "", "LLM provider (openai/anthropic/ollama)")
	ragCmd.Flags().String("model", "", "Model name")
	rootCmd.AddCommand(ragCmd)
}

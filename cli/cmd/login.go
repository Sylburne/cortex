package cmd

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"github.com/qmind/cli/internal/auth"
	"github.com/spf13/cobra"
)

var loginCmd = &cobra.Command{
	Use:   "login",
	Short: "Log in to QMind",
	RunE: func(cmd *cobra.Command, args []string) error {
		apiKey, _ := cmd.Flags().GetString("api-key")
		url, _ := cmd.Flags().GetString("url")

		if apiKey == "" {
			fmt.Print("Enter API key: ")
			reader := bufio.NewReader(os.Stdin)
			apiKey, _ = reader.ReadString('\n')
			apiKey = strings.TrimSpace(apiKey)
		}
		if url == "" {
			url = "http://localhost:8000"
		}

		creds := auth.Credentials{APIKey: apiKey, APIUrl: url}
		if err := auth.Save(creds); err != nil {
			return fmt.Errorf("failed to save credentials: %w", err)
		}
		fmt.Println("Logged in successfully. Credentials saved to ~/.qmind-local/credentials.json")
		return nil
	},
}

func init() {
	loginCmd.Flags().String("api-key", "", "API key")
	loginCmd.Flags().String("url", "", "API URL (default: http://localhost:8000)")
	rootCmd.AddCommand(loginCmd)
}

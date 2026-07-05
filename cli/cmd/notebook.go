package cmd

import (
	"encoding/json"
	"fmt"

	"github.com/qmind/cli/internal/api"
	"github.com/qmind/cli/internal/auth"
	"github.com/qmind/cli/internal/output"
	"github.com/spf13/cobra"
)

var notebookCmd = &cobra.Command{
	Use:   "notebook",
	Short: "Manage notebooks",
}

var notebookListCmd = &cobra.Command{
	Use:   "list",
	Short: "List notebooks",
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		data, err := client.Get("/api/v1/notebooks")
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				Notebooks []struct {
					ID          string `json:"id"`
					Name        string `json:"name"`
					Description string `json:"description"`
				} `json:"notebooks"`
			}
			json.Unmarshal(data, &result)
			for _, nb := range result.Notebooks {
				fmt.Printf("%-40s %s\n", nb.ID, nb.Name)
			}
		}
		return nil
	},
}

var notebookCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a notebook",
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		name, _ := cmd.Flags().GetString("name")
		desc, _ := cmd.Flags().GetString("desc")
		body := map[string]string{"name": name, "description": desc}
		data, err := client.Post("/api/v1/notebooks", body)
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				ID   string `json:"id"`
				Name string `json:"name"`
			}
			json.Unmarshal(data, &result)
			fmt.Printf("Created notebook: %s (%s)\n", result.Name, result.ID)
		}
		return nil
	},
}

var notebookGetCmd = &cobra.Command{
	Use:   "get <id>",
	Short: "Get notebook details",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		data, err := client.Get("/api/v1/notebooks/" + args[0])
		if err != nil {
			return err
		}
		if output == "json" {
			var result map[string]interface{}
			json.Unmarshal(data, &result)
			output.JSON(result)
		} else {
			var result struct {
				ID          string `json:"id"`
				Name        string `json:"name"`
				Description string `json:"description"`
			}
			json.Unmarshal(data, &result)
			fmt.Printf("ID: %s\nName: %s\nDescription: %s\n", result.ID, result.Name, result.Description)
		}
		return nil
	},
}

var notebookDeleteCmd = &cobra.Command{
	Use:   "delete <id>",
	Short: "Delete a notebook",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		client, err := getClient()
		if err != nil {
			return err
		}
		_, err = client.Delete("/api/v1/notebooks/" + args[0])
		if err != nil {
			return err
		}
		fmt.Println("Notebook deleted.")
		return nil
	},
}

func init() {
	notebookCreateCmd.Flags().String("name", "", "Notebook name (required)")
	notebookCreateCmd.MarkFlagRequired("name")
	notebookCreateCmd.Flags().String("desc", "", "Description")

	notebookCmd.AddCommand(notebookListCmd, notebookCreateCmd, notebookGetCmd, notebookDeleteCmd)
	rootCmd.AddCommand(notebookCmd)
}

func getClient() (*api.Client, error) {
	creds, err := auth.Load()
	if err != nil {
		return nil, fmt.Errorf("not logged in. Run 'qmind login' first")
	}
	url := creds.APIUrl
	if apiURL != "" && apiURL != "http://localhost:8000" {
		url = apiURL
	}
	return api.NewClient(url, creds.APIKey), nil
}

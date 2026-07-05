package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	apiURL string
	output string
	verbose bool
)

var rootCmd = &cobra.Command{
	Use:   "qmind",
	Short: "QMind - Personal knowledge base CLI",
	Long:  `QMind is a CLI tool for managing knowledge bases with RAG, vector search, and multi-provider AI.`,
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)
	rootCmd.PersistentFlags().StringVar(&apiURL, "api-url", "http://localhost:8000", "Backend API URL")
	rootCmd.PersistentFlags().StringVarP(&output, "output", "o", "text", "Output format: text or json")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "Enable verbose logging")
	viper.BindPFlag("api_url", rootCmd.PersistentFlags().Lookup("api-url"))
}

func initConfig() {
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath("$HOME/.qmind-local")
	viper.AddConfigPath(".")
	viper.AutomaticEnv()
	viper.ReadInConfig()
}

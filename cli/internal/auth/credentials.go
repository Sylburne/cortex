package auth

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Credentials struct {
	APIKey string `json:"api_key"`
	APIUrl string `json:"api_url"`
}

func credPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".qmind-local", "credentials.json")
}

func Save(creds Credentials) error {
	dir := filepath.Dir(credPath())
	os.MkdirAll(dir, 0700)
	data, err := json.MarshalIndent(creds, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(credPath(), data, 0600)
}

func Load() (Credentials, error) {
	data, err := os.ReadFile(credPath())
	if err != nil {
		return Credentials{}, err
	}
	var creds Credentials
	err = json.Unmarshal(data, &creds)
	return creds, err
}

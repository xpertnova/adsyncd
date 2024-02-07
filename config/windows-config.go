//go:build windows

package config

type WindowsConfig struct {
	UserConfig          map[string]string `json:"userConfig"`
	GroupName           string            `json:"ADGroupName"`
	ActiveDirectoryName string            `json:"ADName"`
	DefaultPassword     string            `json:"defaultPassword"`
}

type Config struct {
	AzureADConfig AzureADConfig `json:"azure"`
	OSConfig      WindowsConfig `json:"os"`
	DaeomonConfig DaemonConfig  `json:"daemon"`
	Debug         bool
}

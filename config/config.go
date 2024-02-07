package config

type AzureADConfig struct {
	ClientId     string   `json:"clientId"`
	ClientSecret string   `json:"clientSecret"`
	AADGroupId   string   `json:"azureADGroupId"`
	AuthURL      string   `json:"authUrl"`
	IgnoreList   []string `json:"ignoreList"`
}

type DaemonConfig struct {
	SyncInterval      int    `json:"syncInterval"`
	CheckInterval     int    `json:"checkInterval"`
	LogBackupCount    int    `json:"logBackupCount"`
	LogFilePath       string `json:"logFilePath"`
	LogBackupMaxSize  int    `json:"logBackupMaxSize"`
	LogBackupMaxAge   int    `json:"logBackupMaxAge"`
	UseLogCompression bool   `json:"useLogCompression"`
}

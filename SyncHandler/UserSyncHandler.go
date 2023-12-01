package SyncHandler

import "xpertnova.de/adsyncd/AzureAD"

type Config struct {
}

type UserConfig map[string]string

type UserSyncHandler struct {
	config            Config
	blockedUsers      []string
	osAdmin           int
	domainAdmin       AzureAD.AzureADSyncHandler
	osUserGroupName   string
	defaultUserConfig UserConfig
}

func New(configFilePath string) {
	u := UserSyncHandler{Config{}, []string, 0, AzureADSyncHandler.New(), "", UserConfig{}}
	return u
}

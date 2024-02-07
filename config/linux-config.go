//go:build linux

package config

type LinuxConfig struct {
	UserConfig      map[string]string `json:"userConfig"`
	GroupConfig     map[string]string `json:"groupConfig"`
	GroupName       string            `json:"groupName"`
	DefaultPassword string            `json:"defaultPassword"`
	SystemFiles     LinuxSystemFiles  `json:"sysFiles"`
}

type LinuxSystemFiles struct {
	Passwd string `json:"passwd"`
	Shadow string `json:"shadow"`
	Group  string `json:"group"`
}

type Config struct {
	AzureADConfig AzureADConfig `json:"azure"`
	OSConfig      LinuxConfig   `json:"os"`
	DaeomonConfig DaemonConfig  `json:"daemon"`
	Debug         bool          `json:"debug"`
}

//go:build linux

package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"slices"
	"strconv"
	"syscall"
	"time"

	"github.com/xpertnova/adsyncd/azuread"
	config "github.com/xpertnova/adsyncd/config"
	"github.com/xpertnova/adsyncd/sysusers"
	"gopkg.in/natefinch/lumberjack.v2"
)

type processLockFile struct {
	*os.File
}

func (p processLockFile) Unlock() error {
	path := p.File.Name()
	if err := p.File.Close(); err != nil {
		return err
	}
	return os.Remove(path)
}

var (
	version     string
	buildTime   string
	versionHash string
	showVersion bool

	triggerSync  bool
	reloadConfig bool
	killRunning  bool

	logger *lumberjack.Logger

	ConfigFilePath string

	killChannel   chan os.Signal
	syncChannel   chan os.Signal
	reloadChannel chan os.Signal

	pidFilePath = "/var/run/adsyncd.pid"
)

func init() {
	flag.StringVar(&ConfigFilePath, "c", "./config.json", "Set the config file path")
	flag.BoolVar(&showVersion, "version", false, "Show version")
}

func main() {
	flag.Parse()
	args := os.Args[1:]
	if len(args) > 0 {
		switch args[0] {
		case "sync":
			triggerSync = true
		case "stop":
			killRunning = true
		case "reload":
			reloadConfig = true
		default:
			log.Panicf("Unknown command: %s", args[0])
		}
	}
	if showVersion {
		fmt.Printf("adsyncd for Linux %s\n", version)
		fmt.Printf("Source code version %s built at %s\n", versionHash, buildTime)
		os.Exit(0)
	} else if triggerSync {
		pid := getPIDFromFile()
		syscall.Kill(pid, syscall.SIGUSR1)
	} else if reloadConfig {
		pid := getPIDFromFile()
		syscall.Kill(pid, syscall.SIGUSR2)
	} else if killRunning {
		pid := getPIDFromFile()
		syscall.Kill(pid, syscall.SIGTERM)
	} else {
		//Declare context
		ctx := context.Background()
		ctx, cancel := context.WithCancel(ctx)
		defer cancel()

		Config := getConfig()

		//Initialize logging
		log.SetOutput(&lumberjack.Logger{
			Filename:   Config.DaeomonConfig.LogFilePath,
			MaxSize:    Config.DaeomonConfig.LogBackupMaxSize,
			MaxBackups: Config.DaeomonConfig.LogBackupCount,
			MaxAge:     Config.DaeomonConfig.LogBackupMaxAge,
			Compress:   Config.DaeomonConfig.UseLogCompression,
		})

		//Lock PID file
		pidFile, err := acquirePIDLock(pidFilePath)
		if err != nil {
			log.Fatalf("Could not lock PID file: %s", err)
		}
		defer func() {
			err := pidFile.Unlock()
			if err != nil {
				log.Fatalf("Could not remove PID lock file: %s\nPlease make sure that adsyncd was terminated correctly and remove the PID file at /var/run/adsyncd.log")
			}
		}()

		//Initialize signal channels
		//It is easier to handle the three cases as seperate channels
		//SIGINT / SIGTERM: Kill
		//SIGUSR1: Sync users
		//SIGUSR2: Reload config
		killChannel = make(chan os.Signal, 1)
		syncChannel = make(chan os.Signal, 1)
		reloadChannel = make(chan os.Signal, 1)

		signal.Notify(killChannel, syscall.SIGTERM, syscall.SIGINT)
		signal.Notify(syncChannel, syscall.SIGUSR1)
		signal.Notify(reloadChannel, syscall.SIGUSR2)

		//Setup the sync timer and "bind" it to the syncChannel
		go func() {
			for {
				select {
				case <-time.Tick(time.Duration(Config.DaeomonConfig.SyncInterval) * time.Second):
					syncChannel <- nil
				case <-killChannel:
					cancel()
					os.Exit(0)
				}
			}
		}()

		//Enter the main loop
		if err := run(ctx, &Config); err != nil {
			log.Fatalf("Fatal error occured: %s", err)
		}
	}
}

func getConfig() config.Config {
	//Read config file
	var cfg config.Config
	f, err := os.Open(ConfigFilePath)
	if err != nil {
		log.Fatalf("Config file not found in %s, exiting", ConfigFilePath)
	}
	defer f.Close()
	d := json.NewDecoder(f)
	err = d.Decode(&cfg)
	if err != nil {
		log.Fatalf("Cannot read config file: %s", err)
	}
	return cfg
}

func getPIDFromFile() int {
	f, err := os.ReadFile(pidFilePath)
	if err != nil {
		log.Panicf("Cannot read PID file at %s\nMake sure adsyncd is started and that you have sufficient permissions\n%+v", pidFilePath, err)
	}
	pid, err := strconv.Atoi(string(f))
	if err != nil {
		log.Panicf("PID in file %s seems to be invalid\nMake sure adsyncd is started and that you have sufficient permissions\n%+v", pidFilePath, err)
	}
	return pid
}

// Create a PID lock file to prevent multiple instances from running
// Adapted from sarumaj's solution in https://gist.github.com/davidnewhall/3627895a9fc8fa0affbd747183abca39?permalink_comment_id=4724043#gistcomment-4724043
func acquirePIDLock(pidFilePath string) (interface{ Unlock() error }, error) {
	if _, err := os.Stat(pidFilePath); !os.IsNotExist(err) {
		raw, err := os.ReadFile(pidFilePath)
		if err != nil {
			return nil, err
		}
		pid, err := strconv.Atoi(string(raw))
		if err != nil {
			return nil, err
		}
		if proc, err := os.FindProcess(int(pid)); err == nil && !errors.Is(proc.Signal(syscall.Signal(0)), os.ErrProcessDone) {
			return nil, errors.New(fmt.Sprintf("An adsyncd instance is already running under PID %s", pid))
		} else if err = os.Remove(pidFilePath); err != nil {
			return nil, err
		}
	}

	f, err := os.OpenFile(pidFilePath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, os.ModePerm)
	if err != nil {
		return nil, err
	}
	if _, err := f.Write([]byte(fmt.Sprint(os.Getpid()))); err != nil {
		return nil, err
	}

	return processLockFile{File: f}, nil
}

func run(ctx context.Context, c *config.Config) error {
	linuxAdmin, err := sysusers.New(&c.OSConfig, c.Debug)
	if err != nil {
		return err
	}
	azureClient, err := azuread.New(&c.AzureADConfig)
	if err != nil {
		return err
	}
	err = linuxAdmin.SyncGroups()
	if err != nil {
		log.Printf("[Daemon] Error creating system user group: %+v", err)
		return err
	}
	if !linuxAdmin.GroupExists(c.OSConfig.GroupName) {
		err = linuxAdmin.AddGroup(c.OSConfig.GroupName)
		if err != nil {
			return err
		}
	}
	for {
		select {
		case <-ctx.Done():
			return nil
		case <-syncChannel:
			syncUsers(linuxAdmin, azureClient, c)
		case <-reloadChannel:
			cfg := getConfig()
			linuxAdmin.Config = &cfg.OSConfig
			azureClient.Config = &cfg.AzureADConfig
		case <-killChannel:
			return nil
		}
	}
}

func syncUserLists(l *sysusers.LinuxSystemAdmin, a *azuread.AzureADSyncHandler) error {
	err := l.SyncUsers()
	if err != nil {
		return err
	}
	err = a.SyncUsers()
	if err != nil {
		return err
	}
	return nil
}

func syncUsers(l *sysusers.LinuxSystemAdmin, a *azuread.AzureADSyncHandler, c *config.Config) error {
	log.Println("[Daemon] Syncing users - Users removed from AzureAD will be removed from system")
	err := syncUserLists(l, a)
	if err != nil {
		log.Printf("[Daemon] Error syncing user lists: %+v", err)
	}
	linuxUsers := l.GetUsernameList()
	azureUsers := a.GetUsernameList()
	for _, user := range azureUsers {
		if !slices.Contains(linuxUsers, user.UserPrincipalName) {
			err := l.AddUser(sysusers.NewUser{Username: user.UserPrincipalName, DisplayName: user.DisplayName})
			if err != nil {
				log.Printf("[Daemon] Error creating user %s: %+v", user.UserPrincipalName, err)
				return err
			}
			err = l.SetUserPassword(user.UserPrincipalName, c.OSConfig.DefaultPassword)
			if err != nil {
				log.Printf("[Daemon] Error setting user password for %s: %+v", user.UserPrincipalName, err)
				return err
			}
		}
	}
	linuxSyncedUsers := l.GetUsersnamesInGroup(c.OSConfig.GroupName)
	if len(azureUsers) < len(linuxSyncedUsers) {
		log.Println("[Daemon] Detected imbalance in synced system users and Azure AD users. Deleting removed users.")
		for _, u := range linuxSyncedUsers {
			if !slices.ContainsFunc(azureUsers, func(au azuread.AzureADUser) bool {
				return au.UserPrincipalName == u
			}) {
				err := l.RemoveUser(u)
				if err != nil {
					log.Printf("[Daemon] Error removing user from system: %+v", err)
					return err
				}
			}
		}
	}
	return nil
}

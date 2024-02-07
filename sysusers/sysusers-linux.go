//go:build linux

package sysusers

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"slices"
	"strings"

	"golang.org/x/crypto/bcrypt"

	"github.com/xpertnova/adsyncd/config"
)

type LinuxSystemAdmin struct {
	groups map[string]*LinuxSystemGroup
	users  map[string]*LinuxSystemUser
	Config *config.LinuxConfig
	_DEBUG bool
}

func New(c *config.LinuxConfig, debug bool) (*LinuxSystemAdmin, error) {
	checkConfig(c)
	a := LinuxSystemAdmin{map[string]*LinuxSystemGroup{}, map[string]*LinuxSystemUser{}, c, debug}
	log.Printf("[LinuxAdmin] Initializing Linux user handler")
	if err := a.SyncUsers(); err != nil {
		return nil, err
	}
	if err := a.SyncGroups(); err != nil {
		return nil, err
	}
	return &a, nil
}

func (a *LinuxSystemAdmin) SyncUsers() error {
	log.Printf("Reading users from " + a.Config.SystemFiles.Passwd)
	users := a.users
	passwdFile, err := os.Open(a.Config.SystemFiles.Passwd)
	if err != nil {
		log.Printf("[LinuxAdmin] Error opening passwd file: %s", err)
		return err
	}
	defer passwdFile.Close()
	scanner := bufio.NewScanner(passwdFile)

	for scanner.Scan() {
		entry := scanner.Text()
		entries := strings.Split(entry, ":")
		user := &LinuxSystemUser{entries[0], entries[1] == "x", entries[2], entries[3], entries[4], entries[5], entries[6], a}
		users[entries[0]] = user
	}
	if err := scanner.Err(); err != nil {
		log.Printf("[LinuxAdmin] Error reading passwd file: %s", err)
		return err
	}
	for name, user := range users {
		if user == nil {
			delete(users, name)
		}
	}
	log.Printf("Detected %d users", len(users))
	a.users = users
	return nil
}

func (a *LinuxSystemAdmin) SyncGroups() error {
	log.Printf("Reading groups from %s", a.Config.SystemFiles.Group)
	groups := a.groups
	groupsFile, err := os.Open(a.Config.SystemFiles.Group)
	if err != nil {
		log.Printf("[LinuxAdmin] Error opening groups file: %s", err)
		return err
	}
	defer groupsFile.Close()
	scanner := bufio.NewScanner(groupsFile)

	for scanner.Scan() {
		entry := scanner.Text()
		if entry == "" || entry == "\n" {
			continue
		}
		entry = strings.ReplaceAll(entry, "\n", "")
		entries := strings.Split(entry, ":")
		group := &LinuxSystemGroup{entries[0], entries[2], strings.Split(entries[3], ",")}
		groups[entries[0]] = group
	}
	if err := scanner.Err(); err != nil {
		log.Printf("[LinuxAdmin] Error reading groups file: %s", err)
		return err
	}
	for name, group := range groups {
		if group == nil {
			delete(groups, name)
		}
	}
	a.groups = groups
	return nil
}

func (a *LinuxSystemAdmin) GetUsernameList() []string {
	a.SyncUsers()
	if a.users == nil {
		return nil
	}
	var usernames []string
	for username := range a.users {
		usernames = append(usernames, username)
	}
	return usernames
}

func (a *LinuxSystemAdmin) GetUsersnamesInGroup(groupname string) []string {
	if g, ok := a.groups[groupname]; ok {
		return g.members
	}
	return []string{}
}

func (a *LinuxSystemAdmin) UserExists(Username string) bool {
	return a.users[Username] != nil
}

func (a *LinuxSystemAdmin) GetUser(Username string) (*LinuxSystemUser, error) {
	if user, ok := a.users[Username]; ok {
		return user, nil
	}
	return nil, &UserNotExistingError{Username: Username, Msg: "User not found"}
}

func (a *LinuxSystemAdmin) AddUser(user NewUser) error {
	userConfig := a.Config.UserConfig
	log.Printf("Adding user %+v with config: %+v", user, userConfig)
	if a.UserExists(user.Username) {
		return &UserAlreadyExistsError{Username: user.Username, Msg: "User already exists"}
	}
	if a.GroupExists(user.Username) {
		if err := a.execCommand("groupdel " + user.Username); err != nil {
			log.Printf("[LinuxAdmin] Error deleting user group with same name as user: %s", err)
			return err
		}
	}
	command := "useradd "
	for option, param := range userConfig {
		//Replace $AD_USER_FULLNAME token to allow for GECOS setting in useradd command
		if param == "$AD_USER_FULLNAME" {
			param = user.DisplayName
		}
		command += option + " "
		if param != "" {
			command += param + " "
		}
	}
	command += user.Username
	if err := a.execCommand(command); err != nil {
		log.Printf("[LinuxAdmin] Error creating user: %s", err)
		return err
	}
	a.SyncUsers()
	return nil
}

func (a *LinuxSystemAdmin) RemoveUser(user string) error {
	a.SyncUsers()
	log.Printf("[LinuxAdmin] Removing user " + user)
	if !a.UserExists(user) {
		return &UserNotExistingError{Username: user, Msg: "User cannot be deleted because it doesn't exist"}
	}
	if err := a.execCommand("userdel -r " + user); err != nil {
		log.Printf("[LinuxAdmin] Error deleting user: %s", err)
		return err
	}
	if err := a.execCommand("groupdel " + user); err != nil {
		log.Printf("[LinuxAdmin] Error deleting group: %s", err)
		return err
	}
	return nil
}

func (a *LinuxSystemAdmin) SetUserPassword(user, password string) error {
	log.Printf("Setting password for user: %s", user)
	a.SyncUsers()
	if !a.UserExists(user) {
		return &UserNotExistingError{Username: user, Msg: "User doesn't exist"}
	}
	modifyPasswd := false
	passwdFile, err := os.OpenFile(a.Config.SystemFiles.Passwd, os.O_RDWR, 0)
	if err != nil {
		log.Printf("[LinuxAdmin] Error opening passwd file: %s", err)
		return err
	}
	defer passwdFile.Close()
	scanner := bufio.NewScanner(passwdFile)

	var lines []string
	for scanner.Scan() {
		entry := scanner.Text()
		entries := strings.Split(entry, ":")
		if entries[0] == user {
			if entries[1] != "x" {
				entries[1] = "x"
				entryString := ""
				for _, s := range entries {
					if s != "\n" {
						entryString += s + ":"
					} else {
						entryString += s
					}
				}
				modifyPasswd = true
				lines = append(lines, entryString)
				continue
			}
			if !modifyPasswd {
				break
			}
		}
		lines = append(lines, entry)
	}
	if err := scanner.Err(); err != nil {
		log.Printf("[LinuxAdmin] Error reading passwd file: %s", err)
		return err
	}

	if modifyPasswd {
		_, err = passwdFile.Seek(0, 0)
		if err != nil {
			log.Printf("[LinuxAdmin] Error seeking to the beginning of the file: %s", err)
			return err
		}
		if err := passwdFile.Truncate(0); err != nil {
			log.Printf("[LinuxAdmin] Error truncating the file: %s", err)
			return err
		}
		writer := bufio.NewWriter(passwdFile)
		for _, line := range lines {
			_, err := writer.WriteString(line)
			if err != nil {
				log.Printf("[LinuxAdmin] Error writing to passwd file: %s", err)
				return err
			}
		}
		if err := writer.Flush(); err != nil {
			log.Printf("[LinuxAdmin] Error flushing file: %s", err)
			return err
		}
	}

	salt, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		log.Printf("[LinuxAdmin] Error generating salt: %s", err)
		return err
	}
	saltString := string(salt)
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(password+saltString), bcrypt.DefaultCost)
	if err != nil {
		log.Printf("[LinuxAdmin] Error generating hashed password: %s", err)
		return err
	}
	hashedPwString := string(hashedPassword)

	shadowFile, err := os.OpenFile(a.Config.SystemFiles.Shadow, os.O_RDWR, 0)
	if err != nil {
		log.Printf("[LinuxAdmin] Error opening passwd file: %s", err)
		return err
	}
	defer shadowFile.Close()
	shadowScanner := bufio.NewScanner(shadowFile)

	var shadowLines []string
	for shadowScanner.Scan() {
		entry := shadowScanner.Text()
		entries := strings.Split(entry, ":")
		if entries[0] == user {
			entries[1] = hashedPwString
			entryString := ""
			for _, s := range entries {
				if s != "\n" {
					entryString += s + ":"
				} else {
					entryString += s
				}
			}
			shadowLines = append(shadowLines, entryString)
			continue
		}
		shadowLines = append(shadowLines, entry)
	}
	if err := shadowScanner.Err(); err != nil {
		log.Printf("[LinuxAdmin] Error reading shadow file: %s", err)
		return err
	}

	_, err = shadowFile.Seek(0, 0)
	if err != nil {
		log.Printf("[LinuxAdmin] Error seeking to the beginning of the file: %s", err)
		return err
	}
	if err := shadowFile.Truncate(0); err != nil {
		log.Printf("[LinuxAdmin] Error truncating the file: %s", err)
		return err
	}
	shadowWriter := bufio.NewWriter(shadowFile)
	for _, line := range shadowLines {
		_, err := shadowWriter.WriteString(line)
		if err != nil {
			log.Printf("Error writing to passwd file: %s", err)
			return err
		}
	}
	if err := shadowWriter.Flush(); err != nil {
		log.Printf("[LinuxAdmin] Error flushing file: %s", err)
		return err
	}
	return nil
}

func (a *LinuxSystemAdmin) GetGroupsForUsername(username string) []*LinuxSystemGroup {
	var groups []*LinuxSystemGroup
	for _, group := range a.groups {
		if slices.Contains(group.members, username) {
			groups = append(groups, group)
		}
	}
	return groups
}

func (a *LinuxSystemAdmin) AddGroup(groupname string) error {
	a.SyncGroups()
	log.Printf("[LinuxAdmin] Adding group %s with config %+v", groupname, a.Config.GroupConfig)
	if a.GroupExists(groupname) {
		err := GroupAlreadyExistsError{Msg: "Group with name " + groupname + " already exists", Groupname: groupname}
		return &err
	}
	command := "groupadd "
	for option, param := range a.Config.GroupConfig {
		command += option
		if param != "" {
			command += param
		}
	}
	a.execCommand(command)
	a.SyncGroups()
	return nil
}

func (a *LinuxSystemAdmin) GroupExists(groupname string) bool {
	if val, ok := a.groups[groupname]; ok {
		return val != nil
	}
	return false
}

func (a *LinuxSystemAdmin) execCommand(command string) error {
	if a._DEBUG {
		fmt.Print(command)
	} else {
		//Execute command
	}
	return nil
}

func checkConfig(c *config.LinuxConfig) {
	if c.GroupName == "" {
		log.Fatalf("[LinuxAdmin] Sync group name may not be empty")
	}
	if val, ok := c.UserConfig["-G"]; ok && val != "" {
		if !strings.Contains(val, c.GroupName) {
			log.Fatalf("[LinuxAdmin] Created users have to be added to sync group")
		}
	} else if val, ok := c.UserConfig["-g"]; ok && val != "" {
		if val != c.GroupName {
			log.Fatalf("[LinuxAdmin] Created users have to be added to sync group")
		}
	} else {
		log.Fatalf("[LinuxAdmin] User config parameter '-g' or '-G' missing")
	}
}

type LinuxSystemUser struct {
	Username    string
	hasPassword bool
	uid         string
	gid         string
	Gecos       string
	homeDir     string
	shell       string
	admin       *LinuxSystemAdmin
}

// Functions for additional scripting support
// Not implemented for now since they're barely used
func (u *LinuxSystemUser) SetPassword(passwordHash string) error {
	return nil
}

func (u *LinuxSystemUser) GetGroups() ([]string, error) {
	return nil, nil
}

func (u *LinuxSystemUser) GetUsername() string {
	return u.Username
}

func (u *LinuxSystemUser) Remove() error {
	return nil
}

func (u *LinuxSystemUser) AddToGroup(groupName string) error {
	return nil
}

type LinuxSystemGroup struct {
	Name    string
	gid     string
	members []string
}

//go:build linux

package LinuxUserAdmin

import (
	"bufio"
	"errors"
	"fmt"
	"log"
	"os"
	"slices"
	"strings"

	"golang.org/x/crypto/bcrypt"

	"xpertnova.de/adsyncd/SyncHandler"
	"xpertnova.de/adsyncd/SystemUserAdmin"
)

type LinuxSystemAdmin struct {
	groups         []LinuxSystemGroup
	users          []LinuxSystemUser
	passwdFilePath string
	shadowFilePath string
	groupFilePath  string
	_DEBUG         bool
}

func New(passwdFilePath, shadowFilePath, groupFilePath string, debug bool) (*LinuxSystemAdmin, error) {
	a := LinuxSystemAdmin{nil, nil, passwdFilePath, shadowFilePath, groupFilePath, debug}
	log.Printf("Initializing Linux user handler")
	if err := a.SyncUsers(); err != nil {
		return nil, err
	}
	if err := a.SyncGroups(); err != nil {
		return nil, err
	}
	return &a, nil
}

func (a *LinuxSystemAdmin) SyncUsers() error {
	log.Printf("Reading users from " + a.passwdFilePath)
	var users []LinuxSystemUser
	passwdFile, err := os.Open(a.passwdFilePath)
	if err != nil {
		log.Printf("Error opening passwd file: %s", err)
		return err
	}
	defer passwdFile.Close()
	scanner := bufio.NewScanner(passwdFile)

	for scanner.Scan() {
		entry := scanner.Text()
		entries := strings.Split(entry, ":")
		user := LinuxSystemUser{entries[0], entries[1] == "x", entries[2], entries[3], entries[4], entries[5], entries[6], a}
		users = append(users, user)
	}
	if err := scanner.Err(); err != nil {
		log.Printf("Error reading passwd file: %s", err)
		return err
	}
	log.Printf("Detected %d users", len(users))
	a.users = users
	return nil
}

func (a *LinuxSystemAdmin) SyncGroups() error {
	log.Printf("Reading groups from %s", a.groupFilePath)
	var groups []LinuxSystemGroup
	groupsFile, err := os.Open(a.groupFilePath)
	if err != nil {
		log.Printf("Error opening groups file: %s", err)
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
		group := LinuxSystemGroup{entries[0], entries[2], strings.Split(entries[3], ",")}
		groups = append(groups, group)
	}
	if err := scanner.Err(); err != nil {
		log.Printf("Error reading groups file: %s", err)
		return err
	}
	a.groups = groups
	return nil
}

func (a *LinuxSystemAdmin) GetUsernameList() ([]string, error) {
	a.SyncUsers()
	if a.users == nil {
		return nil, errors.New("no users found in system")
	}
	var usernames []string
	for _, user := range a.users {
		usernames = append(usernames, user.Username)
	}
	return usernames, nil
}

func (a *LinuxSystemAdmin) UserExists(Username string) bool {
	return slices.ContainsFunc(a.users, func(user LinuxSystemUser) bool {
		return user.Username == Username
	})
}

func (a *LinuxSystemAdmin) GetUser(Username string) (*LinuxSystemUser, error) {
	var user *LinuxSystemUser
	for i := range a.users {
		u := &a.users[i]
		if u.Username == Username {
			user = u
			break
		}
	}
	if user == nil {
		return nil, &SystemUserAdmin.UserNotExistingError{Username: Username, Msg: "User not found"}
	}
	return user, nil
}

func (a *LinuxSystemAdmin) AddUser(user LinuxSystemUser, config SyncHandler.UserConfig) error {
	a.SyncUsers()
	log.Printf("Adding user %s with config: %+v", user, config)
	if a.UserExists(user.Username) {
		return &SystemUserAdmin.UserAlreadyExistsError{Username: user.Username, Msg: "User already exists"}
	}
	if slices.ContainsFunc(a.groups, func(group LinuxSystemGroup) bool {
		return group.Name == user.Username
	}) {
		if err := a.execCommand("groupdel " + user.Username); err != nil {
			log.Printf("Error deleting user group with same name as user: %s", err)
			return err
		}
	}
	command := "useradd "
	for option, param := range config {
		//Replace $AD_USER_FULLNAME token to allow for GECOS setting in useradd command
		if param == "$AD_USER_FULLNAME" {
			param = user.Gecos
		}
		command += option + " "
		if param != "" {
			command += param + " "
		}
	}
	command += user.Username
	if err := a.execCommand(command); err != nil {
		log.Printf("Error creating user: %s", err)
		return err
	}
	a.SyncUsers()
	return nil
}

func (a *LinuxSystemAdmin) RemoveUser(user string) error {
	a.SyncUsers()
	log.Printf("Removing user " + user)
	if !a.UserExists(user) {
		return &SystemUserAdmin.UserNotExistingError{Username: user, Msg: "User cannot be deleted because it doesn't exist"}
	}
	if err := a.execCommand("userdel -r " + user); err != nil {
		log.Printf("Error deleting user: %s", err)
		return err
	}
	if err := a.execCommand("groupdel " + user); err != nil {
		log.Printf("Error deleting group: %s", err)
		return err
	}
	return nil
}

func (a *LinuxSystemAdmin) SetUserPassword(user, password string) error {
	log.Printf("Setting password for user: %s", user)
	a.SyncUsers()
	if !a.UserExists(user) {
		return &SystemUserAdmin.UserNotExistingError{Username: user, Msg: "User doesn't exist"}
	}
	modifyPasswd := false
	passwdFile, err := os.OpenFile(a.passwdFilePath, os.O_RDWR, 0)
	if err != nil {
		log.Printf("Error opening passwd file: %s", err)
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
		log.Printf("Error reading passwd file: %s", err)
		return err
	}

	if modifyPasswd {
		_, err = passwdFile.Seek(0, 0)
		if err != nil {
			log.Printf("Error seeking to the beginning of the file: %s", err)
			return err
		}
		if err := passwdFile.Truncate(0); err != nil {
			log.Printf("Error truncating the file: %s", err)
			return err
		}
		writer := bufio.NewWriter(passwdFile)
		for _, line := range lines {
			_, err := writer.WriteString(line)
			if err != nil {
				log.Printf("Error writing to passwd file: %s", err)
				return err
			}
		}
		if err := writer.Flush(); err != nil {
			log.Printf("Error flushing file: %s", err)
			return err
		}
	}

	salt, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		log.Printf("Error generating salt: %s", err)
		return err
	}
	saltString := string(salt)
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(password+saltString), bcrypt.DefaultCost)
	if err != nil {
		log.Printf("Error generating hashed password: %s", err)
		return err
	}
	hashedPwString := string(hashedPassword)

	shadowFile, err := os.OpenFile(a.shadowFilePath, os.O_RDWR, 0)
	if err != nil {
		log.Printf("Error opening passwd file: %s", err)
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
		log.Printf("Error reading shadow file: %s", err)
		return err
	}

	_, err = shadowFile.Seek(0, 0)
	if err != nil {
		log.Printf("Error seeking to the beginning of the file: %s", err)
		return err
	}
	if err := shadowFile.Truncate(0); err != nil {
		log.Printf("Error truncating the file: %s", err)
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
		log.Printf("Error flushing file: %s", err)
		return err
	}
	return nil
}

func (a *LinuxSystemAdmin) execCommand(command string) error {
	if a._DEBUG {
		fmt.Print(command)
	} else {
		//Execute command
	}
	return nil
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

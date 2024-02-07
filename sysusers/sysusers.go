package sysusers

import config "github.com/xpertnova/adsyncd/config"

type SystemUserAdmin interface {
	New(c *config.Config, debug bool) (*SystemUserAdmin, error)
	SyncUsers() error
	SyncGroups() error
	GetUsernameList() []string
	UserExists(Username string) bool
	GetUser(Username string) (*SystemUser, error)
	AddUser(user NewUser) error
	AddGroup(groupname string) error
	RemoveUser(user string) error
	SetUserPassword(user, password string) error
	GroupExists(groupname string) bool
	GetUsernamesInGroup(groupname string) []string
}

type SystemUser interface {
	SetPassword(passwordHash string) error
	GetGroups() ([]string, error)
	GetUsername() string
	Remove() error
	AddToGroup(groupName string) error
}

type UserNotExistingError struct {
	Username string
	Msg      string
}

func (e *UserNotExistingError) Error() string {
	return e.Msg
}

type UserAlreadyExistsError struct {
	Username string
	Msg      string
}

func (e *UserAlreadyExistsError) Error() string {
	return e.Msg
}

type GroupAlreadyExistsError struct {
	Groupname string
	Msg       string
}

func (e *GroupAlreadyExistsError) Error() string {
	return e.Msg
}

type NewUser struct {
	Username    string
	DisplayName string
}

package SystemUserAdmin

import "xpertnova.de/adsyncd/SyncHandler"

type SystemUserAdmin interface {
	New() (*SystemUserAdmin, error)
	SyncUsers() error
	GetUsernameList() ([]string, error)
	UserExists(userName string) bool
	GetUser(userName string) (SystemUser, error)
	AddUser(user SystemUser, config SyncHandler.UserConfig) error
	RemoveUser(user string) error
	SetUserPassword(user, password string) error
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

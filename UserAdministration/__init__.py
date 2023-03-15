"""
User Administration interface

Interface to add other sources of usernames in the future

Classes:
    UserAdministration
"""
class UserAdministration:
    """
    Interface to add other sources of usernames in the future

    Attributes
    ----------
    __users : list[str]
        List of users

    Methods
    -------
    syncUsers()
        Sync users with source
    getUsernameList()
        Returns list of usernames
    userExists(username)
        Check if user exists
    """
    __users = []
    __groups = []
    DEBUG = False
    def __init__(self):
        """
        Constructor
        """
        pass
    def syncUsers(self):
        """
        Sync users with source

        Returns
        -------
        None
        """
        pass
    def getUsernameList(self):
        """
        Returns list of usernames

        Returns
        -------
        list[Any]
            List of usernames or similar
        """
        pass
    def userExists(self, username):
        """
        Check if user exists

        Parameters
        ----------
        username : str
            Username

        Returns
        -------
        bool
            True if user exists
        """
        pass

    def addUser(self, username, config):
        """
        Add user to list

        Parameters
        ----------
        username : str
            Username

        Returns
        -------
        None
        """

class User:
    """
    Provides an interface for user defined hooks

    Attributes
    ----------
    _username : str
        Username
    __admin : SystemUserAdministration
        Active linux system user handler, private
    _properties : dict
        Properties as defined in the passwd file

    Methods
    -------
    setPassword(passwordHash)
        Set password
    getGroups()
        Returns list of groups user is in
    getUsername()
        Returns username
    remove()
        Remove user from system
    """
    def __init__(self, username, admin, properties):
        """
        Constructor

        Parameters
        ----------
        username : str
            Username
        admin : SystemUserAdministration
            Active linux system user handler
        properties : dict
            Properties of user as in passwd file
        """
        self._username = username
        self.__admin = admin
        self._properties = properties

    def setPassword(self, passwordHash):
        """
        Set password

        Parameters
        ----------
        passwordHash : str
            Hashed (!) password, use crypt to hash password
        """
        self.__admin.setUserPassword(self._username, passwordHash)
    def getGroups(self):
        """
        Returns list of groups user is in

        Returns
        -------
        list[str]
            List of groups
        """
        return self.__admin.getGroupsForUser(self._username)
    def getUsername(self):
        """
        Returns username

        Returns
        -------
        str
            username
        """
        return self._username
    def remove(self):
        """
        Remove user

        Returns
        -------
        None

        Raises
        ------
        UserNotExistingError
            User does not exist, use this class only for existing users
        """
        self.__admin.removeUser(self._username)
class UserNotExistingError(Exception):
    """
    Exception for when user does not exist

    Attributes
    ----------
    _userName : str
        Username of nonexistent user
    """
    _userName = ""

    def __init__(self, userName):
        """
        Constructor

        Parameters
        ----------
        userName : str
            Name of nonexistent user
        """
        super().__init__()
        print("User not existing: " + userName)


class UserAlreadyExistsError(Exception):
    """
    Exception for when user already exists

    Attributes
    ----------
    _userName : str
        Username of existing user
    """

    _userName = ""

    def __init__(self, userName):
        """
        Constructor

        Parameters
        ----------
        userName : str
            Name of existing user
        """
        super().__init__()
        print("User already exists: " + userName)


class GroupAlreadyExistsError(Exception):
    """
    Exception for when group already exists
    """
    def __init__(self, groupname):
        """
        Constructor

        Parameters
        ----------
        groupname : str
            Name of existing group
        """
        super().__init__()
        print("Group already exists: " + groupname)

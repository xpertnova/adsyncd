"""
Windows User Administration

Handles Windows user administration

Classes:
    SystemUserAdministration - Class to handle Linux user administration
    User - Provides an interface for user defined hooks
    UserNotExistingError - Exception for when user not exists
    UserAlreadyExistsError - Exception for when the user already exists
    GroupAlreadyExistsError - Exception for when group already exists
"""


from UserAdministration import UserAdministration, GroupAlreadyExistsError, UserNotExistingError, User, \
    UserAlreadyExistsError
import os
import logging
import crypt
import subprocess
class SystemUserAdministration(UserAdministration):
    """
    Class to handle Windows user administration

    Will create and delete users in sync with Azure AD users in a AD domain

    Attributes
    ----------
    _groups : list[str]
        Groups in system
    _DEBUG : bool
        Methods in this class will print commands instead of executing them if set to True

    Methods
    -------
    getUsernameList()
        Returns list of all usernames
    getGroupnameList()
        Returns list of all group names
    addUser(user, config={"-m": None})
        Adds a user to the system
    removeUser(username)
        Removes a user from the system
    setUserPassword(username, password)
        Sets a password for user
    getGroupsForUser(username)
        Get list of groups the user is in
    getUsersInGroup(groupname)
        Get list of users in group
    syncUsers()
        Read users from passwd file
    syncGroups()
        Read groups from group file
    addGroup(groupname, config={})
        Adds a group to the system
    """

    def __init__(self, DEBUG=False):
        """
        Constructor

        Parameters
        ----------
        passwdFile : str
            Path to passwd file, defaults to '/etc/passwd'
        shadowFile : str
            Path to shadow file, defaults to '/etc/shadow'
        groupFile : str
            Path to group file, defaults to '/etc/group'
        DEBUG : bool
            Methods in this class will print commands instead of executing them if set to True, defaults to False
        """
        super().__init__()
        self.DEBUG = DEBUG
        logging.info(
            "System user administration for Windows initialized")
        self.syncUsers()
        self.syncGroups()

    def getUsernameList(self):
        """
        Returns list of all usernames

        Returns
        -------
        list[str]
            List of usernames
        """
        self.syncUsers()
        usernames = []
        for u in self._users:
            usernames.append(u["username"])
        return usernames

    def getGroupnameList(self):
        """
        Returns list of all group names

        Returns
        -------
        list[str]
            List of group names
        """
        self.syncGroups()
        groupnames = []
        for g in self.__groups:
            groupnames.append(g["name"])
        return groupnames

    def addUser(self, user, config={}):
        """
        Adds a user to the system

        Parameters
        ----------
        user : list[str]
            User display name (GECOS) [0] and username [1] of user to be created
        config : dict
            Configuration for 'useradd' command. If an option needs no argument, use it as key and None or an empty string as value

        Returns
        -------
        None

        Raises
        ------
        UserAlreadyExistsError
            User is already existing and cannot be added
        """
        self.syncUsers()
        logging.info("Adding user " + user[1] + " with config %s", config)
        if user[1] in self.getUsernameList(): raise UserAlreadyExistsError(user[1])
        if user[1] in self.getGroupnameList():
            #A user group with that name exists, remove
            if self.DEBUG:
                print("groupdel " + user[1])
            else:
                os.system("groupdel " + user[1])

        #Composing command
        command = "useradd "
        for option in config:
            command = command + option + " "
            if config[option] or config[option] != "": command = command + config[option] + " "
        command = command + user[1]

        #Execute command
        if self.DEBUG:
            print(command)
        else:
            os.system(command)

        #Set GECOS string in passwd
        with open(self.__passwdFile, "r") as passwdFile:
            passwdData = passwdFile.readlines()
            for line in passwdData:
                passwdString = line.split(":")
                if passwdString[0] == user[1]:
                    passwdString[4] = user[0]
                    entryString = ""
                    for s in passwdString:
                        if not s.endswith("\n"):
                            entryString = entryString + s + ":"
                        else:
                            entryString = entryString + s
                    passwdData[passwdData.index(line)] = entryString
        with open(self.__passwdFile, "w") as passwdFile:
            passwdFile.writelines(passwdData)

        #Re-sync users and fetch userconfig for current user
        self.syncUsers()
        userconfig = ""

        #Execute post-user creation hook, defined in UserCreatedHooks.py
        for u in self._users:
            if u["username"] == user:
                userconfig = u
        try:
            from UserDefinedHooks import postUserCreationHook
            postUserCreationHook(User(user[1], self, userconfig))
        except Exception as e:
            logging.error("Execution of post user creation hook failed with: " + str(e))

    def removeUser(self, username):
        """
        Removes a user from the system

        Parameters
        ----------
        username : str
            Username of user to be removed

        Returns
        -------
        None

        Raises
        ------
        UserNotExistingError
            The user to be removed does not exist and cannot be removed
        """
        logging.info("Removing user " + username)
        if username not in self.getUsernameList(): raise UserNotExistingError(username)
        if self.DEBUG:
            print("userdel -r " + username)
            print("groupdel " + username)
        else:
            os.system("userdel -r " + username)
            os.system("groupdel " + username)

    def setUserPassword(self, username, password):
        """
        Sets a password for user

        Parameters
        ----------
        username : str
            Username
        password : str
            Hashed (!) password to be set, use crypt to hash password

        Returns
        -------
        None

        Raises
        ------
        UserNotExistingError
            User does not exist and their password cannot be set
        """
        logging.info("Setting new password for user " + username)
        modifyPasswd = False
        if not username in self.getUsernameList(): raise UserNotExistingError(username)

        #Check if passwd needs to be modified (if 'x' is set)
        with open(self.__passwdFile, "r") as passwdFile:
            passwdData = passwdFile.readlines()
            for line in passwdData:
                passwdString = line.split(":")
                if passwdString[0] == username:
                    if passwdString[1] != "x":
                        passwdString[1] = "x"
                        entryString = ""
                        for s in passwdString:
                            if not s == "\n":
                                entryString = entryString + s + ":"
                            else:
                                entryString = entryString + s
                        passwdData[passwdData.index(line)] = entryString
                        modifyPasswd = True
                        break
                    else:
                        break
        if modifyPasswd:
            #passwd needs to be re-written
            with open(self.__passwdFile, "w") as passwdFile:
                passwdFile.writelines(passwdData)
        #Set password in shadow
        with open(self.__shadowFile, "r") as shadowFile:
            data = shadowFile.readlines()
            for line in data:
                shadowString = line.split(":")
                if shadowString[0] == username:
                    shadowString[1] = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
                    entryString = ""
                    for s in shadowString:
                        if not s == "\n":
                            entryString = entryString + s + ":"
                        else:
                            entryString = entryString + s
                    data[data.index(line)] = entryString
                    break
        with open(self.__shadowFile, "w") as shadowFile:
            shadowFile.writelines(data)

    def getGroupsForUser(self, username):
        """
        Get list of groups the user is in
        If the specified user doesn't exist, an empty list is returned

        Parameters
        ----------
        username : str
            Username

        Returns
        -------
        list[str]
            List of group names
        """
        groups = []
        for g in self.__groups:
            if username in g["members"]:
                groups.append(g["name"])
        return groups

    def getUsersInGroup(self, groupname):
        """
        Get list of users in group
        If the specified group doesn't exist, an empty list is returned

        Parameters
        ----------
        groupname : str
            Name of group

        Returns
        -------
        list[str]
            List of usernames in group
        """
        for g in self.__groups:
            if groupname == g["name"]:
                return g["members"].split(",")
        return []

    def syncUsers(self):
        """
        Reads users from passwd file

        Returns
        -------
        None
        """
        logging.info("Reading users from " + self.__passwdFile)
        self._users = []
        with open(self.__passwdFile, "r") as passwdFile:
            for entry in passwdFile:
                if not entry == "":
                    passwdString = entry.split(":")
                    self._users.append({"username": passwdString[0],
                                        "hasPassword": (True if passwdString[1] == "x" else False),
                                        "uid": passwdString[2],
                                        "gid": passwdString[3],
                                        "gecos": passwdString[4],
                                        "homeDir": passwdString[5],
                                        "shell": passwdString[6]})
        logging.info("Detected " + str(len(self._users)) + " users")
    def syncGroups(self):
        """
        Read groups from group file

        Returns
        -------
        None
        """
        self.__groups = []
        logging.info("Reading groups from " + self.__groupFile)
        with open(self.__groupFile, "r") as groupFile:
            for entry in groupFile:
                if not (entry == "" or entry == "\n"):
                    entry = entry.replace("\n", "")
                    groupString = entry.split(":")
                    self.__groups.append({"name": groupString[0], "gid": groupString[2], "members": groupString[3]})
        logging.info(str(len(self.__groups)) + " groups detected")

    def addGroup(self, groupname, config={}):
        """
        Adds a group to the system

        Parameters
        ----------
        groupname : str
            Name of group to be created
        config : dict
            Configuration for groupadd, example: {"-f":None} for 'groupadd -f xxx', defaults to {}

        Returns
        -------
        None

        Raises
        ------
        GroupAlreadyExistsError
            Group already exists and cannot be created
        """
        self.syncGroups()
        logging.info("Adding group " + groupname + " with config %s", config)
        if groupname in self.getGroupnameList():
            logging.error("CRITICAL: Group already exists. Raising error.")
            raise GroupAlreadyExistsError(groupname)
        #Composing command
        command = "groupadd "
        for option in config:
            command = command + option + " "
            if config[option]: command = command + config[option] + " "
        command = command + groupname
        if self.DEBUG:
            print(command)
        else:
            logging.info("Adding group with command " + command)
            os.system(command)
        self.syncGroups()

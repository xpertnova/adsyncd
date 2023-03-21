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

import logging
import subprocess
import simplejson as json

class SystemUserAdministration(UserAdministration):
    """
    Class to handle Windows user administration

    Will create and delete users in sync with Azure AD users in a AD domain

    Attributes
    ----------
    _groups : list[str]
        Groups in system
    _users : list[dict{str:str}]
        Users in system
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

    def __init__(self, DEBUG=False, RemovePrincipalAffix=False):
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
        self._RemovePrincipalAffix = RemovePrincipalAffix
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

        #Composing command
        command = "New-ADUser -UserPrincipalName " + user[1] + " -DisplayName \"" + user[0] + " "
        for option in config:
            command = command + option + " "
            if config[option] or config[option] != "": command = command + config[option] + " "

        #Execute command
        if self.DEBUG:
            print(command)
        else:
            subprocess.run(
                ["powershell", "-Command", command])

        #Re-sync users and fetch userconfig for current user
        self.syncUsers()
        userconfig = ""

        #Execute post-user creation hook, defined in UserCreatedHooks.py
        for u in self._users:
            if u["Username"] == user:
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
        command = "Get-ADUser -Filter 'UserPrincipalName -eq \"" + username + "\"' | Remove-ADUser -Confirm:$false"
        if self.DEBUG:
            print(command)
        else:
            subprocess.run(
                ["powershell", "-Command", command])

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
        if not (username in self.getUsernameList()): raise UserNotExistingError(username)
        logging.info("Setting new password for user " + username)
        command = "Get-ADUser -Filter 'UserPrincipalName -eq \"" + username + \
                  "\"Set-ADAccountPassword -Reset -NewPassword (ConvertTo-SecureString -AsPlainText \"" + password + \
                  "\" -Force)"

        if self.DEBUG:
            print(command)
        else:
            subprocess.run(
                ["powershell", "-Command", command])

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
        return_array = []
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-ADPrincipalGroupMembership " + username +
             " | Select-Object name | ConvertTo-Json"],
            capture_output=True)
        groups = json.loads(result)
        for group in groups:
            return_array.append(group["name"])
        return return_array

        return return_array

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
                return_array = []
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-ADGroupMember " + groupname +
                     " | Get-ADUser | Select-Object UserPrincipalName | ConvertTo-Json"],
                    capture_output=True)
                users = json.loads(result)
                for user in users:
                    return_array.append(user["UserPrincipalName"])
                return return_array
        return []

    def syncUsers(self):
        """
        Reads users from passwd file

        Returns
        -------
        None
        """
        logging.info("Reading users from PowerShell command line")
        self._users = []
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-ADUser -Filter * | Select-Object UserPrincipalName, Enabled, Name | ConvertTo-Json"],
            capture_output=True)
        users = json.loads(result)
        if isinstance(users, list):
            for user in users:
                self._users.append({"Username": user["UserPrincipalName"],
                                    "Enabled": user["Enabled"],
                                    "Name": user["Name"]})
        else:
            self._users.append({"Username": users["UserPrincipalName"],
                                "Enabled": users["Enabled"],
                                "Name": users["Name"]})
        logging.info("Detected " + str(len(self._users)) + " users")
    def syncGroups(self):
        """
        Read AD groups from PowerShell

        Returns
        -------
        None
        """
        result = subprocess.run(
            ["powershell", "-Command", "Get-ADGroup -Filter * | Select-Object Name | ConvertTo-Json"],
            capture_output=True)
        groups = json.loads(result)
        self.__groups = []
        if isinstance(groups, list):
            for group in groups:
                self.__groups.append({"name": group["Name"], "members": []})
        else:
            self.__groups.append({"name": groups["Name"], "members": []})


    def addGroup(self, groupname, config=None):
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
        if config is None:
            config = {"GroupCategory": "Security", "GroupScope": "Global", "Description": "Created by adsyncd"}
        self.syncGroups()
        logging.info("Adding group " + groupname + " with config %s", config)
        if groupname in self.getGroupnameList():
            logging.error("CRITICAL: Group already exists. Raising error.")
            raise GroupAlreadyExistsError(groupname)
        #Composing command
        command = "New-ADGroup "
        for option in config:
            command = command + "-" + option + " "
            if config[option]: command = command + config[option] + " "
        command = command + "-Name " + groupname
        if self.DEBUG:
            print(command)
        else:
            logging.info("Adding group with command " + command)
            subprocess.run(["powershell", "-Command", command])
        self.syncGroups()
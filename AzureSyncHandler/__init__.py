"""
Azure AD User Synchronization Handler

This is "where the magic happens". This component is responsible for syncing Azure AD users with your Linux machine.

Classes:
    AzureSyncHandler - Class to handle user synchronization
    UserGroupNotInConfigError - Exception when the user group is not in the standard user config
    InvalidUserConfigError - Exception when the user config is invalid

"""

import configparser
import simplejson as json
from LinuxUsers import SystemUserAdministration, UserNotExistingError, UserAlreadyExistsError
from AzureAD import DomainUserAdministration
import logging

class AzureSyncHandler:
    """
    This class handles user synchronization

    Attributes
    ----------
    _config : configparser.ConfigParser
        Config parsed from config.cfg file
    _blockedUsers : list[str]
        Users in ignore list
    _linuxAdmin : LinuxUsers.SystemUserAdministration
        Linux user administration handler
    _domainAdmin : AzureAD.DomainUserAdministration
        Domain user synchronization handler
    _linuxUserGroupName : str
        Name of the Linux user group for Azure AD user
    _standardUserConfig : dict{str:str}
        Default config for 'useradd'

    Methods
    -------
    syncUsers()
        Synchronize users - creates/deletes Linux users for users in Azure AD
    syncUserLists()
        Syncs the lists of Linux and Domain users
    """
    _config = None
    _blockedUsers = []
    _linuxAdmin = None
    _domainAdmin = None
    _linuxUserGroupName = "azuread"
    _standardUserConfig = {}

    def __init__(self, configFile="./config.cfg"):
        """
        Constructor
        Define all relevant parameters in your config file and pass a path to it as parameter
        Defaults to ./config.cfg for config file path

        Parameters
        ----------
        configFile : str
            Path to config file

        Raises
        ------
            UserGroupNotInConfigError
                User group must be contained in user default config
            InvalidUserConfigError
                User default config is invalid
        """
        logging.info("Initializing sync handler")

        #Read config
        config = configparser.ConfigParser()
        config.read(configFile)
        self._config = config
        self._blockedUsers = config["Users"]["blockedPrincipals"].split(", ")
        self._domainAdmin = DomainUserAdministration(config["Azure"]["clientId"], config["Azure"]["clientSecret"], self._blockedUsers)
        linuxAdminConfig = {}

        #Set system file paths
        if config.has_option("Linux", "passwdFile"): linuxAdminConfig["passwdFile"] = config["Linux"]["passwdFile"]
        if config.has_option("Linux", "shadowFile"): linuxAdminConfig["shadowFile"] = config["Linux"]["shadowFile"]
        if config.has_option("Linux", "groupFile"): linuxAdminConfig["groupFile"] = config["Linux"]["groupFile"]

        #Initialize Linux user handler and check if config is valid (only partially)
        self._linuxAdmin = SystemUserAdministration(**linuxAdminConfig)
        if config.has_option("Linux", "azureGroupName"): self._linuxUserGroupName = config["Linux"]["azureGroupName"]
        if config.has_option("Linux", "standardUserConfig"): self._standardUserConfig = json.loads(config["Linux"]["standardUserConfig"])
        else: self._standardUserConfig = {"-m": None, "-g": self._linuxUserGroupName}
        if ("-g" in self._standardUserConfig and self._standardUserConfig["-g"] != self._linuxUserGroupName) or ("-G" in self._standardUserConfig and (self._linuxUserGroupName not in self._standardUserConfig["-G"])): raise UserGroupNotInConfigError
        if "-g" in self._standardUserConfig and "-G" in self._standardUserConfig: raise InvalidUserConfigError
        logging.info("Sync handler initialized")

    def syncUserLists(self):
        """
        Syncs the lists of Linux and Domain users

        Returns
        -------
        None
        """
        self._linuxAdmin.syncUsers()
        self._domainAdmin.syncUsers()

    def syncUsers(self):
        """
        Synchronize users - creates/deletes Linux users for users in Azure AD

        Returns
        -------
        None
        """
        logging.info("Syncing users - users not in AzureAD will be removed from system")
        azureUsers = self._domainAdmin.getUsernameList()
        linuxUsers = self._linuxAdmin.getUsernameList()
        #Check if user group exists
        if self._linuxUserGroupName not in self._linuxAdmin.getGroupnameList():
            try:
                self._linuxAdmin.addGroup(self._linuxUserGroupName)
            except:
                logging.error("Failed to create standard user group")

        #Create Linux user for every Azure AD principal
        for u in azureUsers:
            if u[1] not in linuxUsers:
                try:
                    self._linuxAdmin.addUser(u, config=self._standardUserConfig)
                    self._linuxAdmin.setUserPassword(u[1], self._config["Linux"]["standardPassword"])
                except UserNotExistingError:
                    logging.error("A user under this name does not exist. Please check if user creation is successful manually")
                except UserAlreadyExistsError:
                    logging.error("A user already exists under this name. Please make sure that the standard user grop name in config is correct")
        #Get all linux users
        azureadUsers = self._linuxAdmin.getUsersInGroup(self._linuxUserGroupName)

        #Check if user is to be deleted and delete
        if len(azureadUsers) != len(self._linuxAdmin.getUsersInGroup((self._linuxUserGroupName))):
            logging.info("Detected imbalance in Linux and Azure AD users. Deleting user not in Azure AD")
            for u in azureadUsers:
                if u not in azureUsers:
                    try:
                        self._linuxAdmin.removeUser(u)
                    except UserNotExistingError:
                        logging.error("Deleting a user was attempted, but the user couldn't be found")
        #Re-sync Linux users
        self._linuxAdmin.syncUsers()

class UserGroupNotInConfigError(Exception):
    """
    This is an exception for when the user group name specified in config is not in the default user config
    The user config must contain -g <groupname> or -G ...,<groupname>
    """
    def __init__(self):
        """
        Initializes super constructor
        """
        super().__init__()

class InvalidUserConfigError(Exception):
    """
    This is an exception for when the user config is invalid
    """
    def __init__(self):
        """
        Initializes super constructor
        """
        super().__init__()
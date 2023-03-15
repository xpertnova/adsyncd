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
from AzureAD import DomainUserAdministration
import logging

from UserAdministration import UserNotExistingError, UserAlreadyExistsError


class AzureSyncHandler:
    """
    This class handles user synchronization

    Attributes
    ----------
    __config : configparser.ConfigParser
        Config parsed from config.cfg file
    __blockedUsers : list[str]
        Users in ignore list
    __userAdmin : LinuxUsers.SystemUserAdministration
        Linux user administration handler
    __domainAdmin : AzureAD.DomainUserAdministration
        Domain user synchronization handler
    __systemUserGroupName : str
        Name of the Linux user group for Azure AD user
    __standardUserConfig : dict{str:str}
        Default config for 'useradd'

    Methods
    -------
    syncUsers()
        Synchronize users - creates/deletes Linux users for users in Azure AD
    syncUserLists()
        Syncs the lists of Linux and Domain users
    """
    __config = None
    __blockedUsers = []
    __systemAdmin = None
    __domainAdmin = None
    __systemUserGroupName = "azuread"
    __standardUserConfig = {}

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
        self.__config = config
        self.__blockedUsers = config["Users"]["blockedPrincipals"].split(", ")
        self.__domainAdmin = DomainUserAdministration(config["Azure"]["clientId"], config["Azure"]["clientSecret"],
                                                      self.__blockedUsers)
        if config.has_option("Windows"):
            if config.has_option("Linux"): raise Exception("Config file must not contain both Windows and Linux sections")
            from WindowsUsers import SystemUserAdministration
            self.__systemAdmin = SystemUserAdministration()
            if config.has_option("Windows", "azureGroupName"): self.__systemUserGroupName = config["Linux"][
                "azureGroupName"]
            if config.has_option("Windows", "standardUserConfig"):
                self.__standardUserConfig = json.loads(config["Windows"]["standardUserConfig"])
            else:
                self.__standardUserConfig = {"-m": None, "-g": self.__systemUserGroupName}

        else:
            from LinuxUsers import SystemUserAdministration
            linuxAdminConfig = {}

            #Set system file paths
            if config.has_option("Linux", "passwdFile"): linuxAdminConfig["passwdFile"] = config["Linux"]["passwdFile"]
            if config.has_option("Linux", "shadowFile"): linuxAdminConfig["shadowFile"] = config["Linux"]["shadowFile"]
            if config.has_option("Linux", "groupFile"): linuxAdminConfig["groupFile"] = config["Linux"]["groupFile"]

            #Initialize Linux user handler and check if config is valid (only partially)
            self.__systemAdmin = SystemUserAdministration(**linuxAdminConfig)
            if config.has_option("Linux", "azureGroupName"): self.__systemUserGroupName = config["Linux"]["azureGroupName"]
            if config.has_option("Linux", "standardUserConfig"): self.__standardUserConfig = json.loads(config["Linux"]["standardUserConfig"])
            else: self.__standardUserConfig = {"-m": None, "-g": self.__systemUserGroupName}
            if ("-g" in self.__standardUserConfig and self.__standardUserConfig["-g"] != self.__systemUserGroupName) or ("-G" in self.__standardUserConfig and (self.__systemUserGroupName not in self.__standardUserConfig["-G"])): raise UserGroupNotInConfigError
            if "-g" in self.__standardUserConfig and "-G" in self.__standardUserConfig: raise InvalidUserConfigError

        logging.info("Sync handler initialized")

    def syncUserLists(self):
        """
        Syncs the lists of Linux and Domain users

        Returns
        -------
        None
        """
        self.__systemAdmin.syncUsers()
        self.__domainAdmin.syncUsers()

    def syncUsers(self):
        """
        Synchronize users - creates/deletes system users for users in Azure AD

        Returns
        -------
        None
        """
        logging.info("Syncing users - users not in AzureAD will be removed from system")
        azureUsers = self.__domainAdmin.getUsernameList()
        systemUsers = self.__systemAdmin.getUsernameList()
        #Check if user group exists
        if self.__systemUserGroupName not in self.__systemAdmin.getGroupnameList():
            try:
                self.__systemAdmin.addGroup(self.__systemUserGroupName)
            except:
                logging.error("Failed to create standard user group")

        #Create system user for every Azure AD principal
        for u in azureUsers:
            if u[1] not in systemUsers:
                try:
                    self.__systemAdmin.addUser(u, config=self.__standardUserConfig)
                    self.__systemAdmin.setUserPassword(u[1], self.__config["Linux"]["standardPassword"])
                except UserNotExistingError:
                    logging.error("A user under this name does not exist. Please check if user creation is successful manually")
                except UserAlreadyExistsError:
                    logging.error("A user already exists under this name. Please make sure that the standard user grop name in config is correct")
        #Get all linux users
        systemAzureUsers = self.__systemAdmin.getUsersInGroup(self.__systemUserGroupName)

        #Check if user is to be deleted and delete
        if len(systemAzureUsers) != len(azureUsers):
            logging.info("Detected imbalance in Linux and Azure AD users. Deleting user not in Azure AD")
            domainPrincipals = []
            for u in azureUsers:
                domainPrincipals.append(u[1])
            for u in systemAzureUsers:
                if u not in domainPrincipals:
                    try:
                        self.__systemAdmin.removeUser(u)
                    except UserNotExistingError:
                        logging.error("Deleting a user was attempted, but the user couldn't be found")
        #Re-sync users
        self.__systemAdmin.syncUsers()

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
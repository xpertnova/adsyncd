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
    __systemAdmin : UserAdministration.UserAdministration
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
    __standardPassword = ""
    __systemType = ""

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
        if config.has_section("Windows"):
            logging.info("Initializing Windows user handler")
            if config.has_section("Linux"):
                logging.error("Config file must not contain both Windows and Linux sections")
                raise Exception("Config file must not contain both Windows and Linux sections")
            from WindowsUsers import SystemUserAdministration
            self.__systemType = "Windows"
            self.__systemAdmin = SystemUserAdministration()
            if config.has_option("Windows", "azureGroupName"):
                self.__systemUserGroupName = config["Windows"]["azureGroupName"]
            if config.has_option("Windows", "standardUserConfig"):
                self.__standardUserConfig = json.loads(config["Windows"]["standardUserConfig"])
            else:
                self.__standardUserConfig = {"CannotChangePassword": "$true", "PasswordNeverExpires": "$true", "Enabled": "$true", "ChangePasswordAtLogon": "$false", "UserCannotChangePassword": "$true"}
            if config.has_option("Windows", "standardPassword"):
                self.__standardPassword = config["Windows"]["standardPassword"]
            else:
                raise Exception("Standard password must be set in config file")
        else:
            logging.info("Initializing Linux user handler")
            from LinuxUsers import SystemUserAdministration
            self.__systemType = "Linux"
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
            if config.has_option("Linux", "standardPassword"):
                self.__standardPassword = config["Windows"]["standardPassword"]
            else:
                raise Exception("Standard password must be set in config file")

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
                    if self.__systemType == "Linux": self.__systemAdmin.addUser(u, self.__standardPassword, config=self.__standardUserConfig)
                    else: self.__systemAdmin.addUser(u, self.__standardPassword, self.__systemUserGroupName, config=self.__standardUserConfig)
                except UserNotExistingError:
                    logging.error("A user under this name does not exist. Please check if user creation is successful manually")
                except UserAlreadyExistsError:
                    logging.error("A user already exists under this name. Please make sure that the standard user grop name in config is correct")
        #Get all system users
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
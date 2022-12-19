import configparser
import simplejson as json
from LinuxUsers import SystemUserAdministration, UserNotExistingError, UserAlreadyExistsError
from AzureAD import DomainUserAdministration
import logging

class AzureSyncHandler:
    _config = None
    _blockedUsers = []
    _linuxAdmin = None
    _domainAdmin = None
    _linuxUserGroupName = "azuread"
    _standardUserConfig = {}

    def __init__(self, configFile="./config.cfg"):
        logging.info("Initializing sync handler")
        config = configparser.ConfigParser()
        config.read(configFile)
        self._config = config
        self._blockedUsers = config["Users"]["blockedPrincipals"].split(", ")
        self._domainAdmin = DomainUserAdministration(config["Azure"]["clientId"], config["Azure"]["clientSecret"], self._blockedUsers)
        linuxAdminConfig = {}
        if config.has_option("Linux", "passwdFile"): linuxAdminConfig["passwdFile"] = config["Linux"]["passwdFile"]
        if config.has_option("Linux", "shadowFile"): linuxAdminConfig["shadowFile"] = config["Linux"]["shadowFile"]
        if config.has_option("Linux", "groupFile"): linuxAdminConfig["groupFile"] = config["Linux"]["groupFile"]
        self._linuxAdmin = SystemUserAdministration(**linuxAdminConfig)
        if config.has_option("Linux", "azureGroupName"): self._linuxUserGroupName = config["Linux"]["azureGroupName"]
        if config.has_option("Linux", "standardUserConfig"): self._standardUserConfig = json.loads(config["Linux"]["standardUserConfig"])
        else: self._standardUserConfig = {"-m": None, "-g": self._linuxUserGroupName}
        if ("-g" in self._standardUserConfig and self._standardUserConfig["-g"] != self._linuxUserGroupName) or ("-G" in self._standardUserConfig and (self._linuxUserGroupName not in self._standardUserConfig["-G"])): raise UserGroupNotInConfigError
        if "-g" in self._standardUserConfig and "-G" in self._standardUserConfig: raise InvalidUserConfigError
        logging.info("Sync handler initialized")
    def syncUserLists(self):
        self._linuxAdmin.syncUsers()
        self._domainAdmin.syncUsers()

    def syncUsers(self):
        logging.info("Syncing users - users not in AzureAD will be removed from system")
        azureUsers = self._domainAdmin.getUsernameList()
        linuxUsers = self._linuxAdmin.getUsernameList()
        if self._linuxUserGroupName not in self._linuxAdmin.getGroupnameList():
            try:
                self._linuxAdmin.addGroup(self._linuxUserGroupName)
            except:
                logging.error("Failed to create standard user group")
        for u in azureUsers:
            if u[1] not in linuxUsers:
                try:
                    self._linuxAdmin.addUser(u, config=self._standardUserConfig)
                    self._linuxAdmin.setUserPassword(u[1], self._config["Linux"]["standardPassword"])
                except UserNotExistingError:
                    logging.error("A user under this name does not exist. Please check if user creation is successful manually")
                except UserAlreadyExistsError:
                    logging.error("A user already exists under this name. Please make sure that the standard user grop name in config is correct")
        azureadUsers = self._linuxAdmin.getUsersInGroup(self._linuxUserGroupName)
        if len(azureadUsers) != len(self._linuxAdmin.getUsersInGroup((self._linuxUserGroupName))):
            logging.info("Detected imbalance in Linux and Azure AD users. Deleting user not in Azure AD")
            for u in azureadUsers:
                if u not in azureUsers:
                    try:
                        self._linuxAdmin.removeUser(u)
                    except UserNotExistingError:
                        logging.error("Deleting a user was attempted, but the user couldn't be found")
        self._linuxAdmin.syncUsers()

class UserGroupNotInConfigError(Exception):
    def __init__(self):
        super().__init__()

class InvalidUserConfigError(Exception):
    def __init__(self):
        super().__init__()
import configparser
import simplejson as json
from LinuxUsers import SystemUserAdministration
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
        logging.basicConfig(filename="adsyncd.log", filemode="w", format="%(asctime)s-%(process)d--%(levelname)s-%(message)s", level=logging.INFO)
        logging.info("Initializing")
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

    def syncUserLists(self):
        self._linuxAdmin.syncUsers()
        self._domainAdmin.syncUsers()

    def syncUsers(self):
        logging.info("Syncing users - users not in AzureAD will be removed from system")
        azureUsers = self._domainAdmin.getUsernameList()
        linuxUsers = self._linuxAdmin.getUsernameList()
        if self._linuxUserGroupName not in self._linuxAdmin.getGroupnameList():
            self._linuxAdmin.addGroup(self._linuxUserGroupName)

        for u in azureUsers:
            if u not in linuxUsers:
                self._linuxAdmin.addUser(u, config=self._standardUserConfig)

        azureadUsers = self._linuxAdmin.getUsersInGroup(self._linuxUserGroupName)
        print(azureadUsers)
        for u in azureadUsers:
            if u not in azureUsers:
                self._linuxAdmin.removeUser(u)

class UserGroupNotInConfigError(Exception):
    def __init__(self):
        super().__init__()

class InvalidUserConfigError(Exception):
    def __init__(self):
        super().__init__()

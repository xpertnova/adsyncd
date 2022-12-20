from UserAdministration import UserAdministration
import os
import logging
import crypt
from UserDefinedHooks import postUserCreationHook
class SystemUserAdministration(UserAdministration):
    _groups = []
    _passwdFile = ""
    _shadowFile = ""
    _groupFile = ""
    _DEBUG = False

    def __init__(self, passwdFile="/etc/passwd", shadowFile="/etc/shadow", groupFile="/etc/group", DEBUG=False):
        super().__init__()
        self._passwdFile = passwdFile
        self._shadowFile = shadowFile
        self._groupFile = groupFile
        self._DEBUG = DEBUG
        logging.info(
            "System user administration initialized with passwd file " + self._passwdFile + ", shadow file " + self._shadowFile + " and group file " + self._groupFile)
        self.syncUsers()
        self.syncGroups()

    def getUsernameList(self):
        usernames = []
        for u in self._users:
            usernames.append(u["username"])
        return usernames

    def getGroupnameList(self):
        groupnames = []
        for g in self._groups:
            groupnames.append(g["name"])
        return groupnames

    def addUser(self, user, config={"-m": None}):  #throws UserAlreadyExistsError
        self.syncUsers()
        logging.info("Adding user " + user[1] + " with config %s", config)
        if user[1] in self.getUsernameList(): raise UserAlreadyExistsError(user[1])
        if user[1] in self.getGroupnameList(): #a user group with that name exists, remove
            if self._DEBUG:
                print("groupdel " + user[1])
            else:
                os.system("groupdel " + user[1])
        command = "useradd "
        for option in config:
            command = command + option + " "
            if config[option] or config[option] != "": command = command + config[option] + " "
        command = command + user[1]
        if self._DEBUG:
            print(command)
        else:
            os.system(command)
        with open(self._passwdFile, "r") as passwdFile:
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
        with open(self._passwdFile, "w") as passwdFile:
            passwdFile.writelines(passwdData)
        self.syncUsers()
        userconfig = ""
        for u in self._users:
            if u["username"] == user:
                userconfig = u
        postUserCreationHook(User(user, self, userconfig))

    def removeUser(self, username):
        logging.info("Removing user " + username)
        if username not in self.getUsernameList(): raise UserNotExistingError(username)
        if self._DEBUG:
            print("userdel -r " + username)
        else:
            os.system("userdel -r " + username)
            os.system("groupdel " + username)

    def setUserPassword(self, username, password):  # throws UserNotExistingError
        logging.info("Setting new password for user " + username)
        modifyPasswd = False
        if not username in self.getUsernameList(): raise UserNotExistingError(username)
        with open(self._passwdFile, "r") as passwdFile:
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
            with open(self._passwdFile, "w") as passwdFile:
                passwdFile.writelines(passwdData)
        with open(self._shadowFile, "r") as shadowFile:
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
        with open(self._shadowFile, "w") as shadowFile:
            shadowFile.writelines(data)

    def getGroupsForUser(self, username):
        groups = []
        for g in self._groups:
            if username in g["members"]:
                groups.append(g["name"])
        return groups

    def getUsersInGroup(self, groupname):
        for g in self._groups:
            if groupname == g["name"]:
                return g["members"].split(",")
        return None

    def syncUsers(self):
        logging.info("Reading users from " + self._passwdFile)
        self._users = []
        with open(self._passwdFile, "r") as passwdFile:
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
        self._groups = []
        logging.info("Reading groups from " + self._groupFile)
        with open(self._groupFile, "r") as groupFile:
            for entry in groupFile:
                if not (entry == "" or entry == "\n"):
                    groupString = entry.split(":")
                    self._groups.append({"name": groupString[0], "gid": groupString[2], "members": groupString[3]})
        logging.info(str(len(self._groups)) + " groups detected")

    def addGroup(self, groupname, config={}): #throws GroupAlreadyExistsError
        self.syncGroups()
        logging.info("Adding group " + groupname + " with config %s", config)
        if groupname in self.getGroupnameList():
            logging.error("CRITICAL: Group already exists. Raising error.")
            raise GroupAlreadyExistsError(groupname)
        command = "groupadd "
        for option in config:
            command = command + option + " "
            if config[option]: command = command + config[option] + " "
        command = command + groupname
        if self._DEBUG:
            print(command)
        else:
            logging.info("Adding group with command " + command)
            os.system(command)
        self.syncGroups()


class User:
    def __init__(self, username, admin, properties):
        self._username = username
        self._admin = admin
        self._properties = properties

    def setPassword(self, passwordHash):
        self._admin.setUserPassword(self._username, passwordHash)
    def getGroups(self):
        return self._admin.getGroupsForUser(self._username)
    def getUsername(self):
        return self._username
    def remove(self):
        _admin.removeUser(self._username)
class UserNotExistingError(Exception):
    _userName = ""

    def __init__(self, userName):
        super().__init__()
        print("User not existing: " + userName)


class UserAlreadyExistsError(Exception):
    _userName = ""

    def __init__(self, userName):
        super().__init__()
        print("User already exists: " + userName)


class GroupAlreadyExistsError(Exception):
    def __init__(self, groupname):
        super().__init__()
        print("Group already exists: " + groupname)

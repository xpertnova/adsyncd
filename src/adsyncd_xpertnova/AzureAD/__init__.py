import requests

from UserAdministration import UserAdministration

import logging


class DomainUserAdministration(UserAdministration):
    _clientId = ""
    _clientSecret = ""
    _token = ""
    _ignoreList = []

    def __init__(self, clientId, clientSecret, ignoreList=[]):
        super().__init__()
        self._clientId = clientId
        self._clientSecret = clientSecret
        self._ignoreList = ignoreList
        self.getApiToken()
        self.syncUsers()

    def getApiToken(self):
        logging.info("Getting API token")
        url = 'https://login.microsoftonline.com/xpertnovade.onmicrosoft.com/oauth2/v2.0/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self._clientId,
            'scope': 'https://graph.microsoft.com/.default',
            'client_secret': self._clientSecret
        }
        r = requests.post(url, data=data)
        self._token = r.json().get('access_token')
        logging.info("Token retrieved")

    def syncUsers(self):
        logging.info("Getting users from Azure AD")
        url = 'https://graph.microsoft.com/v1.0/users'
        headers = {
            'Content-Type': 'application\json',
            'Authorization': 'Bearer {}'.format(self._token)
        }
        r = requests.get(url, headers=headers)
        result = r.json()
        userJson = result["value"]
        users = []
        for u in userJson:
            if not u["userPrincipalName"] in self._ignoreList: users.append([u["displayName"], u["userPrincipalName"]])
        self._users = users

    def getUsernameList(self):
        self.syncUsers()
        users = []
        for u in self._users:
            users.append(u[1])
        return users

    def setIgnoreList(self, ignoreList):
        self._ignoreList = ignoreList

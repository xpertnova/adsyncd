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
    _users : list[str]
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
    _users = []
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
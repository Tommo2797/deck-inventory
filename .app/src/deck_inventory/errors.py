class UserFacingError(Exception):
    """Errore da mostrare all'utente, con messaggio in italiano."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class SettingsError(UserFacingError):
    pass


class NoDecksError(UserFacingError):
    pass


class BinderPrivateError(UserFacingError):
    pass


class BinderNetworkError(UserFacingError):
    pass


class SiteChangedError(UserFacingError):
    pass


class BrowserUnavailableError(UserFacingError):
    pass


class EmptyBinderError(UserFacingError):
    pass

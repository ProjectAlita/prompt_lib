class PromptInaccessableError(Exception):
    "Raised when prompt in project for which user doesn't have permission"

    def __init__(self, message):
        self.message = message


class PromptDoesntExist(Exception):
    "Raised when prompt doesn't exist"
    def __init__(self, message):
        self.message = message

class PromptAlreadyInCollectionError(Exception):
    "Raised when prompt is already in collection"
    def __init__(self, message):
        self.message = message


class NotFound(Exception):
    "Raised when nothing found by the query when it was required"
    def __def__(self, message):
        self.message = message
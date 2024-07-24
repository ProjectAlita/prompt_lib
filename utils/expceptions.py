class NotFound(Exception):
    "Raised when nothing found by the query when it was required"
    def __def__(self, message):
        self.message = message

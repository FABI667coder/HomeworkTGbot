class Statu200Error(Exception):
    def __init__(self, text):
        self.text = text


class RequestAPIError(Exception):
    def __init__(self, text):
        self.text = text


class JSONDecorError(Exception):
    def __init__(self, text):
        self.text = text


class HWStatusError(Exception):
    def __init__(self, text):
        self.text = text


class ResponseError(Exception):
    def __init__(self, text):
        self.text = text

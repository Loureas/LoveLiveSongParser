class Progress:

    def __init__(self):
        self.__progress_string_length = 0

    def print_progress(self, string: str):
        if not self.__progress_string_length:
            print(string + '\r', end='')
        else:
            print(' ' * self.__progress_string_length + '\r' + string + '\r', end='')
        self.__progress_string_length = len(string)

    def print_last_progress(self, string: str):
        if not self.__progress_string_length:
            print(string)
        else:
            print(' ' * self.__progress_string_length + '\r' + string)
        self.__progress_string_length = 0


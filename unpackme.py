import requests


class UnpackMeClientLoginInfo:
    def __init__(self, url=None, login=None, password=None):
        if url is None:
            url = "http://api.unpackme.shadosoft-tm.com/"
        if login is None:
            login = "djmaxeditor"
        if password is None:
            password = "djmaxeditor"

        self._url = url
        self._login = login
        self._password = password


class UnpackMeClient:
    def __init__(self, login_info=None):
        if login_info is None:
            login_info = UnpackMeClientLoginInfo()

        self._login_info = login_info

        self._url = self._login_info._url
        self._login = self._login_info._login
        self._password = self._login_info._password

        self._token = None

    def set_token(self, token):
        self._token = token

    def get_token(self):
        return self._token

    def authenticate(self, login=None, password=None):
        if login is None:
            login = self._login
        if password is None:
            password = self._password
        url = requests.compat.urljoin(self._url, "/auth")
        response = requests.post(url, data={"login": login, "password": password})
        response.raise_for_status()
        response_body = response.json()
        token = response_body["token"]
        self.set_token(token)
        return response_body

    def get_available_commands(self):
        token = self.get_token()
        assert token is not None
        url = requests.compat.urljoin(self._url, "/command/available")
        response = requests.get(url, headers={"Token": token})
        response.raise_for_status()
        response_body = response.json()
        return response_body

    def create_task_from_command_id(self, command_id, file):
        token = self.get_token()
        assert token is not None
        url = requests.compat.urljoin(self._url, f"/task/create/{command_id}")
        response = requests.post(
            url,
            headers={"Token": token},
            files={"file": ("test", file)},
        )
        response.raise_for_status()
        response_body = response.json()
        return response_body

    def get_task_by_id(self, task_id):
        token = self.get_token()
        assert token is not None
        url = requests.compat.urljoin(self._url, f"/task/{task_id}")
        response = requests.get(url, headers={"Token": token})
        response.raise_for_status()
        response_body = response.json()
        return response_body

    def download_task(self, task_id):
        token = self.get_token()
        assert token is not None
        url = requests.compat.urljoin(self._url, f"/task/{task_id}/download")
        response = requests.get(url, headers={"Token": token})
        response.raise_for_status()
        return response

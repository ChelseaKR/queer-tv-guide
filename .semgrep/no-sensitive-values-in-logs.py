import logging

logger = logging.getLogger(__name__)
api_key = "x"
token = "x"
user_email = "x"
count = 3
url = "https://example.test/"


def log(message: str) -> None:
    pass


class Client:
    def log(self, message: str) -> None:
        pass

    def run(self) -> None:
        # ruleid: no-sensitive-values-in-logs-python
        self.log(f"retrying with {token}")
        # ok: no-sensitive-values-in-logs-python
        self.log(f"network error on {url}; retry {count}")


# ruleid: no-sensitive-values-in-logs-python
print(api_key)
# ruleid: no-sensitive-values-in-logs-python
print(f"key is {api_key}")
# ruleid: no-sensitive-values-in-logs-python
log(f"user {user_email} signed in")
# ruleid: no-sensitive-values-in-logs-python
logger.info("auth %s", token)
# ok: no-sensitive-values-in-logs-python
log(f"shows: {count} fetched this run")
# ok: no-sensitive-values-in-logs-python
print(f"ok: {url} still grants reuse")
# ok: no-sensitive-values-in-logs-python
logger.info("fetched %d", count)
tokens: list[str] = []
# ok: no-sensitive-values-in-logs-python
tokens.append(token)

from enum import Enum


class CredicarroEnvironment(str, Enum):
    STAGING = "staging"
    PRODUCTION = "production"


_BASE_URLS = {
    CredicarroEnvironment.STAGING: "https://api.staging.credicarro.com.br/integration/",
    CredicarroEnvironment.PRODUCTION: "https://api.credicarro.com.br/integration/",
}


def environment_base_url(environment: CredicarroEnvironment) -> str:
    return _BASE_URLS[environment]

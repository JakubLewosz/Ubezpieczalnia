from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = "Dane zmienił inny pracownik. Odśwież widok i ponów zmianę."


def exception_handler(exc, context):
    return drf_exception_handler(exc, context)

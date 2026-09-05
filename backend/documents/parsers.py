"""Keep invalid original filenames from being silently cleaned by multipart parsing."""

from django.conf import settings
from django.http.multipartparser import MultiPartParser as DjangoMultiPartParser, MultiPartParserError
from rest_framework.exceptions import ParseError
from rest_framework.parsers import DataAndFiles, MultiPartParser

from exports.text import ExportValidationError, validate_xlsx_text


class OriginalNameMultipartParser(DjangoMultiPartParser):
    def sanitize_file_name(self, file_name):
        name = file_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        try:
            validate_xlsx_text(name, "Nazwa pliku")
        except ExportValidationError as error:
            raise ParseError(str(error)) from None
        if len(name) > 255:
            raise ParseError("Nazwa pliku przekracza 255 znaków. Skróć ją jawnie przed uploadem.")
        return None if name in {"", ".", ".."} else name


class DocumentMultipartParser(MultiPartParser):
    def parse(self, stream, media_type=None, parser_context=None):
        context = parser_context or {}
        request = context["request"]
        meta = request.META.copy()
        meta["CONTENT_TYPE"] = media_type
        try:
            parser = OriginalNameMultipartParser(meta, stream, request.upload_handlers,
                                                 context.get("encoding", settings.DEFAULT_CHARSET))
            data, files = parser.parse()
            return DataAndFiles(data, files)
        except MultiPartParserError:
            # Do not log a raw multipart header/name supplied by the client.
            raise ParseError("Nieprawidłowa struktura przesłanego pliku.") from None

"""OCR gate errors."""


class OCRGateError(RuntimeError):
    pass


class OCRAdapterUnavailable(OCRGateError):
    pass


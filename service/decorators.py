import logging

_logger = logging.getLogger(__name__)


def with_logger(cls):
    attr_name = "_logger"
    cls_name = cls.__qualname__
    setattr(cls, attr_name, logging.getLogger(cls_name))
    return cls

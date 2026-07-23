"""Module-level singleton state mirroring week1_baseline/ruby/06_the_logger's
`module Boukensha; def self.config; @config ||= Config.new; end; ... end`.
Lives here rather than boukensha/__init__.py for Python import-order
reasons -- see docs/plans/python_port/06_the_logger.

Ruby's bang/question-mark method names (debug!, debug?, quiet!, quiet?,
loud!) have no valid Python identifier equivalent -- dropped the same way
every other Ruby bang method has been (see backends/base.py's
validate_model, ported from validate_model!).
"""
from .config import Config

_config = None
_debug = False
_quiet = False


def config():
    global _config
    if _config is None:
        _config = Config()
    return _config


def enable_debug():
    global _debug
    _debug = True


def is_debug():
    return _debug


def enable_quiet():
    global _quiet
    _quiet = True


def disable_quiet():
    global _quiet
    _quiet = False


def is_quiet():
    return _quiet

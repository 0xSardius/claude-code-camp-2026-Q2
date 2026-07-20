"""Port of week1_baseline/ruby/00_config/lib/boukensha.rb -- aggregates the
package's public surface, mirroring what `require "boukensha"` makes
available in Ruby (Config, plus Tasks::Player and, transitively, Tasks::Base).
"""
from .config import Config
from .tasks.base import Base
from .tasks.player import Player

__all__ = ["Config", "Base", "Player"]

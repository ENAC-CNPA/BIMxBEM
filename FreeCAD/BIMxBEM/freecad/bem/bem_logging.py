# coding: utf8
"""This module contains common preconfigured logger to be optionnally used in each module.

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import io
import logging

LOG_FORMAT = "{levelname} {asctime} {funcName}-{message}"
LOG_STREAM = io.StringIO()
logging.basicConfig(
    stream=LOG_STREAM, level=logging.WARNING, format=LOG_FORMAT, style="{"
)
logger = logging.getLogger()

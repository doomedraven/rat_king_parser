#!/usr/bin/env python3
#
# config_normalization.py
#
# Authors: doomedraven/jeFF0Falltrades
#
# Provides a utility class for parsing field names and values of various types
# from raw RAT config data
#
# MIT License
#
# Copyright (c) 2024 Jeff Archer
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from typing import Any

normalized_keys = {
    "Hosts": ("HOSTS", "Hosts", "ServerIp", "hardcodedhosts", "PasteUrl"),
    "Ports": ("Port", "Ports", "ServerPort"),
    "Mutex": ("MTX", "MUTEX", "Mutex"),
    "Version": ("VERSION", "Version"),
    "Key": ("Key", "key", "EncryptionKey", "ENCRYPTIONKEY"),
    "Group": ("Group", "Groub", "GroupTag", "TAG"),
}


# Normalizes config keys/values for easier mapping
def check_key_n_value(key: str, value: Any) -> tuple[str, Any]:
    key_normalized = key.replace("_", "")
    for k, v in normalized_keys.items():
        if key_normalized in v:
            key = k
            break

    if (
        key in ("Hosts", "Ports")
        and isinstance(value, str)
        and value not in ("null", "false")
    ):
        splitter = "," if "," in value else ";"
        value = list(filter(None, value.split(splitter)))

    return key, value

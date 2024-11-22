#!/usr/bin/env python3
#
# config_decryptor_aes_ecb.py
#
# Author: jeFF0Falltrades
#
# Provides a custom AES decryptor for RAT payloads utilizing ECB mode
#
# Example Hash: d5028e10a756f2df677f32ebde105d7de8df37e253c431837c8f810260f4428e
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
from base64 import b64decode
from hashlib import md5
import logging
from re import DOTALL, compile, search

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.modes import ECB
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.primitives.ciphers.algorithms import AES

try:
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
except ImportError:
    # from cryptography.hazmat.primitives.ciphers.algorithms import AES
    # To be deprecated in 48, moved in 43
    # https://cryptography.io/en/latest/hazmat/decrepit/ciphers/

    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES

from ...config_parser_exception import ConfigParserException
from ..data_utils import bytes_to_int, decode_bytes
from ..dotnetpe_payload import DotNetPEPayload
from .config_decryptor import ConfigDecryptor, IncompatibleDecryptorException

logger = logging.getLogger(__name__)

"""
# ToDo this detects AES
re_config_crypt_aes = (
    rb"(\x08|\x07)"
    rb"\x20(\x80\x00|\x00\x01)\x00\x00"  # 128 or 256 bits
    rb"\x6f...\x0a"
    rb"(\x08|\x07)"
    rb"\x20\x80\x00\x00\x00"
    rb"\x6f...\x0a"
    rb"(\x08|\x07)"
    rb"(.)"
)
"""

class ConfigDecryptor3DES(ConfigDecryptor):
    # MD5 hash pattern used to detect AES key
    _PATTERN_MD5_HASH = compile(rb"\x7e(.{3}\x04)\x28.{3}\x06\x6f", DOTALL)
    _PATTERN_HARDCODED_KEY = compile(rb"\x00\x72(.{3}\x70)\x0A\x28.{4}", DOTALL)
    # Detect AES vs 3DES
    _IS_3DES = compile(rb"(\x28|\x73).{3}\x0A\x13\x04\x11\x04", DOTALL)
    # Patterns for identifying AES metadata
    _IS_AES = compile(b"[\x06-\x09]\x20(.{4})\x6f.{4}[\x06-\x09]\x20(.{4})\x6f.{4}[\x06-\x09](.)\x6f.{4}", DOTALL)

    def __init__(self, payload: DotNetPEPayload) -> None:
        super().__init__(payload)

        self.is_AES = search(self._IS_AES, self._payload.data)
        self.is_3DES = search(self._IS_3DES, self._payload.data)

        try:
            self._key_rva = self._get_key_rva()
        except Exception as e:
            raise IncompatibleDecryptorException(e)

    # Given ciphertext, creates a Cipher object with the AES/3DES key and decrypts
    # the ciphertext
    def _decrypt(self, ciphertext: bytes) -> bytes:
        if self.is_3DES:
            algo = TripleDES(self.key)
            block_size = TripleDES.block_size
        elif self.is_AES:
            algo = AES(self.key)
            block_size
        else:
            raise("Not identified crypto")
        algo_cipher = Cipher(algo, ECB(), backend=default_backend())
        decryptor = algo_cipher.decryptor()
        # Use a PKCS7 unpadder to remove padding from decrypted value
        # https://cryptography.io/en/latest/hazmat/primitives/padding/
        unpadder = PKCS7(block_size).unpadder()

        try:
            padded_text = decryptor.update(ciphertext) + decryptor.finalize()
            try:
                unpadded_text = unpadder.update(padded_text) + unpadder.finalize()
            except ValueError:
                # Might be not padded
                return None
        except Exception as e:
            raise ConfigParserException(f"Error decrypting ciphertext {ciphertext} with key {self.key.hex()}: {e}")

        logger.debug(f"Decryption result: {unpadded_text}")
        return unpadded_text

    # Decrypts encrypted config values with the provided cipher data
    def decrypt_encrypted_strings(self, encrypted_strings):  # dict[str, str]):  -> dict[str, str]:
        logger.debug("Decrypting encrypted strings...")
        if not self.key:
            try:
                raw_key_field = self._payload.field_name_from_rva(self._key_rva)
                self.key = self._derive_key(encrypted_strings[raw_key_field])
            except Exception as e:
                raise ConfigParserException(f"Failed to derive AES/3DES key: {e}")

        decrypted_config_strings = {}
        for k, v in encrypted_strings.items():
            # Leave empty strings as they are
            if len(v) == 0:
                logger.debug(f"Key: {k}, Value: {v}")
                decrypted_config_strings[k] = v
                continue

            # Check if base64-encoded string
            b64_exception = False
            try:
                decoded_val = b64decode(v)
            except Exception:
                b64_exception = True
            # If it was not base64-encoded, leave the value as it is
            if b64_exception:
                logger.debug(f"Key: {k}, Value: {v}")
                decrypted_config_strings[k] = v
                continue

            ciphertext = decoded_val
            result, last_exc = None, None
            try:
                result = decode_bytes(self._decrypt(ciphertext))
            except ConfigParserException as e:
                last_exc = e

            if result is None:
                logger.debug(f"Decryption failed for item {v}: {last_exc}")
                result = v

            logger.debug(f"Key: {k}, Value: {result}")
            decrypted_config_strings[k] = result

        logger.debug("Successfully decrypted strings")
        return decrypted_config_strings

    # Given the raw bytes that will become the key value, derives the AES/3DES key
    def _derive_key(self, key_unhashed: str) -> bytes:
        # Generate the MD5 hash
        md5_hash = md5()
        md5_hash.update(key_unhashed.encode("utf-8"))
        md5_digest = md5_hash.digest()

        # Key is a 32-byte(AES not 3DES) value made up of the MD5 hash overlaying itself,
        # tailed with one null byte
        if self.is_AES:
            key = md5_digest[:15] + md5_digest[:16] + b"\x00"
        elif self.is_3DES:
            key = md5_digest
        # Key is a 32-byte value made up of the MD5 hash overlaying itself,
        # tailed with one null byte
        # key = md5_digest + md5_digest[:8]
        logger.debug(f"Key derived: {key}")
        return key

    # Extracts the AES/3DES key RVA from the payload
    def _get_key_rva(self) -> int:
        logger.debug("Extracting AES/3Des key value...")
        key_hit = search(self._PATTERN_MD5_HASH, self._payload.data)
        # Hardcoded key in function. Getting MdToken
        hardcoded = False
        if not key_hit:
            key_hit = search(self._PATTERN_HARDCODED_KEY, self._payload.data)
            if key_hit:
                hardcoded = True
        if not key_hit:
            raise ConfigParserException("Could not find AES/3DES key pattern")

        if not hardcoded:
            key_rva = bytes_to_int(key_hit.groups()[0])
            logger.debug(f"AES/3DES key RVA: {hex(key_rva)}")
            key_rva = self._payload.field_name_from_rva(key_rva)
        else:
            key_mdtoken = key_hit.groups()[0]
            if key_mdtoken:
                self.key = self._payload.get_string_from_mdtoken(key_mdtoken)
                self.key = self._derive_key(self.key)
                key_rva = self.key

        return key_rva
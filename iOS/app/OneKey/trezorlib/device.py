# This file is part of the Trezor project.
#
# Copyright (C) 2012-2019 SatoshiLabs and contributors
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the License along with this library.
# If not, see <https://www.gnu.org/licenses/lgpl-3.0.html>.

import os
import time

from . import messages
from .exceptions import Cancelled
from .tools import expect, session

RECOVERY_BACK = "\x08"  # backspace character, sent literally


@expect(messages.Success, field="message")
def apply_settings(
        client,
        label=None,
        language=None,
        use_passphrase=None,
        homescreen=None,
        auto_lock_delay_ms=None,
        display_rotation=None,
        passphrase_always_on_device: bool = None,
        fastpay_pin: bool = None,
        use_ble: bool = None,
        use_se: bool = None,
        is_bixinapp: bool = None,
        fastpay_confirm: bool = None,
        fastpay_money_limit: int = None,
        fastpay_times: int = None,
        safety_checks=None,
):
    settings = messages.ApplySettings(
        label=label,
        language=language,
        use_passphrase=use_passphrase,
        homescreen=homescreen,
        passphrase_always_on_device=passphrase_always_on_device,
        auto_lock_delay_ms=auto_lock_delay_ms,
        display_rotation=display_rotation,
        use_ble=use_ble,
        use_se=use_se,
        is_bixinapp=is_bixinapp,
        fastpay_pin=fastpay_pin,
        fastpay_confirm=fastpay_confirm,
        fastpay_money_limit=fastpay_money_limit,
        fastpay_times=fastpay_times,
        safety_checks=safety_checks,
    )

    out = client.call(settings)
    client.init_device()  # Reload Features
    return out


@expect(messages.Success, field="message")
def apply_flags(client, flags):
    out = client.call(messages.ApplyFlags(flags=flags))
    client.init_device()  # Reload Features
    return out


@expect(messages.Success, field="message")
def change_pin(client, remove=False):
    ret = client.call(messages.ChangePin(remove=remove))
    client.init_device()  # Re-read features
    return ret


@expect(messages.Success, field="message")
def change_wipe_code(client, remove=False):
    ret = client.call(messages.ChangeWipeCode(remove=remove))
    client.init_device()  # Re-read features
    return ret


@expect(messages.Success, field="message")
def sd_protect(client, operation):
    ret = client.call(messages.SdProtect(operation=operation))
    client.init_device()
    return ret


@expect(messages.Success, field="message")
def wipe(client):
    ret = client.call(messages.WipeDevice())
    client.init_device()
    return ret


@expect(messages.Success, field="message")
def reboot(client):
    ret = client.call(messages.BixinReboot())
    return ret


def recover(
        client,
        word_count=24,
        passphrase_protection=False,
        pin_protection=True,
        label=None,
        language="en-US",
        input_callback=None,
        type=messages.RecoveryDeviceType.ScrambledWords,
        dry_run=False,
        u2f_counter=None,
):
    if client.features.model == "1" and input_callback is None:
        raise RuntimeError("Input callback required for Trezor One")

    if word_count not in (12, 18, 24):
        raise ValueError("Invalid word count. Use 12/18/24")

    if client.features.initialized and not dry_run:
        raise RuntimeError(
            "Device already initialized. Call device.wipe() and try again."
        )

    if u2f_counter is None:
        u2f_counter = int(time.time())

    msg = messages.RecoveryDevice(
        word_count=word_count, enforce_wordlist=True, type=type, dry_run=dry_run
    )

    if not dry_run:
        # set additional parameters
        msg.passphrase_protection = passphrase_protection
        msg.pin_protection = pin_protection
        msg.label = label
        msg.language = language
        msg.u2f_counter = u2f_counter

    res = client.call(msg)

    while isinstance(res, messages.WordRequest):
        try:
            inp = input_callback(res.type)
            res = client.call(messages.WordAck(word=inp))
        except Cancelled:
            res = client.call(messages.Cancel())

    client.init_device()
    return res


@expect(messages.Success, field="message")
@session
def reset(
        client,
        display_random=False,
        strength=None,
        passphrase_protection=False,
        pin_protection=False,
        label=None,
        language="en-US",
        u2f_counter=0,
        skip_backup=False,
        no_backup=False,
        backup_type=messages.BackupType.Bip39,
):
    if client.features.initialized:
        raise RuntimeError(
            "Device is initialized already. Call wipe_device() and try again."
        )

    if strength is None:
        if client.features.model == "1":
            strength = 256
        else:
            strength = 128

    # Begin with device reset workflow
    msg = messages.ResetDevice(
        display_random=bool(display_random),
        strength=strength,
        passphrase_protection=bool(passphrase_protection),
        pin_protection=bool(pin_protection),
        language=language,
        label=label,
        u2f_counter=u2f_counter,
        skip_backup=bool(skip_backup),
        no_backup=bool(no_backup),
        backup_type=backup_type,
    )

    resp = client.call(msg)
    if not isinstance(resp, messages.EntropyRequest):
        raise RuntimeError("Invalid response, expected EntropyRequest")

    external_entropy = os.urandom(32)
    # LOG.debug("Computer generated entropy: " + external_entropy.hex())
    ret = client.call(messages.EntropyAck(entropy=external_entropy))
    client.init_device()
    return ret


@expect(messages.Success, field="message")
def backup(client):
    ret = client.call(messages.BackupDevice())
    return ret


@expect(messages.BixinBackupAck, field="data")
def se_backup(client):
    ret = client.call(messages.BixinBackupRequest())
    return ret


@expect(messages.BixinWhiteListAck, field="address")
def bx_inquire_whitelist(client, type, addr_in=None):
    ret = client.call(messages.BixinWhiteListRequest(type=type, addr_in=addr_in))
    return ret


@expect(messages.Success, field="message")
def bx_add_or_delete_whitelist(client, type, addr_in=None):
    ret = client.call(messages.BixinWhiteListRequest(type=type, addr_in=addr_in))
    return ret


@expect(messages.BixinOutMessageSE, field="outmessage")
def se_proxy(client, message):
    ret = client.call(messages.BixinMessageSE(inputmessage=bytes.fromhex(message)))
    return ret


@expect(messages.Success, field="message")
def se_restore(
        client, data, language="en-US", label="OneKey", passphrase_protection=True
):
    ret = client.call(
        messages.BixinRestoreRequest(
            data=bytes.fromhex(data),
            language=language,
            label=label,
            passphrase_protection=bool(passphrase_protection),
        )
    )
    return ret


@expect(messages.BixinVerifyDeviceAck)
def se_verify(client, data):
    ret = client.call(messages.BixinVerifyDeviceRequest(data=data))
    return ret


@expect(messages.BixinBackupDeviceAck, field='mnemonics')
def bixin_backup_device(client):
    ret = client.call(messages.BixinBackupDevice())
    return ret


@expect(messages.Success, field="message")
def bixin_load_device(
        client, mnemonics=None, language="en-US", label="OneKey", skip_checksum=False
):
    ret = client.call(
        messages.BixinLoadDevice(
            mnemonics=mnemonics,
            language=language,
            label=label,
            skip_checksum=bool(skip_checksum),
        )
    )
    return ret

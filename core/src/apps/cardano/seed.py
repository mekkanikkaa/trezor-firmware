import storage
from storage import cache
from trezor import wire
from trezor.crypto import bip32

from apps.cardano import SEED_NAMESPACE
from apps.common import mnemonic
from apps.common.passphrase import get as get_passphrase

if False:
    from typing import Tuple

    from apps.common.seed import Bip32Path, MsgIn, MsgOut, Handler, HandlerWithKeychain


class Keychain:
    """Cardano keychain hard-coded to SEED_NAMESPACE."""

    def __init__(self, root: bip32.HDNode) -> None:
        self.root = root

    def match_path(self, path: Bip32Path) -> Tuple[int, Bip32Path]:
        if path[: len(SEED_NAMESPACE)] != SEED_NAMESPACE:
            raise wire.DataError("Forbidden key path")
        return 0, path[len(SEED_NAMESPACE) :]

    def derive(self, node_path: Bip32Path) -> bip32.HDNode:
        _, suffix = self.match_path(node_path)
        # derive child node from the root
        node = self.root.clone()
        for i in suffix:
            node.derive_cardano(i)
        return node

    def __del__(self) -> None:
        self.root.__del__()


@cache.stored_async(cache.APP_CARDANO_ROOT)
async def get_keychain(ctx: wire.Context) -> Keychain:
    if not storage.is_initialized():
        raise wire.NotInitialized("Device is not initialized")

    passphrase = await get_passphrase(ctx)
    if mnemonic.is_bip39():
        # derive the root node from mnemonic and passphrase
        root = bip32.from_mnemonic_cardano(mnemonic.get_secret().decode(), passphrase)
    else:
        seed = mnemonic.get_seed(passphrase)
        root = bip32.from_seed(seed, "ed25519 cardano seed")

    # derive the namespaced root node
    for i in SEED_NAMESPACE:
        root.derive_cardano(i)

    keychain = Keychain(root)
    return keychain


def with_keychain(func: HandlerWithKeychain[MsgIn, MsgOut]) -> Handler[MsgIn, MsgOut]:
    def wrapper(ctx: wire.Context, msg: MsgIn) -> MsgOut:
        keychain = get_keychain(ctx)
        try:
            return func(ctx, msg, keychain)
        finally:
            keychain.__del__()

    return wrapper

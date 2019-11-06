#! /usr/bin/env python3

from hashlib import sha256
from subprocess import run
from uuid import uuid4 as uuid, UUID
from typing import Union
from base64 import b32encode
import tempfile

import pygit2 as git  # type: ignore

# --- test data ---


def store_hash(seed: Union[int, UUID, None] = None) -> str:
    if seed is None:
        seed = uuid()

    with tempfile.NamedTemporaryFile() as f:
        f.write(f"{seed}".encode("utf-8"))
        f.seek(0)
        return str(
            run(
                [
                    "nix-hash",
                    "--type",
                    "sha256",
                    "--truncate",
                    "--base32",
                    "--flat",
                    f.name,
                ],
                capture_output=True,
            )
            .stdout.strip()
            .decode("utf-8")
        )


def nar_hash(seed: str) -> str:
    return sha256(f"{seed}".encode("utf-8")).hexdigest()


# --- test ---

if __name__ == "__main__":
    for i in range(0, 10):
        store = store_hash(i)
        nar = nar_hash(store)
        print(f"store: {store} // nar: {nar}")

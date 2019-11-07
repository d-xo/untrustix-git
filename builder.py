#! /usr/bin/env python3

from base64 import b32encode
from hashlib import sha256
from pathlib import Path
from subprocess import run
from tempfile import NamedTemporaryFile, mkdtemp
from typing import Optional
from uuid import uuid4 as uuid

import pygit2 as git  # type: ignore

# --- test data ---


def store_hash(seed: Optional[str] = None) -> str:
    """hash `seed` using the nix store hash format. `seed` is random if not provided"""
    if seed is None:
        seed = uuid().hex

    with NamedTemporaryFile() as f:
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


def nar_hash(seed: Optional[str] = None) -> str:
    """hash `seed` using the using sha256. `seed` is random if not provided"""
    if seed is None:
        seed = uuid().hex

    return sha256(f"{seed}".encode("utf-8")).hexdigest()


def create_repo() -> git.Repository:
    """create a git repo in a new temporary directory. configure it to allow for partial clones"""
    d = mkdtemp()
    repo = git.init_repository(d, bare=True)

    # add partial clone support
    conf = repo.config
    conf["uploadpack.allowfilter"] = 1
    conf["uploadpack.allowanysha1inwant"] = 1

    return repo


# --- repo utils ---


def write_build(store_hash: str, content_hash: str) -> None:
    pass


# --- test ---

if __name__ == "__main__":
    repo = create_repo()

    for i in range(0, 10):
        store = store_hash(f"{i}")
        nar = nar_hash(store)
        print(f"store: {store} // nar: {nar}")

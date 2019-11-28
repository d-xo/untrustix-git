#! /usr/bin/env python3

"""
You can emulate a lightweight follower by fetching using `git clone --filter=tree:0 --depth=1
--no-checkout --no-hardlinks file://<PATH_TO_REPO> client`. This will fetch only the latest commit
object. It will not fetch any tree or blob objects referenced in the commit. It will not checkout
any data into the worktree. Note that this must be done on a local copy of the repo, as github
currently does not support partial clones.

You can then query individual build results by recursively calling `git fetch-pack --filter=tree:0
file://<PATH_TO_REPO> <OBJECT_HASH>` inside the client repository until you reach the desired leaf
node.

./fetcher.py --repo <REPO_PATH> <STORE_HASH>
"""

from argparse import ArgumentParser
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional
import subprocess

import common


def run(cmd: str, cwd: Optional[Path] = None) -> str:
    """run `cmd` and return the output, print stderr and bail if it fails"""
    try:
        return str(
            subprocess.run(
                cmd.split(), capture_output=True, check=True, cwd=cwd
            ).stdout.decode("utf-8")
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr.decode("utf-8"))
        exit(1)


def fetch_object(remote: str, repo: Path, oid: str) -> None:
    run(f"git fetch-pack --filter=tree:0 {remote} {oid}", cwd=repo)
    run(f"git cat-file -p {oid}")


def get_tree_id(repo: Path, commit_id: str) -> str:
    return "hi"


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Fetch a build result from an untrustix-git repo using the lightweight protocol"
    )
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="The repo containing the build log, can be any repo url supported by git",
    )
    parser.add_argument(
        "store_hash",
        type=str,
        help="The store hash identifying the build that should be fetched",
    )
    args = parser.parse_args()

    dest = mkdtemp()

    print(f"initializing light client for {args.repo} in {dest}")
    run(f"git clone --filter=tree:0 --depth=1 --bare --no-hardlinks {args.repo} {dest}")

    commit = run("git rev-parse HEAD", cwd=Path(dest)).strip("\n")
    print(f"fetched commit: {commit}")

    shards = common.shards(args.store_hash)
    print(f"fetching tree branch for {shards}")

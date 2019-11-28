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
import re
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


def fetch_object(remote: str, repo: str, oid: str) -> None:
    """fetch the object identified by `oid` into `repo` from `remote`"""
    run(f"git fetch-pack --filter=tree:0 {remote} {oid}", cwd=repo)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Fetch a build result from an untrustix-git repo using the lightweight protocol"
    )
    parser.add_argument(
        "--remote",
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

    repo = mkdtemp()

    print(f"initializing light client for {args.remote} in {repo}")
    run(f"git clone --filter=tree:0 --depth=1 --bare --no-hardlinks {args.remote} {repo}")
    print(run(f"du -sh {repo}"))

    commit_id = run("git rev-parse HEAD", cwd=repo).strip("\n")
    print(f"fetched commit: {commit_id}")
    print(run(f"du -sh {repo}"))

    raw_commit = run(f"git cat-file -p {commit_id}", cwd=repo)
    tree_root = re.match(r"^tree\s(\w{40})$", raw_commit, re.MULTILINE).groups()[0]
    print(f"fetching tree root: {tree_root}")
    fetch_object(args.remote, repo, tree_root)
    print(run(f"du -sh {repo}"))


    # shards = common.shards(args.store_hash)
    # print(f"fetching branch for {shards}")
    # print(run(f"du -sh {repo}"))

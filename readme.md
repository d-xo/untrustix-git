# untrustix-git

This is a design / proof of concept for a git backed append only log of nix build results. It makes
use of the new [partial clone](https://git-scm.com/docs/partial-clone) features in git to allow for
relatively lightweight log followers.

As far as I can tell there are no major git hosting services that currently support partial clones
in git, although gitlab are currently working to enable support
([ref](https://docs.gitlab.com/ee/topics/git/partial_clone.html)). It does however work with self
hosted repos (I have tested with the `ssh` and `git` protocols).

If a git client requests an object, the git transfer protocol currently specifies that the server
returns the requested objects, and *all dependendent objects*. This means that it is not possible
for a git client to request a single build result and it's associated inclusion proof (a.k.a merkle
branch).

This unfortunately mean that log followers must retain more state than is ideal, meaning that git is
probably not a good choice for logs that are expected to grow very large (e.g. a log containing ~3.3
million builds requires clients to maintain 169 MiB of state locally).

If the transfer protocol was improved to allow more granularity in the transferred objects, it should
be possible to construct log followers that require only a few hundred kilobytes of state.

What follows is a description of the most efficient protocol I was able to devise given the
limitations of the current transfer protocol.

## Protocol Overview

The repo is a mapping from store paths to build results, backed by a verifiable log of state
transitions.

Build results for each store path are stored in a file with the name of that store hash. Build
results are sharded into subdirectories based on the first characters of their store hash, this
keeps directory sizes (and tree objects) reasonable. To make matters more concrete the expected
contents of the store path identified by `zzlfqv4p4hf55saim00zc9vvqj08nxjb` would be written to a
file at `zz/lf/qv4p4hf55saim00zc9vvqj08nxjb`).

Each time a new build is added to the log, a new commit object is created. The commit message is as
follows `<STORE_HASH> <BUILD_RESULT>`. This means that the commit object contains all information
needed for the client to construct the new root hash using only state that it retains locally, so
clients need to fetch the commit objects only.

## Clients

### Synchronisation

Clients start from a known good commit (the first if they are paranoid). They store the tree objects
(directories), but not the blobs (file contents) for that commit. For each new commit they locally
add the data specified in the commit message to the directory tree and compute the new root hash. If
it matches the root hash specified in the commit object, then they can be sure that the commit
contains only the addition specified in the commit message. They can then throw away the old commit
and any orphaned tree objects and repeat for the next commit.

### Lookup

Clients simply request the blob specified in the newest copy of the directory tree (e.g. `git cat-file -p
<BLOB_HASH>`). This fetches the blob from the remote.

## Builders

Builders need store the same state as the client. They can keep only the most recent commit and the
directory tree. When they wish to add a new build they:

1. Insert the build result and calculate the new root hash
1. Commit the new state and write the addition to the commit message
1. Push their changes

## Testing

A small script `builder.py` is included in this repo that can be used to generate fake build results
and commit them to a log. I ran it for a few days and generated a test repository with ~3.3 million
builds. This repo is 7.6GiB on disk, and a client would need to store 169MiB of state locally.

This repo is available here: https://github.com/xwvvvvwx/untrustix-git-testdata.

You can emulate a client by fetching using `git clone --filter=blob:none --depth=1 --no-checkout
--no-hardlinks file://<PATH_TO_REPO> pruned`. This will perform a shallow clone and fetch only the
tree data for the latest commit, it will not checkout any data into the worktree. Note that this
must be done on a local copy of the repo, as github currently does not support partial clones.


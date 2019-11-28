from typing import List


def shards(path: str, depth: int = None) -> List[str]:
    """
    returns the list of directories that a given store path will be written to

    >>> shards("xajasisp7xdgy1fvxhm3rbia7wxazaf9", depth=5)
    ['xa', 'ja', 'si', 'sp', '7x', 'dgy1fvxhm3rbia7wxazaf9']

    >>> shards("xajasisp7xdgy1fvxhm3rbia7wxazaf9", depth=3)
    ['xa', 'ja', 'si', 'sp7xdgy1fvxhm3rbia7wxazaf9']

    >>> shards("xajasisp7xdgy1fvxhm3rbia7wxazaf9")
    ['xa', 'ja', 'sisp7xdgy1fvxhm3rbia7wxazaf9']
    """
    if depth is None:
        depth = 2

    if len(path) != 32:
        raise Exception("invalid store path")

    shards = []
    for i in range(0, depth):
        shards.append(path[2 * i : 2 * i + 2])
    shards.append(path[2 * depth :])
    return shards

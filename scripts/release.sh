#!/bin/bash
set -e

VERSION="v$(cat VERSION)"

echo "Releasing $VERSION"

# Remove tag locally if it exists
if git tag | grep -q "^$VERSION$"; then
    echo "Tag $VERSION exists locally, removing..."
    git tag -d "$VERSION"
fi

# Remove tag from remote if it exists
if git ls-remote --tags origin | grep -q "refs/tags/$VERSION$"; then
    echo "Tag $VERSION exists on remote, removing..."
    git push origin ":refs/tags/$VERSION"
fi

# Delete the GitHub Release if it exists (requires gh cli)
if gh release view "$VERSION" &>/dev/null; then
    echo "GitHub Release $VERSION exists, deleting..."
    gh release delete "$VERSION" --yes
fi

# Push the tag
git tag "$VERSION"
git push origin "$VERSION"

echo "Done. $VERSION pushed."
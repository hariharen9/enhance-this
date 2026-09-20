#!/bin/bash

VERSION_FILE="enhance_this/version.py"
PACKAGE_JSON="package.json"

# Check if a new version argument is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <new_version>"
  echo "Example: $0 0.4.1"
  exit 1
fi

NEW_VERSION="$1"

# Extract the current version from version.py (the single source of truth).
# pyproject.toml reads its version dynamically from this file via
# [tool.setuptools.dynamic]; package.json mirrors it for the npm wrapper.
OLD_VERSION=$(grep -m 1 '__version__' "$VERSION_FILE" | sed 's/.*"\(.*\)".*/\1/')

if [ -z "$OLD_VERSION" ]; then
  echo "✖ Could not read the current version from $VERSION_FILE. Aborting."
  exit 1
fi

echo "----------------------------------------"
echo "  Automated Release Script"
echo "----------------------------------------"
echo "  Current enhance_this/version.py: $OLD_VERSION"
echo "  New version to set:             $NEW_VERSION"
echo "----------------------------------------"

# Confirm with user
read -p "Are you sure you want to update to version $NEW_VERSION and push? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborting release process."
    exit 1
fi

# Update enhance_this/version.py (the canonical version).
echo "Updating $VERSION_FILE to version $NEW_VERSION..."
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/^__version__ = .*/__version__ = \"$NEW_VERSION\"/" "$VERSION_FILE"
else
  sed -i "s/^__version__ = .*/__version__ = \"$NEW_VERSION\"/" "$VERSION_FILE"
fi

# Mirror the version into package.json for the npm wrapper.
echo "Updating $PACKAGE_JSON to version $NEW_VERSION..."
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/^[[:space:]]*\"version\": \".*\"/  \"version\": \"$NEW_VERSION\"/" "$PACKAGE_JSON"
else
  sed -i "s/^[[:space:]]*\"version\": \".*\"/  \"version\": \"$NEW_VERSION\"/" "$PACKAGE_JSON"
fi

# Add changes to Git
echo "Adding version changes to Git..."
git add "$VERSION_FILE" "$PACKAGE_JSON"

# Commit changes
echo "Committing version bump..."
git commit -m "Release v$NEW_VERSION"

# Create and push tag
echo "Creating Git tag v$NEW_VERSION..."
git tag "v$NEW_VERSION"

echo "Pushing commit and tag to remote..."
git push origin main # Push the commit
git push origin "v$NEW_VERSION" # Push the tag

echo "----------------------------------------"
echo "  Release process initiated for v$NEW_VERSION."
echo "  GitHub Actions CI/CD should now be triggered."
echo "----------------------------------------"
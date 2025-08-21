#!/bin/bash

# Check if a new version argument is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <new_version>"
  echo "Example: $0 0.1.2"
  exit 1
fi

NEW_VERSION="$1"
# Extract current version from pyproject.toml
OLD_PYPROJECT_VERSION=$(grep -m 1 'version = ' pyproject.toml | awk -F'"' '{print $2}')
# Extract current version from package.json
OLD_PACKAGE_VERSION=$(grep -m 1 '"version":' package.json | awk -F'"' '{print $4}') # Assuming "version": "X.Y.Z" 

echo "----------------------------------------"
echo "  Automated Release Script"
echo "----------------------------------------"
echo "  Current pyproject.toml version: $OLD_PYPROJECT_VERSION"
echo "  Current package.json version:   $OLD_PACKAGE_VERSION"
echo "  New version to set:             $NEW_VERSION"
echo "----------------------------------------"

# Confirm with user
read -p "Are you sure you want to update to version $NEW_VERSION and push? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborting release process."
    exit 1
fi

# Update pyproject.toml
echo "Updating pyproject.toml to version $NEW_VERSION..."
# Use sed -i '' for macOS compatibility (no backup file)
# Use sed -i for Linux compatibility
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/version = \"$OLD_PYPROJECT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
else
  sed -i "s/version = \"$OLD_PYPROJECT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
fi

# Update package.json
echo "Updating package.json to version $NEW_VERSION..."
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/^[[:space:]]*\"version\": \"$OLD_PACKAGE_VERSION\"/  \"version\": \"$NEW_VERSION\"/" package.json
else
  sed -i "s/^[[:space:]]*\"version\": \"$OLD_PACKAGE_VERSION\"/  \"version\": \"$NEW_VERSION\"/" package.json
fi


# Add changes to Git
echo "Adding version changes to Git..."
git add pyproject.toml package.json

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

#!/bin/sh
set -e

cd /app

git config --global --add safe.directory /app

# Get the 5 most recent tags
TAGS=$(git tag --sort=-creatordate | head -n 5)

# If there are no tags, use the last 5 commits
if [ -z "$TAGS" ]; then
    TAGS=$(git log --format="%h" -n 5)
fi

# Make sure we're on the latest commit
git checkout $(git remote show origin | sed -n '/HEAD branch/s/.*: //p')

cd docs

# Create a version for each tag
for TAG in $TAGS; do
    echo "Creating version $TAG"
    npm run docusaurus docs:version $TAG
done

# Build the docs
npm run build

# Create a versions.txt file
echo $TAGS > /app/docs/build/versions.txt
echo "latest" >> /app/docs/build/versions.txt

# Print the versions
echo "Built versions:"
cat /app/docs/build/versions.txt

set -ex
VERSION=`awk -F\' '{print $2,$4}' message_adapter/version.py`
export LATEST_TAG=$(curl -H \
  "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nasa/cumulus-message-adapter/tags | jq --raw-output '.[0].name')

if [ "$VERSION_TAG" != "$LATEST_TAG" ]; then
  echo "tag does not exist for version $VERSION_TAG, creating tag"

  # create git tag
  git tag -a "$VERSION_TAG" -m "$VERSION_TAG" || echo "$VERSION_TAG already exists"
  git push origin "$VERSION_TAG"
fi

export RELEASE_URL=$(curl -H \
  "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nasa/cumulus-message-adapter/releases/tags/$VERSION_TAG | jq --raw-output '.url // ""')

if [ -z "$RELEASE_URL" ]; then
  echo "release does not exist"

  curl -H \
    "Authorization: token $GITHUB_TOKEN" \
    -d "{\"tag_name\": \"$VERSION_TAG\", \"name\": \"$VERSION_TAG\", \"body\": \"Release $VERSION_TAG\" }"\
    -H "Content-Type: application/json"\
    -X POST \
    https://api.github.com/repos/nasa/cumulus-message-adapter/releases
fi

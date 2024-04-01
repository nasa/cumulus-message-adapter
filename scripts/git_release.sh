
set -ex
yum update -y && yum install -y zip openssh-clients git curl make jq binutils
GIT_API_URL=https://api.github.com/repos
VERSION_TAG=`awk -F\' '{print $2}' ./message_adapter/version.py`
GIT_PATH=nasa/cumulus-message-adapter
git config --global user.email "cumulus.bot@gmail.com"
git config --global user.name "cumulus-bot"

export LATEST_TAG=$(curl -H \
  "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nasa/cumulus-message-adapter/tags | jq --raw-output '.[0].name')

if [ "$VERSION_TAG" != "$LATEST_TAG" ]; then
  echo "tag does not exist for version $VERSION_TAG, creating tag"
  # get notes
  
  # create git tag
  git tag -a "$VERSION_TAG" -m "$VERSION_TAG"
  git push https://cumulus-bot:${GITHUB_TOKEN}@github.com/nasa/cumulus-message-adapter "$VERSION_TAG"

fi


export RELEASE_URL=$(curl -H \
  "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nasa/cumulus-message-adapter/releases/tags/$VERSION_TAG | jq --raw-output '.url // ""')

if [ -z "$RELEASE_URL" ]; then
  echo "release does not exist"
  RELEASE_NOTES=$(python scripts/separate_release_notes.py ${VERSION_TAG})
  curl -H \
    "Authorization: token $GITHUB_TOKEN" \
    --data-binary "{\"tag_name\": \"$VERSION_TAG\", \"name\": \"$VERSION_TAG\", \"body\": \"$RELEASE_NOTES\" }"\
    -H "Content-Type: application/json"\
    -X POST \
    https://api.github.com/repos/nasa/cumulus-message-adapter/releases
fi
ZIPFILENAME=cumulus-message-adapter.zip
pip install .
make clean
make $ZIPFILENAME
if [ -f $ZIPFILENAME ]; then
  UPLOAD_URL_TEMPLATE=$(curl $GIT_API_URL/$GIT_PATH/releases/tags/$VERSION_TAG | jq '.upload_url' --raw-output)
  UPLOAD_URL=${UPLOAD_URL_TEMPLATE//{?name,label\}/?name=$ZIPFILENAME}
  echo "Uploading release to ${UPLOAD_URL}"
  curl -X POST -u etcart:$GITHUB_TOKEN \
    -H "Content-Type: application/zip" \
    $UPLOAD_URL \
    --data-binary @./$ZIPFILENAME | jq .
else
    echo "$ZIPFILENAME does not exist."
    exit 1
fi
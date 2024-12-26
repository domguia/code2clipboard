# usefull command

# change version
bump2version patch
bump2version minor

# push to git (with made by bump2version tag)
git push origin

# build
python -m build
# publish to pypip
twine upload --repository pypi dist/*


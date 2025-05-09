@echo off
echo Pushing changes to GitHub...

echo Adding modified files...
git add app.py requirements.txt templates/index.html push_to_github.bat

echo Committing changes...
git commit -m "Push project to new repository"

echo Pushing to GitHub...
git push origin master

echo Done!
pause

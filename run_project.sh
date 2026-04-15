#!/bin/bash

cd "$(dirname "$0")"

echo "Project folder: $(pwd)"

# Create venv if missing
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate venv 
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Virtual environment activation failed"
    exit 1
fi

# Install only once
if [ ! -f ".installed" ]; then
    echo "Installing requirements..."
    pip install -r requirements.txt
    touch .installed
fi

# Git push option
read -p "Do you want to push to git? (y/n): " git_choice
if [ "$git_choice" = "y" ] || [ "$git_choice" = "Y" ]; then
    read -p "Enter commit message: " commit_msg
    git add .
    git commit -m "$commit_msg"
    git push
    echo "Git push complete."
else
    echo "Skipping git push."
fi

echo "Running migrations..."
python manage.py migrate

echo "Starting Django server..."
python manage.py runserver
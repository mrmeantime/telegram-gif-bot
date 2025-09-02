#!/bin/bash
# Install system packages
apt-get update
apt-get install -y ffmpeg

# Install Python dependencies
pip install -r requirements.txt
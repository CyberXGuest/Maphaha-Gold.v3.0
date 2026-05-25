# 1. Install Termux from F-Droid (NOT Google Play Store)
# Download from: https://f-droid.org/en/packages/com.termux/

# 2. Open Termux and update packages
pkg update && pkg upgrade -y

# 3. Install Python
pkg install python -y

# 4. Install required packages
pkg install python-pip -y
pkg install git -y
pkg install nano -y
pkg install openssl -y

# 5. Upgrade pip
pip install --upgrade pip

# 6. Give storage permission
termux-setup-storage
# Step 3: Make executable
chmod +x Termux.py

# Step 4: Run
python Termux.py

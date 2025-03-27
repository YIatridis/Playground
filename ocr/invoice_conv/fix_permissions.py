import os
import stat

# Path to database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sql_app.db')

def fix_permissions():
    """Fix permissions on the SQLite database"""
    if os.path.exists(DB_PATH):
        print(f"Fixing permissions for {DB_PATH}")
        
        # Get current permissions
        current_mode = os.stat(DB_PATH).st_mode
        print(f"Current permissions: {oct(current_mode)}")
        
        # Set read/write permissions for user and group
        os.chmod(DB_PATH, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)
        
        # Verify new permissions
        new_mode = os.stat(DB_PATH).st_mode
        print(f"New permissions: {oct(new_mode)}")
        
        # Check if the file is writable
        if os.access(DB_PATH, os.W_OK):
            print("Database is now writable!")
        else:
            print("WARNING: Database is still not writable!")
        
        # Check ownership
        import pwd
        user = pwd.getpwuid(os.stat(DB_PATH).st_uid).pw_name
        print(f"File is owned by: {user}")
    else:
        print(f"Database file not found: {DB_PATH}")
    
    # Check the directory permissions too
    db_dir = os.path.dirname(DB_PATH)
    if os.path.exists(db_dir):
        print(f"Checking directory permissions for {db_dir}")
        dir_mode = os.stat(db_dir).st_mode
        print(f"Directory permissions: {oct(dir_mode)}")
        
        # Make sure directory is writable
        if not os.access(db_dir, os.W_OK):
            print("Making directory writable")
            os.chmod(db_dir, dir_mode | stat.S_IWUSR | stat.S_IWGRP)

if __name__ == "__main__":
    fix_permissions()
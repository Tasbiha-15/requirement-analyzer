import csv
import os

USERS_CSV = 'users.csv'  # Ye file project folder mein create hogi aur users ka data store karegi

def load_users():
    users = {}
    if os.path.exists(USERS_CSV):
        with open(USERS_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                users[row['email']] = {
                    'name': row['name'],
                    'password': row['password']
                }
    return users

def save_user_to_csv(name, email, password):
    file_exists = os.path.isfile(USERS_CSV)
    with open(USERS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['name', 'email', 'password'])
        writer.writerow([name, email, password])

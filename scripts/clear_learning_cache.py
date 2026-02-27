import os
import glob

def rm(path):
    try:
        os.remove(path)
        print("Removed", path)
    except Exception as e:
        print("Error removing", path, e)

# Remove learning_store DB
db = os.path.join(os.getcwd(), 'learning_store.sqlite')
if os.path.exists(db):
    rm(db)
else:
    print('No learning_store.sqlite found')

# Remove cached TXT files
patterns = [
    'media/conversor/processing/**/*_texto_universal.txt',
    'media/conversor/processing/**/*_padrao.txt'
]
removed = 0
for pat in patterns:
    for p in glob.glob(pat, recursive=True):
        rm(p)
        removed += 1

print(f"Done. Removed {removed} cached files.")

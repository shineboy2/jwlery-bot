import os, re

base_dir = '/home/shahab/bot/boutique_erp/app/bot/handlers'
for root, _, files in os.walk(base_dir):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r') as file:
                content = file.read()
            
            content = re.sub(r'([ \t]+)from bale import InlineKeyboardButton[ \t]+from app\.bot\.keyboards\.inline import build_kb',
                             r'\1from bale import InlineKeyboardButton\n\1from app.bot.keyboards.inline import build_kb',
                             content)
            
            with open(path, 'w') as file:
                file.write(content)
print("Indentation fixed again")

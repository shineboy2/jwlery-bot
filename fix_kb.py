import os
import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    if filepath.endswith('inline.py'):
        # Just replace return InlineKeyboardMarkup with return build_kb
        content = re.sub(r'return InlineKeyboardMarkup\(\[', r'return build_kb([', content)
        content = re.sub(r'return InlineKeyboardMarkup\(buttons\)', r'return build_kb(buttons)', content)
    else:
        # In handlers, replace InlineKeyboardMarkup(...) with build_kb(...)
        # and we must import build_kb
        if 'InlineKeyboardMarkup' in content and 'build_kb' not in content:
            content = content.replace(
                'from bale import InlineKeyboardMarkup, InlineKeyboardButton',
                'from bale import InlineKeyboardButton\nfrom app.bot.keyboards.inline import build_kb'
            )
            content = re.sub(r'InlineKeyboardMarkup\(\[', r'build_kb([', content)
            content = re.sub(r'InlineKeyboardMarkup\(buttons\)', r'build_kb(buttons)', content)

    with open(filepath, 'w') as f:
        f.write(content)

base_dir = '/home/shahab/bot/boutique_erp/app/bot'
fix_file(os.path.join(base_dir, 'keyboards', 'inline.py'))

for root, _, files in os.walk(os.path.join(base_dir, 'handlers')):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

print("Fixed keyboards!")

import os, re

base_dir = '/home/shahab/bot/boutique_erp/app/bot/handlers'

for root, _, files in os.walk(base_dir):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r') as file:
                content = file.read()
            
            # Replace alerts with message.reply
            content = re.sub(
                r'await callback\.answer\(([^,]+),\s*show_alert=True\)',
                r'await callback.message.reply(\1)',
                content
            )
            content = re.sub(
                r'await callback\.answer\(([^,]+),\s*show_alert=False\)',
                r'# \1 (silent callback answer)',
                content
            )
            # Replace loading state (just a string) with comment
            content = re.sub(
                r'await callback\.answer\(([^,]+)\)',
                r'# loading: \1',
                content
            )

            with open(path, 'w') as file:
                file.write(content)

print("Callback answers fixed!")

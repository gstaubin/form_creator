import PyInstaller.__main__
import os
import form_creator

package_name = "form_creator.py"
output_name = "FormCreator{}".format(form_creator.VERSION)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    '--name=%s' % output_name,

    '--noconfirm',
    '--onefile',
    os.path.join(BASE_DIR, package_name),
])

# '--icon=%s' % os.path.join(BASE_DIR, BASE_DIR, 'icon.ico'),
# '--add-data={};{}'.format(os.path.join(BASE_DIR, 'style_sheet.c'), os.path.join(BASE_DIR, "dist", output_name)),

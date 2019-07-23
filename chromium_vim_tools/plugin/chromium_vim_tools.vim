let s:plugin_root_dir = fnamemodify(resolve(expand('<sfile>:p')), ':h')

python3 << EOF
import sys
import os
import vim
plugin_root_dir = vim.eval('s:plugin_root_dir')
python_root_dir = os.path.normpath(
  os.path.join(plugin_root_dir, '..', 'plugin'))
sys.path.insert(0, python_root_dir)
import main
EOF

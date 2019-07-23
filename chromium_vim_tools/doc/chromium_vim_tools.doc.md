

INSTALLING:
 install neovim: `# apt-get install neovim`
 install pyenv: `$ curl https://pyenv.run | bash`
 setup pyenv: `$ pyenv install 3.6.5`
              `$ pyenv virtualenv 3.6.5 neovim`
              `$ pyenv activate neovim3`
 install neovim python: `$ pip install neovim`
 copy the output from `pyenv which python`
 paste output into `~/.config/nvim/init.vim` like:
   `let g:python3_host_prog = 'path you just copied'`



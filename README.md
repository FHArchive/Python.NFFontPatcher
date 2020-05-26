[![Github top language](https://img.shields.io/github/languages/top/FredHappyface/Python.NFFontPatcher.svg?style=for-the-badge)](../../)
[![Codacy grade](https://img.shields.io/codacy/grade/[codacy-proj-id].svg?style=for-the-badge)](https://www.codacy.com/manual/FredHappyface/Python.NFFontPatcher)
[![Repository size](https://img.shields.io/github/repo-size/FredHappyface/Python.NFFontPatcher.svg?style=for-the-badge)](../../)
[![Issues](https://img.shields.io/github/issues/FredHappyface/Python.NFFontPatcher.svg?style=for-the-badge)](../../issues)
[![License](https://img.shields.io/github/license/FredHappyface/Python.NFFontPatcher.svg?style=for-the-badge)](/LICENSE.md)
[![Commit activity](https://img.shields.io/github/commit-activity/m/FredHappyface/Python.NFFontPatcher.svg?style=for-the-badge)](../../commits/master)
[![Last commit](https://img.shields.io/github/last-commit/FredHappyface/Python.NFFontPatcher.svg?style=for-the-badge)](../../commits/master)

# Python.NFFontPatcher

The NerdFont font patcher

## Rationale
Cloning nerdfonts is a rather laborious process so this repo just has the bits
you need to build your own nerd font

## Usage
1. Install fontforge
	```powershell
	choco install fontforge
	```
2. Locate the interactive terminal
   1. FontForge > Open File Location
   2. Open FontForge interactive console
3. Change directory to the project root (the parent dir of this readme)
	```powershell
	cd .../git/Python.NFFontPatcher
	```
4. Run patch.py (you may want to use the help flag for more options)
	```cmd
	fontforge -script patch.py PATH -c -w
	```
	For example
	```cmd
	fontforge -script patch.py otf\\FiraCode-Bold.oft -c -w
	```
	or
	```cmd
	fontforge -script patch.py otf -c -w -out otf_out
	```



## Language information
### Built for
This program has been written for Python 3 and has been tested with
Python version 3.8.0 <https://www.python.org/downloads/release/python-380/>.

## Install Python on Windows
### Chocolatey
```powershell
choco install python
```
### Download
To install Python, go to <https://www.python.org/> and download the latest
version.

## Install Python on Linux
### Apt
```bash
sudo apt install python3.8
```

## How to run
### With VSCode
1. Open the .py file in vscode
2. Ensure a python 3.8 interpreter is selected (Ctrl+Shift+P > Python:Select
Interpreter > Python 3.8)
3. Run by pressing Ctrl+F5 (if you are prompted to install any modules, accept)
### From the Terminal
```bash
./[file].py
```


## Download
### Clone
#### Using The Command Line
1. Press the Clone or download button in the top right
2. Copy the URL (link)
3. Open the command line and change directory to where you wish to
clone to
4. Type 'git clone' followed by URL in step 2
```bash
$ git clone https://github.com/FredHappyface/Python.NFFontPatcher
```

More information can be found at
<https://help.github.com/en/articles/cloning-a-repository>

#### Using GitHub Desktop
1. Press the Clone or download button in the top right
2. Click open in desktop
3. Choose the path for where you want and click Clone

More information can be found at
<https://help.github.com/en/desktop/contributing-to-projects/cloning-a-repository-from-github-to-github-desktop>

### Download Zip File

1. Download this GitHub repository
2. Extract the zip archive
3. Copy/ move to the desired location


## Community Files
### Licence
MIT License
(See the [LICENSE](/LICENSE.md) for more information.)

### Changelog
See the [Changelog](/CHANGELOG.md) for more information.

### Code of Conduct
In the interest of fostering an open and welcoming environment, we
as contributors and maintainers pledge to make participation in our
project and our community a harassment-free experience for everyone.
Please see the
[Code of Conduct](https://github.com/FredHappyface/.github/blob/master/CODE_OF_CONDUCT.md) for more information.

### Contributing
Contributions are welcome, please see the [Contributing Guidelines](https://github.com/FredHappyface/.github/blob/master/CONTRIBUTING.md) for more information.

### Security
Thank you for improving the security of the project, please see the [Security Policy](https://github.com/FredHappyface/.github/blob/master/SECURITY.md) for more information.

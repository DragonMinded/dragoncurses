# DragonCurses

A simple UI wrapper library around curses for python3. Supports mouse click events, keyboard input, rendering abstractions and automatic resizing events. Includes a few batteries-included components that allow you to build a simple UI.

Run "python3 -m example1" for a quick example.

## Current State

This library, while operational, is far from complete. It has a partial layout concept which it uses to display to the screen. However, it is top down rather than bottom up. So if you are expecting an HTML-style layout from your component specifications you will (currently) be disappointed. This library is used in several of my other open-source projects in order to bang out quick and easy-to-use console UIs for profile and settings editors. It is definitely usable for similar tasks if you so desire.

## Installing

This package is available on PyPI under the "dragoncurses" package and can be installed with pip or placed in a requirements.txt or setup.py file. Alternatively, you can check out this repository and then type "python3 -m pip install ." at the root to install the current development version. Please note that it requires a modern version of Python3 to run (Python 3.6 or greater).

## Developing

There are settings files for both mypy and flake8. Black is used to format the entire repository, with no settings tweaks. To check for type issuse, run "mypy ." at the root of the project. Similarly, to check for lint issues, run "flake8 ." at the root of the project. To autoformat code, run "black ." at the root of the project.

"""Hermes-inspired terminal theme."""

from __future__ import annotations

LOGO = r"""
 ██╗     ██╗     ███╗   ███╗
 ██║     ██║     ████╗ ████║
 ██║     ██║     ██╔████╔██║
 ██║     ██║     ██║╚██╔╝██║
 ███████╗███████╗██║ ╚═╝ ██║
 ╚══════╝╚══════╝╚═╝     ╚═╝
"""

APP_CSS = """
Screen {
    background: #0a0a0a;
}

#root {
    height: 100%;
    layout: vertical;
}

#header {
    height: auto;
    padding: 0 2;
    margin-top: 1;
}

#logo {
    color: #c9a227;
    width: auto;
    height: auto;
}

#meta {
    color: #888888;
    padding: 0 0 0 2;
    height: auto;
}

#meta-line {
    color: #c9a227;
}

#main {
    height: 1fr;
    padding: 0 2;
}

#step-title {
    color: #c9a227;
    text-style: bold;
    height: auto;
    margin: 1 0;
}

#step-body {
    height: 1fr;
    scrollbar-color: #333333;
    scrollbar-background: #0a0a0a;
}

.section-label {
    color: #c9a227;
    text-style: bold;
    margin: 1 0 0 0;
    height: auto;
}

.skill-line {
    height: auto;
    margin: 0;
    padding: 0;
}

.skill-key {
    color: #c9a227;
}

.skill-val {
    color: #cccccc;
}

ChoiceList {
    height: auto;
    max-height: 12;
    border: none;
    padding: 0;
    margin: 1 0;
}

ChoiceList:focus {
    background: #111100;
}

ChoiceItem {
    height: 1;
    padding: 0 1;
}

ChoiceItem.selected {
    background: #2a2a00;
    color: #ffe566;
}

ChoiceItem.checked {
    color: #3ecf3e;
}

#choices-panel {
    height: auto;
    max-height: 14;
    border-top: solid #333333;
    padding-top: 1;
}

#footer-panel {
    dock: bottom;
    height: auto;
    border: solid #8b3a3a;
    padding: 1 2;
    margin: 0 2 1 2;
    background: #0d0d0d;
}

#welcome {
    color: #dddddd;
    height: auto;
}

#status-bar {
    color: #888888;
    height: auto;
    margin-top: 1;
}

#status-gold {
    color: #c9a227;
}

#hint-bar {
    color: #666666;
    height: auto;
    margin-top: 1;
}

Input {
    margin: 1 0;
    border: solid #444444;
    background: #111111;
    color: #eeeeee;
    padding: 0 1;
}

Input:focus {
    border: solid #c9a227;
}

#doctor-log {
    height: 1fr;
    border: none;
    background: transparent;
}

#deploy-log {
    height: 12;
    border: solid #333333;
    margin-top: 1;
    padding: 0 1;
}

#command-input {
    margin-top: 1;
    border: solid #444444;
    background: #111111;
    color: #eeeeee;
    padding: 0 1;
}

#command-input:focus {
    border: solid #8b3a3a;
}
"""

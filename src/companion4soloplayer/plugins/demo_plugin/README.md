# Demo Plugin

Game System Demo Plugin.

## Disclaimer

The mechanics implemented are generic board game concepts that are not protected by copyright.

## Features

- Grid-based dungeon mapping
- 2d6 room generation
- Simple character progression
- Exploration mechanics
- Character creation workflow (races, classes, attributes, skills,
  spells) declared in `datas/workflow.yaml` with Condition/Effect
  bonuses in `datas/creation_rules.yaml`; `datas/races.yaml` and
  `datas/classes.yaml` declare `can_cast_spells` (spellcasting flag
  gating the spells block of the creation dialog)

## Usage

This plugin is automatically loaded by Companion4SoloPlayer when selected in the application.

# retrotracker

Uses OCR to watch screen and parse retrommo battle events. Keep track of damage
dealt, gold and exp earned.

Fixing OCR typos with known retrommo names is a work in progres..

## executables
There are 3 executable python scripts for using retrotracker:
1. retrotracker.py - the actual tracker/parser
1. modify.py - queries for editing the database
1. query.py - read-only database queries

## basic usage
1. start by initializing the database: `./modify.py init`
1. create some player stats
  1. use preset stats `./modify create_presets`
  1. or use the interactive tool `./modify add_player`
1. set up screen capture coordinates (TODO)
1. run the tracker `./retrotracker.py start "retrommo username" "stats alias"
  1. retrommo is whatever name appears on screen text
  1. stats alias was created in step 2 above
